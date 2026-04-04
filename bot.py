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
from src.services.code_pars.piston import PistonClient
from src.services.gemini import GeminiClient
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
    gemini = GeminiClient(
        api_key=config.gemini.api_key,
        model=config.gemini.model,
    )
    dp = Dispatcher(
        client=client,
        runtime_settings=runtime_settings,
        routers=routers,
        redis=redis,
        piston=PistonClient(),
        gemini=gemini,
    )
    dp.run()


if __name__ == '__main__':
    try:
        main()
    except (KeyboardInterrupt, SystemExit):
        logging.error('Бот був вимкнений!')
