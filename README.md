# How to start


Before start, we need to authorize credentials for a desktop application in your google account:

*https://developers.google.com/drive/api/quickstart/python*

```bash
$ git https://github.com/SiegfriedSchmidt/GDriveSyncPython.git
$ cd GDriveSyncPython
$ mkdir auth
# save credentials.json here (auth/credentials.json)
```

### Python venv
```bash
$ python3 -m venv venv
$ source venv/bin/activate
$ python3 main.py local_folder_path remote_folder_name
```


### Docker compose
REMOTE_FOLDER_NAME - name of google drive folder

Also change volume path to local folder

```yaml
version: "3"

services:
  app:
    image: gdrivesync
    container_name: gdrivesync
    environment:
      REMOTE_FOLDER_NAME: defaultfoldername
    volumes:
      - /local/path/folder:/app/folder_sync:ro

    restart: unless-stopped
```

```bash
$ docker build . -t gdrivesync
$ docker compose up -d
```
