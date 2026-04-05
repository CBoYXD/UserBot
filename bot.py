import logging
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
        name='userbot',
        api_id=config.userbot.api_id,
        api_hash=config.userbot.api_hash,
        parse_mode=ParseMode.MARKDOWN,
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
    config = get_config()
    dispatcher = build_dispatcher(config)
    dispatcher.run()


def init_session() -> User:
    setup_logging()
    config = get_config()
    with create_client(config) as client:
        return client.get_me()


def main() -> None:
    run_bot()


if __name__ == '__main__':
    try:
        main()
    except (KeyboardInterrupt, SystemExit):
        logging.error('Бот був вимкнений!')
