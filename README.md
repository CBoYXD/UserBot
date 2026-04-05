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
4) Run project

```bash
docker compose up
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
