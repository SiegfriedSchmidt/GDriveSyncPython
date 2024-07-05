import os
from pathlib import Path

local_folder_path = Path(os.environ.get("LOCAL_FOLDER_PATH", "./folder_sync"))
auth_key_path = Path(os.environ.get("AUTH_KEY_PATH", "./auth/key.json"))
remote_folder_name = os.environ.get("REMOTE_FOLDER_NAME", "from_server")
