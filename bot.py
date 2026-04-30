import asyncio
import logging
from pathlib import Path

import betterlogging as bl
from pyrogram import Client, idle
from pyrogram.enums import ParseMode
from pyrogram.types import User
from src.config import (
    Config,
    get_config,
    RuntimeSettings,
    get_redis_engine,
)
from src.services.acl import init_acl
from src.core.dispatcher import Dispatcher
from src.services.code_pars.piston import PistonClient
from src.services.agentic import AgenticRuntime
from src.services.codex import CodexClient
from src.services.crypto import CryptoService
from src.services.mermaid import MermaidService
from src.services.quote import QuoteService
from src.services.weather import WeatherService
from src.bot import routers


ROOT_DIR = Path(__file__).resolve().parent
SESSION_NAME = 'userbot'
SESSION_FILE = ROOT_DIR / f'{SESSION_NAME}.session'


def setup_logging() -> None:
    log_level = logging.INFO
    bl.basic_colorized_config(level=log_level)

    logging.basicConfig(
        level=logging.INFO,
        format='%(filename)s:%(lineno)d #%(levelname)-8s [%(asctime)s] - %(name)s - %(message)s',
    )
    logger = logging.getLogger(__name__)
    logger.info('Starting bot')


def create_client(config: Config) -> Client:
    return Client(
        name=SESSION_NAME,
        api_id=config.userbot.api_id,
        api_hash=config.userbot.api_hash,
        parse_mode=ParseMode.MARKDOWN,
        workdir=ROOT_DIR,
    )


def build_runtime(config: Config):
    redis = get_redis_engine(config.redis)
    runtime_settings = RuntimeSettings(redis)
    codex = CodexClient(redis=redis)
    agentic = AgenticRuntime(
        redis=redis,
        settings=config.agentic,
        ollama_settings=config.ollama,
    )
    init_acl(redis, agentic.storage.session_factory)
    client = create_client(config)
    dispatcher = Dispatcher(
        client=client,
        runtime_settings=runtime_settings,
        routers=routers,
        redis=redis,
        agentic=agentic,
        piston=PistonClient(),
        codex=codex,
        weather=WeatherService(),
        crypto=CryptoService(),
        quote=QuoteService(),
        mermaid=MermaidService(),
    )
    return client, redis, dispatcher, agentic


async def _run_async(
    client: Client,
    redis,
    dispatcher: Dispatcher,
    agentic: AgenticRuntime,
) -> None:
    client.loop = asyncio.get_running_loop()
    await agentic.start()
    await dispatcher.runtime_settings.load()
    dispatcher.update_runtime_settings()
    dispatcher.register_routers()
    await client.start()
    try:
        await idle()
    finally:
        await client.stop()
        await agentic.close()
        await redis.aclose()
        await _cancel_pending_tasks()


async def _cancel_pending_tasks() -> None:
    current = asyncio.current_task()
    pending = [
        t
        for t in asyncio.all_tasks()
        if t is not current and not t.done()
    ]
    for task in pending:
        task.cancel()
    if pending:
        await asyncio.gather(*pending, return_exceptions=True)


def run_bot() -> None:
    setup_logging()
    ensure_session_exists()
    config = get_config()
    client, redis, dispatcher, agentic = build_runtime(config)
    asyncio.run(_run_async(client, redis, dispatcher, agentic))


def init_session() -> User:
    setup_logging()
    config = get_config()
    with create_client(config) as client:
        return client.get_me()


def ensure_session_exists() -> None:
    if SESSION_FILE.exists():
        return
    raise RuntimeError(
        'Telegram session file was not found. '
        'Run `uv run userbot session-init` on the host first. '
        f'Expected file: {SESSION_FILE}'
    )


def main() -> None:
    run_bot()


if __name__ == '__main__':
    try:
        main()
    except (KeyboardInterrupt, SystemExit):
        logging.error('Бот був вимкнений!')
