import os
import time
import json

from google.oauth2 import service_account
from googleapiclient.http import MediaFileUpload
from googleapiclient.discovery import build
from pathlib import Path

from typing import Iterable, Generator, Tuple
from abc import ABC, abstractmethod
from synology_api import filestation

from init import remote_folder_name, local_folder_path, auth_key_path, drive_type, clear_downloads
from libs.logger import logger


class Drive(ABC):
    @abstractmethod
    def show_folder_content(self, folder: str) -> set[str]:
        pass

    @abstractmethod
    def upload_files(self, files: Iterable[Tuple[Path, str, str]]) -> Generator[Tuple[str, str], None, None]:
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

    def show_folder_content(self, folder: str) -> set[str]:
        with self.file_station as fs:
            return set(map(lambda a: a.get('name'), fs.get_file_list(folder)['data']['files']))

    def upload_files(self, files: Iterable[Tuple[Path, str, str]]) -> Generator[Tuple[str, str], None, None]:
        with self.file_station as fs:
            for file_path, name, folder in files:
                rs = fs.upload_file(folder, str(file_path), progress_bar=False, verify=True)
                yield rs['data']['file'], file_path


class GoogleDrive(Drive):
    SCOPES = ['https://www.googleapis.com/auth/drive']

    def __init__(self, key_path):
        self.creds = self.get_cred(key_path)

    @staticmethod
    def get_cred(service_account_json_key):
        return service_account.Credentials.from_service_account_file(filename=service_account_json_key,
                                                                     scopes=GoogleDrive.SCOPES)

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

    def show_folder_content(self, folder: str) -> set[str]:
        return set(map(lambda a: a.get('name'), self.find_files_by_query(f"'{folder}' in parents")))

    def upload_files(self, files: Iterable[Tuple[Path, str, str]]) -> Generator[Tuple[str, str], None, None]:
        with build("drive", "v3", credentials=self.creds) as service:
            for file_path, name, folder_id in files:
                file_metadata = {
                    'name': name,
                    'parents': [folder_id]
                }
                media = MediaFileUpload(file_path, resumable=True)
                r = service.files().create(body=file_metadata, media_body=media, fields='id, name').execute()
                yield r.get('name'), file_path

        return


class LocalFolderScanner:
    def __init__(self, folder_path, on_find_new_files: callable):
        self.folder_path = folder_path
        self.on_find_new_files = on_find_new_files

    def scanning(self, interval=3):
        files = set()
        try:
            while True:
                cur_files = set(os.listdir(self.folder_path))
                new_files = cur_files - files
                if len(new_files) > 0:
                    self.on_find_new_files(new_files)
                    files = cur_files
                time.sleep(interval)
        except KeyboardInterrupt:
            logger.info("Aborted.")


class MyError(BaseException):
    pass


def on_find(sync_folder: Path, remote_folder: str, drive_api: Drive):
    def wrapped(new_files: set[str]):
        logger.info(f'Find new files: {new_files}')
        folder_content = drive_api.show_folder_content(remote_folder)
        diff = new_files - folder_content
        if len(diff) > 0:
            logger.info(f'Files not on the disk: {diff}')
            logger.info(f'Start uploading...')
            files_to_upload = [(sync_folder / name, name, remote_folder) for name in diff]
            for filename, filepath in drive_api.upload_files(files_to_upload):
                logger.info(f'"{filename}" has been uploaded')
                if clear_downloads:
                    os.remove(filepath)
            logger.info(f'Uploading finished')
        else:
            logger.info(f'All new files on disk')

    return wrapped


def main():
    if drive_type == 'GOOGLE':
        drive_api = GoogleDrive(auth_key_path)

        try:
            remote_folder = drive_api.get_folder(remote_folder_name)
        except MyError as error:
            return logger.error(error)

        logger.info('Set drive type to GOOGLE')

    elif drive_type == 'SYNOLOGY':
        drive_api = SynologyDrive(auth_key_path)
        remote_folder = remote_folder_name

        logger.info('Set drive type to SYNOLOGY')
    else:
        return logger.error("Incorrect drive type specified!")

    logger.info(f'Remote folder with name "{remote_folder_name}" found')
    scanner = LocalFolderScanner(local_folder_path, on_find(local_folder_path, remote_folder, drive_api))
    logger.info(f'Start scanning')
    scanner.scanning()


if __name__ == '__main__':
    main()
