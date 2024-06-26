FROM python:3.10.9-alpine
COPY . /app
WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=100 \
    BROWSER=/bin/echo \
    REMOTE_FOLDER_NAME='defaultfoldername'
RUN pip install -r requirements.txt
ENTRYPOINT python3 main.py folder_sync $REMOTE_FOLDER_NAME
