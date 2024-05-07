from ..tools.router import Router
from pyrogram import filters, Client
from pyrogram.errors import FloodWait
from pyrogram.types import Message
from pyrogram.enums import ParseMode
from meval import meval
from asyncio import sleep
from logging import getLogger
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
    piston_code = await piston.execute(parse_code)
    input_msg = (
        '**Input:**\n'
        + f'```{parse_code.language}\n'
        + f'{parse_code.code}\n'
        + f'```'
    )
    output_msg = (
        '**Output:**\n'
        + '```output\n'
        + f'{piston_code.output}\n'
        + '```'
    )
    ready_msg = input_msg + '\n\n' + output_msg
    await msg.edit(ready_msg)


@intrp_router.message(
    filters.me
    & (
        filters.command('пу', prefixes='.')
        | filters.command('py', prefixes='.')
    )
)
async def exec_python_code(msg: Message, piston, client, redis):
    code = '\n'.join(msg.text.split('\n')[1:])
    res = await meval(
        globs=globals(), **locals(), intrp_router=intrp_router
    )
    from_terminal = ''
    input_msg = '**Input:**\n' + f'```python\n' + f'{code}\n' + f'```'
    output_msg = '**Output:**\n' + '```output\n' + f'{res}\n' + '```'
    if bool(from_terminal):
        from_terminal_msg = (
            '**From terminal:**\n'
            + '```output\n'
            + f'{from_terminal}\n'
            + '```'
        )
    else:
        from_terminal_msg = ''
    ready_msg = (
        input_msg + '\n\n' + output_msg + '\n\n' + from_terminal_msg
    )
    await msg.edit(ready_msg)
