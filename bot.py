import logging
import betterlogging as bl
from pyrogram import Client
from pyrogram.enums import ParseMode
from src.config import (
    get_config,
    RuntimeSettings,
    get_redis_engine,
)
from src.bot.tools.dispatcher import Dispatcher
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


def main() -> None:
    setup_logging()
    config = get_config()
    redis = get_redis_engine(config.redis)
    runtime_settings = RuntimeSettings('.config/settings.json')
    runtime_settings.load()
    client = Client(
        name='userbot',
        api_id=config.userbot.api_id,
        api_hash=config.userbot.api_hash,
        parse_mode=ParseMode.MARKDOWN,
    )
    dp = Dispatcher(
        client=client,
        runtime_settings=runtime_settings,
        routers=routers,
        redis=redis,
    )
    dp.run()


if __name__ == '__main__':
    try:
        main()
    except (KeyboardInterrupt, SystemExit):
        logging.error('Бот був вимкнений!')
