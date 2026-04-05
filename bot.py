import logging
from pathlib import Path

import betterlogging as bl
from pyrogram import Client
from pyrogram.enums import ParseMode
from pyrogram.types import User
from src.config import (
    Config,
    get_config,
    RuntimeSettings,
    get_redis_engine,
)
from src.bot.tools.dispatcher import Dispatcher
from src.services.code_pars.piston import PistonClient
from src.services.codex import CodexClient
from src.bot.modules import routers


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


def build_dispatcher(config: Config) -> Dispatcher:
    redis = get_redis_engine(config.redis)
    runtime_settings = RuntimeSettings('.config/settings.json')
    runtime_settings.load()
    codex = CodexClient(
        credentials_path=config.codex.credentials_path,
    )
    return Dispatcher(
        client=create_client(config),
        runtime_settings=runtime_settings,
        routers=routers,
        redis=redis,
        piston=PistonClient(),
        codex=codex,
    )


def run_bot() -> None:
    setup_logging()
    ensure_session_exists()
    config = get_config()
    dispatcher = build_dispatcher(config)
    dispatcher.run()


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
