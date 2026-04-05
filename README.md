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
docker compose up -d redis_db
uv run userbot session-init
uv run userbot run
```

Local CLI expects Redis on `127.0.0.1:${REDIS__PORT}`.
`docker compose up -d redis_db` publishes that port from Docker.
`session-init` must be done on the host before `docker compose up --build`,
so `userbot.session` exists in the project root.

For the full Docker stack:

```bash
docker compose up --build
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

### 5. Run code in Telegram

1) Execute code in Piston with `.run <language> <code>`
2) Multi-line also works as `.run <language>` on the first line and code below it
3) Reply with code to `.run <language>` if you do not want to paste it inline
4) Execute local Python with `.py <code>`, `.py` plus code on the next lines, or reply with `.py`
5) Save snippets with `.code save <name> <language> <code>`
6) Run snippets with `.code run <name>`
7) Show snippet source with `.code show <name>`
8) List snippets with `.code ls`
9) Delete snippets with `.code rm <name>`

### 6. Enjoy using the userbot
