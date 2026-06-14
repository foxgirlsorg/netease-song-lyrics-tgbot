FROM python:3.12.7-alpine
LABEL authors="netease-bot"

WORKDIR /usr/local/app

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

RUN apk add --no-cache \
    gcc \
    musl-dev \
    libffi-dev \
    openssl-dev

COPY requirements.txt ./

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

STOPSIGNAL SIGINT

ENTRYPOINT ["python", "main.py"]