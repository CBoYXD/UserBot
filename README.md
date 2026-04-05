# Steps, to run UserBot at localhost

This project uses `kurigram` as the Telegram client library.
Kurigram exposes the `pyrogram` import namespace, so source imports stay
as `from pyrogram ...`.

### 1. Clone this repository

```bash
git clone https://github.com/CBoYXD/UserBot.git
```

### 2. Start project with [docker compose](https://docs.docker.com/compose/)

1) [Install Docker](https://docs.docker.com/engine/install/) (if not already installed)
2) Start Docker
3) Create `.env` from `example.env`
4) Start Redis
5) Create Telegram session
6) Run the bot

```bash
uv sync
uv run python manage.py redis-up
uv run python manage.py session-init
uv run python manage.py run
```

Local CLI expects Redis on `127.0.0.1:${REDIS__PORT}`.
`manage.py redis-up` publishes that port from Docker automatically.

For the full Docker stack:

```bash
uv run python manage.py up
```

### 3. Connect Codex OAuth

1) Send `.codexlogin` in Telegram
2) Open the URL and sign in with ChatGPT/Codex
3) Copy the full redirect URL from the browser
4) Send `.codexauth <redirect_url>`

### 4. Configure AI settings in Telegram

1) Check current settings with `.aimodel`
2) Set the model with `.codexmodel <model>`
3) Set reasoning effort with `.codexeffort <minimal|low|medium|high|xhigh>`
4) Reset both values to built-in defaults with `.codexreset`

Model and effort are stored in Redis, not in `.env`.

### 5. Enjoy using the userbot
