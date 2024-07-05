FROM python:3.10.9-slim
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY requirements.txt /
RUN pip install --no-cache -r /requirements.txt

RUN addgroup --gid 1001 --system app && \
    adduser --no-create-home --shell /bin/false --disabled-password --uid 1001 --system --group app

USER app
STOPSIGNAL SIGINT

COPY . /app
ENTRYPOINT ["python3", "main.py"]
