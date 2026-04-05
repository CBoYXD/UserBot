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

### 4. Enjoy using the userbot
