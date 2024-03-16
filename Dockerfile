FROM python:3.10

ENV PYTHONUNBUFFERED=1

LABEL maintainer="https://github.com/CBoYXD" version="1.0.0"

WORKDIR /usr/src/userbot

RUN apt update && apt upgrade -y

COPY . /usr/src/userbot

RUN pip install --upgrade pip && \
    pip install --requirement requirements.txt

CMD python3 bot.py