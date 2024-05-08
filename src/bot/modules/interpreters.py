from pyrogram import filters, Client
from pyrogram.errors import FloodWait
from pyrogram.types import Message
from pyrogram.enums import ParseMode
from meval import meval
from asyncio import sleep
from logging import getLogger
from time import process_time
from redis.asyncio import Redis
from ..tools.router import Router
from ..tools import utils
from ...services.code_pars.piston import PistonClient
from ...services.code_pars.base import ParseCode


intrp_router = Router('intrp')
intrp_router.router_filters = filters.me


@intrp_router.message(
    filters.command('код', prefixes='.')
    | filters.command('code', prefixes='.')
)
async def exec_code(msg: Message, piston: PistonClient, redis: Redis):
    parse_code = ParseCode.parse_tg_msg(utils.get_msg_text(msg))
    start_process_time = process_time()
    piston_code = await piston.execute(parse_code)
    end_process_time = process_time()
    utils.exec_commands(parse_code.commands)
    ready_msg = utils.get_ready_msg(
        utils.get_input_msg(parse_code.language, parse_code.code),
        utils.get_output_msg(piston_code.output),
        utils.get_process_time_msg(
            start_process_time, end_process_time
        ),
    )
    await msg.edit(ready_msg, parse_mode=ParseMode.HTML)


@intrp_router.message(
    filters.command('пу', prefixes='.')
    | filters.command('py', prefixes='.')
)
async def exec_python_code(
    msg: Message, redis: Redis, piston, client
):
    parse_code = ParseCode.parse_tg_msg(
        utils.get_msg_text(msg), 'python'
    )
    start_process_time = process_time()
    res = await meval(
        globs=globals(),
        **locals(),
        intrp_router=intrp_router,
        code=parse_code.code,
    )
    end_process_time = process_time()
    from_terminal = utils.get_terminal_output()
    utils.exec_commands(parse_code.commands)
    ready_msg = utils.get_ready_msg(
        utils.get_input_msg('python', parse_code.code),
        utils.get_output_msg(res),
        utils.get_from_terminal_msg(from_terminal),
        utils.get_process_time_msg(
            start_process_time, end_process_time
        ),
    )
    await msg.edit(ready_msg, parse_mode=ParseMode.HTML)
