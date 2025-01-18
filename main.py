import os
import time
import json

from google.oauth2 import service_account
from googleapiclient.http import MediaFileUpload
from googleapiclient.discovery import build
from pathlib import Path
from pprint import pformat

from typing import Iterable, Generator, Tuple, Set, List
from abc import ABC, abstractmethod
from synology_api import filestation

from libs.logger import logger


class Drive(ABC):
    @abstractmethod
    def list_files_recursively(self, root_folder: str, only_dirs=True) -> set[str]:
        pass

    @abstractmethod
    def upload_files(self, files: Iterable[Tuple[Path | str, Path | str]]) -> Generator[Tuple[str, str], None, None]:
        # Generator[YieldType, SendType, ReturnType] --- Don't know about SendType :)
        pass


class SynologyFileStation:
    def __init__(self, ip, port, username, password):
        self.ip = ip
        self.port = port
        self.username = username
        self.password = password
        self.file_station: filestation.FileStation

    def __enter__(self):
        self.file_station = filestation.FileStation(self.ip, self.port, self.username, self.password, secure=True,
                                                    cert_verify=True, dsm_version=7, debug=False, otp_code=None)
        return self.file_station

    def __exit__(self, exception_type, exception_value, exception_traceback):
        self.file_station.logout()


class SynologyDrive(Drive):
    def __init__(self, config_path):
        with open(config_path) as f:
            config = json.load(f)

        self.file_station = SynologyFileStation(**config)

    def list_files_recursively(self, root_folder: str, only_dirs=True) -> set[str]:
        files = []
        with self.file_station as fs:
            data = fs.get_file_list(root_folder, filetype='dir' if only_dirs else None)['data']
            if data['total'] != 0:
                for folder in data['files']:
                    if folder['isdir']:
                        self.__recursive_dirs(folder['path'], files, fs, only_dirs)
                    else:
                        files.append(folder['path'])

        return set(os.path.relpath(file, root_folder) for file in files)

    def __recursive_dirs(self, root_folder, files: List[str], fs: filestation.FileStation, only_dirs):
        data = fs.get_file_list(root_folder, filetype='dir' if only_dirs else None)['data']
        if data['total'] == 0:
            if only_dirs:
                files.append(root_folder)
            return

        for folder in data['files']:
            if folder['isdir']:
                self.__recursive_dirs(folder['path'], files, fs, only_dirs)
            else:
                files.append(folder['path'])

    def upload_files(self, files: Iterable[Tuple[Path | str, Path | str]]) -> Generator[Tuple[str, str], None, None]:
        with self.file_station as fs:
            for local_path, dest_path in files:
                rs = fs.upload_file(file_path=str(local_path), dest_path=str(dest_path), progress_bar=False,
                                    verify=True)
                yield rs['data']['file'], local_path


class GoogleDrive(Drive):
    SCOPES = ['https://www.googleapis.com/auth/drive']

    def __init__(self, key_path: str, remote_folder_name: str):
        self.creds = self.get_cred(key_path)
        self.remote_folder_id = self.get_folder(remote_folder_name)

    @staticmethod
    def get_cred(service_account_json_key):
        return service_account.Credentials.from_service_account_file(filename=service_account_json_key,
                                                                     scopes=GoogleDrive.SCOPES)

    def set_remote_folder(self, remote_folder_name: str):
        self.remote_folder_id = self.get_folder(remote_folder_name)

    def find_files_by_query(self, query: str):
        # https://developers.google.com/drive/api/guides/ref-search-terms
        with build("drive", "v3", credentials=self.creds) as service:
            files = []
            page_token = None
            while True:
                response = (
                    service.files()
                    .list(
                        q=query,
                        spaces="drive",
                        fields="nextPageToken, files(id, name)",
                        pageToken=page_token,
                    )
                    .execute()
                )
                files.extend(response.get("files", []))
                page_token = response.get("nextPageToken", None)
                if page_token is None:
                    break
        return files

    def find_file_id_by_name(self, name: str):
        return list(map(lambda a: a.get('id'), self.find_files_by_query(f"name='{name}'")))

    def get_folder(self, folder_name):
        folders = self.find_file_id_by_name(folder_name)
        if len(folders) == 0:
            raise MyError(f'Remote folder "{folder_name}" not found!')

        if len(folders) > 1:
            raise MyError(f'Several files were found with the same name "{folder_name}"!')

        return folders[0]

    def list_files_recursively(self, root_folder: str, only_dirs=True) -> set[str]:
        return set(map(lambda a: a.get('name'), self.find_files_by_query(f"'{root_folder}' in parents")))

    def upload_files(self, files: Iterable[Tuple[Path | str, Path | str]]) -> Generator[Tuple[str, str], None, None]:
        with build("drive", "v3", credentials=self.creds) as service:
            for local_path, dest_path in files:
                file_metadata = {
                    'name': os.path.basename(local_path),
                    'parents': [self.remote_folder_id],
                }
                media = MediaFileUpload(local_path, resumable=True)
                r = service.files().create(body=file_metadata, media_body=media, fields='id, name').execute()
                yield r.get('name'), local_path

        return


def list_local_files_recursively(root_dir: Path) -> Set[str]:
    file_paths = set()
    for root, dirs, files in os.walk(root_dir):
        for file in files:
            file_paths.add(os.path.relpath(os.path.join(root, file), root_dir))
    return file_paths


class LocalFolderScanner:
    def __init__(self, folder_path, on_find_new_files: callable):
        self.folder_path = folder_path
        self.on_find_new_files = on_find_new_files

    def scanning(self, interval=3):
        files = set()
        try:
            while True:
                cur_files = list_local_files_recursively(self.folder_path)
                new_files = cur_files - files
                if len(new_files) > 0:
                    self.on_find_new_files(new_files)
                    files = cur_files
                time.sleep(interval)
        except KeyboardInterrupt:
            logger.info("Aborted.")


class MyError(BaseException):
    pass


def on_find(local_folder: str, remote_folder: str, drive_api: Drive, clear_downloads):
    def wrapped(new_files: set[str]):
        logger.info(f'Find new files: {new_files}')
        folder_content = drive_api.list_files_recursively(remote_folder, False)
        diff = new_files - folder_content
        if len(diff) > 0:
            logger.info(f'Files not on the disk:\n{pformat(diff)}')
            logger.info(f'Start uploading...')
            files_to_upload = [
                (Path(local_folder) / file_path, os.path.dirname(Path(remote_folder) / file_path)) for file_path in diff
            ]
            for file_name, local_path in drive_api.upload_files(files_to_upload):
                logger.info(f'"{file_name}" has been uploaded')
                if clear_downloads:
                    os.remove(local_path)
            logger.info(f'Uploading finished')
        else:
            if clear_downloads:
                for file in new_files:
                    os.remove(Path(local_folder) / file)
            logger.info(f'All new files on disk')

    return wrapped


def main():
    from init import remote_folder, local_folder, auth_key_path, drive_type, clear_downloads

    if drive_type == 'GOOGLE':
        try:
            drive_api = GoogleDrive(auth_key_path, remote_folder)
        except MyError as error:
            return logger.error(error)
    elif drive_type == 'SYNOLOGY':
        drive_api = SynologyDrive(auth_key_path)
        for folder in drive_api.list_files_recursively(remote_folder):
            os.makedirs(local_folder / folder, exist_ok=True)
    else:
        return logger.error("Incorrect drive type specified!")

    logger.info(f'Set drive type to {drive_type}')
    logger.info(f'Remote folder "{remote_folder}" found.')
    scanner = LocalFolderScanner(local_folder, on_find(local_folder, remote_folder, drive_api, clear_downloads))
    logger.info(f'Start scanning "{local_folder}".')
    scanner.scanning()


if __name__ == '__main__':
    main()
