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
5) OAuth state is stored in Redis under `auth:codex`

### 4. Configure AI settings in Telegram

1) Check current settings with `.aimodel`
2) Set the model with `.codexmodel <model>`
3) Set reasoning effort with `.codexeffort <minimal|low|medium|high|xhigh>`
4) Reset both values to built-in defaults with `.codexreset`

Model and effort are stored in Redis, not in `.env`.
Runtime settings are stored in Redis under `settings:runtime`.

AI commands such as `.ai`, `.chat`, `.tldr`, and `.tr` use Codex
first when OAuth is connected. If Codex is not available or the call
fails, they fall back to the configured local Ollama chat model. The
translation fallback looks for a local `translategemma` model first.

### 5. Local Ollama agent

Agentic memory and replies use only local Ollama. There is no Codex or
OpenAI fallback for this path.

1) Install and start Ollama on the host.
2) Pull a local chat model, for example `ollama pull qwen3:8b`.
3) Set `OLLAMA__BASE_URL` and `OLLAMA__CHAT_MODEL` in `.env`.
4) Start the bot.

When running the bot inside Docker on Windows, `OLLAMA__BASE_URL`
usually needs to point at the host, for example
`http://host.docker.internal:11434`.

Commands:

```text
.agent status
.agent on
.agent off
.agent model [name]
.agent ask <prompt>
.agent memory <query>
.agent context [N]
.agent trace [N|here N|trace_id]
.agent autoreply on|off
```

The agent stores durable local memory in SQLite at
`AGENTIC__DB_PATH` and keeps only non-content hot state in Redis:
settings, ids, health cache, and cooldowns. Embeddings are disabled by
default.

`.agent ask` and `.agent memory` run a local Ollama read-only tool
loop over indexed Telegram data. Available tools can list indexed
chats, read recent messages, search message text, fetch one message,
read context around a message, inspect chat stats, and read messages
from one user. Auto-reply uses the same tool loop, but it is restricted
to the current chat.

Use `.agent trace` to inspect what the local model did: loop starts,
model responses, requested tools, tool results, errors, and final
answers are written to local SQLite trace events.

### 6. Run code in Telegram

1) Execute code in Piston with `.run <language> <code>`
2) Multi-line also works as `.run <language>` on the first line and code below it
3) Reply with code to `.run <language>` if you do not want to paste it inline
4) Execute local Python with `.py <code>`, `.py` plus code on the next lines, or reply with `.py`
5) Save snippets with `.code save <name> <language> <code>`
6) Run snippets with `.code run <name>`
7) Show snippet source with `.code show <name>`
8) List snippets with `.code ls`
9) Delete snippets with `.code rm <name>`

Notes and code snippets are stored locally in SQLite at
`data/userbot.sqlite3`, not in Redis.

### 7. Enjoy using the userbot
