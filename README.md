# How to start
Before start, we need to get key.json for a service account in google api:

*https://developers.google.com/drive/api/quickstart/python*

### Docker compose
#### Environment
- LOCAL_FOLDER_PATH  --- path to folder to sync
- AUTH_KEY_PATH      --- path to key.json
- REMOTE_FOLDER_NAME --- google drive folder name

#### Volumes
- ./folder_sync:/app/folder_sync:ro --- path to folder to sync
- ./auth:/app/auth:ro               --- path to auth folder with key.json file

```yaml
services:
  gdrivesync:
    #platform: linux/amd64
    build: .
    image: siegfriedschmidt/gdrivesync
    container_name: gdrivesync
    environment:
      - LOCAL_FOLDER_PATH=/app/folder_sync
      - AUTH_KEY_PATH=/app/auth/key.json
      - REMOTE_FOLDER_NAME=from_server
    volumes:
      - ./folder_sync:/app/folder_sync:ro
      - ./auth:/app/auth:ro

    restart: "unless-stopped"
```

```bash
$ docker compose up -d
```
