import os
from pathlib import Path
from typing import Literal

drive_type: Literal['GOOGLE', 'SYNOLOGY'] = os.environ.get("DRIVE_TYPE", "GOOGLE")
local_folder_path = Path(os.environ.get("LOCAL_FOLDER_PATH", "./folder_sync"))
auth_key_path = Path(os.environ.get("AUTH_KEY_PATH", "./auth/key.json"))
remote_folder_name = os.environ.get("REMOTE_FOLDER_NAME", "from_server")
clear_downloads = int(os.environ.get("CLEAR_DOWNLOADS", "1"))
