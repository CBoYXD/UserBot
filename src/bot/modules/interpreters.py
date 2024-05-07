from ..tools.router import Router
from pyrogram import filters, Client
from pyrogram.errors import FloodWait
from pyrogram.types import Message
from pyrogram.enums import ParseMode
from meval import meval
from asyncio import sleep
from logging import getLogger
from time import process_time
from src.services.code_pars.piston import (
    PistonClient,
    ParseCodeForPiston,
)


intrp_router = Router('intrp')


@intrp_router.message(
    filters.me
    & (
        filters.command('код', prefixes='.')
        | filters.command('code', prefixes='.')
    )
)
async def exec_code(msg: Message, piston: PistonClient):
    parse_code = ParseCodeForPiston.parse_tg_msg(msg.text)
    start_process_time = process_time()
    piston_code = await piston.execute(parse_code)
    process_time_msg = (
        f'<b>Process time: {process_time()-start_process_time}</b>'
    )
    input_msg = (
        '<b>Input:</b>'
        + '\n'
        + f'<pre language="{parse_code.language}">{parse_code.code}</pre>'
    )
    output_msg = (
        '<b>Output:</b>\n'
        + f'<pre language="output">{piston_code.output}</pre>'
    )
    ready_msg = (
        input_msg + '\n\n' + output_msg + '\n\n' + process_time_msg
    )
    await msg.edit(ready_msg, parse_mode=ParseMode.HTML)


@intrp_router.message(
    filters.me
    & (
        filters.command('пу', prefixes='.')
        | filters.command('py', prefixes='.')
    )
)
async def exec_python_code(msg: Message, piston, client, redis):
    code = '\n'.join(msg.text.split('\n')[1:])
    start_process_time = process_time()
    res = await meval(
        globs=globals(), **locals(), intrp_router=intrp_router
    )
    process_time_msg = (
        f'<b>Process time: {process_time()-start_process_time}</b>'
    )
    from_terminal = ''
    input_msg = (
        '<b>Input:</b>'
        + '\n'
        + f'<pre language="python">{code}</pre>'
    )
    output_msg = (
        '<b>Output:</b>\n' + f'<pre language="output">{res}</pre>'
    )
    if bool(from_terminal):
        from_terminal_msg = (
            '<b>Output:</b>\n'
            + f'<pre language="output">{from_terminal}</pre>'
        )
    else:
        from_terminal_msg = ''
    ready_msg = (
        input_msg
        + '\n\n'
        + output_msg
        + from_terminal_msg
        + '\n\n'
        + process_time_msg
    )
    await msg.edit(ready_msg, parse_mode=ParseMode.HTML)
