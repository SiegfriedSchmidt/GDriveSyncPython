import os
import sys
import time
import logging
import colorama

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload
from pprint import pprint
from pathlib import Path
from typing import Tuple


class CustomFormatter(logging.Formatter):
    format = "%(asctime)s - %(levelname)s - %(message)s (%(filename)s:%(lineno)d)"

    FORMATS = {
        logging.DEBUG: colorama.Fore.LIGHTWHITE_EX + format + colorama.Fore.RESET,
        logging.INFO: colorama.Fore.LIGHTWHITE_EX + format + colorama.Fore.RESET,
        logging.WARNING: colorama.Fore.YELLOW + format + colorama.Fore.RESET,
        logging.ERROR: colorama.Fore.RED + format + colorama.Fore.RESET,
        logging.CRITICAL: colorama.Fore.LIGHTRED_EX + format + colorama.Fore.RESET
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt, "%Y-%m-%d %H:%M:%S")
        return formatter.format(record)


def createLogger():
    colorama.init()

    logger = logging.getLogger("My_app")
    logger.setLevel(logging.DEBUG)

    # create console handler with a higher log level
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)

    ch.setFormatter(CustomFormatter())

    logger.addHandler(ch)
    return logger


class GoogleApi:
    SCOPES = ['https://www.googleapis.com/auth/drive']

    def __init__(self):
        self.creds = self.get_cred('auth/credentials.json', 'auth/token.json')

    @staticmethod
    def get_cred(credentials_path, token_path):
        creds = None
        if os.path.exists(token_path):
            creds = Credentials.from_authorized_user_file(token_path, GoogleApi.SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                assert os.path.exists(credentials_path), "Credentials.json not found!"
                flow = InstalledAppFlow.from_client_secrets_file(credentials_path, GoogleApi.SCOPES)
                creds = flow.run_local_server(port=0)

            with open(token_path, 'w') as token:
                token.write(creds.to_json())
        return creds

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

    def show_folder_content(self, folder_id: str):
        return self.find_files_by_query(f"'{folder_id}' in parents")

    def upload_files(self, files: list):
        with build("drive", "v3", credentials=self.creds) as service:
            for file_path, name, folder_id in files:
                file_metadata = {
                    'name': name,
                    'parents': [folder_id]
                }
                media = MediaFileUpload(file_path, resumable=True)
                r = service.files().create(body=file_metadata, media_body=media, fields='id, name').execute()
                yield r.get('id'), r.get('name')

        return


class LocalFolderScanner:
    def __init__(self, folder_path, logger, on_find_new_files: callable):
        self.folder_path = folder_path
        self.on_find_new_files = on_find_new_files
        self.logger: logging.Logger = logger

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
            self.logger.info("Aborted.")


class MyError(BaseException):
    pass


def on_find(sync_folder: Path, folder_id: str, gapi: GoogleApi, logger: logging.Logger):
    def wrapped(new_files: set[str]):
        logger.info(f'Find new files: {new_files}')
        folder_content = set(map(lambda a: a.get('name'), gapi.show_folder_content(folder_id)))
        diff = new_files - folder_content
        if len(diff) > 0:
            logger.info(f'Files not on the disk: {diff}')
            logger.info(f'Start uploading...')
            files_to_upload = [(sync_folder / name, name, folder_id) for name in diff]
            for file_id, file_name in gapi.upload_files(files_to_upload):
                logger.info(f'"{file_name}" has been uploaded')
            logger.info(f'Uploading finished')
        else:
            logger.info(f'All new files on disk')

    return wrapped


def parse_argv() -> Tuple[str, str]:
    argv = sys.argv
    if len(argv) != 3:
        raise MyError(f'Two arguments must be provided! (local_folder_path remote_folder_name)')

    if not os.path.isdir(argv[1]):
        raise MyError(f'"{argv[1]}" is not a folder!')

    return argv[1], argv[2]


def get_folder_id(gapi: GoogleApi, remote_folder_name):
    folders = gapi.find_file_id_by_name(remote_folder_name)
    if len(folders) == 0:
        raise MyError(f'Remote folder "{remote_folder_name}" not found!')

    if len(folders) > 1:
        raise MyError(f'Several files were found with the same name "{remote_folder_name}"!')

    return folders[0]


def main():
    logger = createLogger()
    gapi = GoogleApi()

    try:
        local_folder_path, remote_folder_name = parse_argv()
        remote_folder_id = get_folder_id(gapi, remote_folder_name)
    except MyError as error:
        logger.error(error)
        exit()

    local_folder_path = Path(local_folder_path)
    logger.info(f'Set local folder as "{local_folder_path}" and remote folder as "{remote_folder_name}"')

    scanner = LocalFolderScanner(local_folder_path, logger, on_find(local_folder_path, remote_folder_id, gapi, logger))
    scanner.scanning()


if __name__ == '__main__':
    main()
