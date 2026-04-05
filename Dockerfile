FROM python:3.10

ENV PYTHONUNBUFFERED=1
ENV UV_PROJECT_ENVIRONMENT=/opt/venv
ENV UV_LINK_MODE=copy
ENV PATH="/opt/venv/bin:$PATH"

LABEL maintainer="https://github.com/CBoYXD" version="1.0.0"

WORKDIR /usr/src/userbot

RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir --upgrade pip uv

COPY pyproject.toml uv.lock README.md /usr/src/userbot/
RUN uv sync --frozen --no-dev

COPY bot.py /usr/src/userbot/
COPY manage.py /usr/src/userbot/
COPY src /usr/src/userbot/src

CMD ["uv", "run", "python", "manage.py", "run"]
