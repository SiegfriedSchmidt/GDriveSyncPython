import os
from pathlib import Path
from typing import Literal

drive_type: Literal['GOOGLE', 'SYNOLOGY'] = os.environ.get("DRIVE_TYPE", "SYNOLOGY")
local_folder = Path(os.environ.get("LOCAL_FOLDER", "./folder_sync"))
auth_key_path = Path(os.environ.get("AUTH_KEY_PATH", "./auth/synology.json"))
remote_folder = os.environ.get("REMOTE_FOLDER", "/home/Test")
clear_downloads = int(os.environ.get("CLEAR_DOWNLOADS", "1"))
