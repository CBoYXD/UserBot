import io
import sys
from time import process_time

from meval import meval
from pyrogram import Client, filters
from pyrogram.enums import ParseMode
from pyrogram.types import Message
from redis.asyncio import Redis

from src.bot.tools import utils
from src.bot.tools.router import Router
from src.services.code_pars.base import (
    ParseCode,
    ParseCommands,
)
from src.services.code_pars.piston import PistonClient


intrp_router = Router('intrp')
intrp_router.router_filters = filters.me


async def _prepare_code(
    msg: Message,
    redis: Redis,
    default_language: str | None = None,
) -> tuple[ParseCommands, str, str]:
    """Extract commands, language, and code from message."""
    my_msg = msg.text
    lines = my_msg.split('\n')
    commands = ParseCommands.parse_tg_msg(lines[0])

    if commands.use_reply and msg.reply_to_message:
        full_text = utils.get_msg_text_with_reply(
            my_msg, msg
        )
        lines = full_text.split('\n')

    code = None
    language = default_language

    if commands.use_file:
        raw: bytes | None = await redis.get(
            commands.kwargs.get('name_of_file', '')
        )
        if raw:
            code = raw.decode('utf-8')
            language = commands.kwargs.get(
                'language', default_language
            )

    if code is None:
        parsed = ParseCode.parse_tg_msg(
            lines[1:], language=default_language
        )
        code = parsed.code
        language = parsed.language

    return commands, language, code


async def _save_if_needed(
    commands: ParseCommands,
    redis: Redis,
    code: str,
) -> None:
    """Save code to Redis if !s flag was used."""
    if (
        commands.save_file
        and not commands.use_file
        and commands.kwargs.get('name_of_file')
    ):
        await redis.set(
            commands.kwargs['name_of_file'], code
        )


@intrp_router.message(
    filters.command('код', prefixes='.')
    | filters.command('code', prefixes='.')
)
async def exec_code(
    msg: Message, piston: PistonClient, redis: Redis
):
    try:
        commands, language, code = await _prepare_code(
            msg, redis
        )
        start = process_time()
        result = await piston.execute(
            ParseCode(language=language, code=code)
        )
        end = process_time()

        await _save_if_needed(commands, redis, code)

        ready_msg = utils.get_ready_msg(
            utils.get_input_msg(language, code),
            utils.get_output_msg(result.output),
            utils.get_process_time_msg(start, end),
        )
        await msg.edit(
            ready_msg, parse_mode=ParseMode.HTML
        )
    except Exception as e:
        await msg.edit(
            f'<b>Error:</b> <code>{e}</code>',
            parse_mode=ParseMode.HTML,
        )


@intrp_router.message(
    filters.command('пу', prefixes='.')
    | filters.command('py', prefixes='.')
)
async def exec_python_code(
    msg: Message, redis: Redis, piston, client
):
    try:
        commands, _, code = await _prepare_code(
            msg, redis, default_language='python'
        )

        # Capture stdout
        old_stdout = sys.stdout
        sys.stdout = captured = io.StringIO()

        start = process_time()
        try:
            res = await meval(
                code,
                globs=globals(),
                **locals(),
                intrp_router=intrp_router,
            )
        finally:
            sys.stdout = old_stdout

        end = process_time()
        terminal_output = captured.getvalue()

        await _save_if_needed(commands, redis, code)

        ready_msg = utils.get_ready_msg(
            utils.get_input_msg('python', code),
            utils.get_output_msg(res),
            utils.get_from_terminal_msg(terminal_output),
            utils.get_process_time_msg(start, end),
        )
        await msg.edit(
            ready_msg, parse_mode=ParseMode.HTML
        )
    except Exception as e:
        await msg.edit(
            f'<b>Error:</b> <code>{e}</code>',
            parse_mode=ParseMode.HTML,
        )
