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
from ...services.code_pars.base import ParseCode, ParseCommands


intrp_router = Router('intrp')
intrp_router.router_filters = filters.me


@intrp_router.message(
    filters.command('код', prefixes='.')
    | filters.command('code', prefixes='.')
)
async def exec_code(msg: Message, piston: PistonClient, redis: Redis):
    my_msg = msg.text
    my_msg_lines = my_msg.split('\n')
    parse_commands = ParseCommands.parse_tg_msg(my_msg_lines[0])
    if parse_commands.use_reply:
        message_with_reply = utils.get_msg_text_with_reply(
            my_msg, msg
        )
        msg_text_lines = message_with_reply.split('\n')
    else:
        msg_text_lines = my_msg_lines
    code = None
    language = None
    if parse_commands:
        if parse_commands.use_file:
            res_from_db: bytes = await redis.get(
                parse_commands.kwargs['name_of_file']
            )
            code: str = res_from_db.decode('utf-8')
            language = parse_commands.kwargs['language']
    if code is None:
        parse_code = ParseCode.parse_tg_msg(msg_text_lines[1:])
        code = parse_code.code
        language = parse_code.language
    start_process_time = process_time()
    piston_code = await piston.execute(
        ParseCode(language=language, code=code)
    )
    end_process_time = process_time()
    if parse_commands:
        if not parse_commands.use_file and parse_commands.save_file:
            await redis.set(
                parse_commands.kwargs['name_of_file'], code
            )
    ready_msg = utils.get_ready_msg(
        utils.get_input_msg(language, code),
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
    my_msg = msg.text
    my_msg_lines = my_msg.split('\n')
    parse_commands = ParseCommands.parse_tg_msg(my_msg_lines[0])
    if parse_commands.use_reply:
        message_with_reply = utils.get_msg_text_with_reply(
            my_msg, msg
        )
        msg_text_lines = message_with_reply.split('\n')
    else:
        msg_text_lines = my_msg_lines
    code = None
    if parse_commands:
        if parse_commands.use_file:
            res_from_db: bytes = await redis.get(
                parse_commands.kwargs['name_of_file']
            )
            code: str = res_from_db.decode('utf-8')
    if code is None:
        parse_code = ParseCode.parse_tg_msg(
            msg_text_lines[1:], language='python'
        )
        code = parse_code.code
    start_process_time = process_time()
    res = await meval(
        globs=globals(),
        **locals(),
        intrp_router=intrp_router,
    )
    end_process_time = process_time()
    from_terminal = utils.get_terminal_output()
    if parse_commands:
        if not parse_commands.use_file and parse_commands.save_file:
            await redis.set(
                parse_commands.kwargs['name_of_file'], code
            )
    ready_msg = utils.get_ready_msg(
        utils.get_input_msg('python', code),
        utils.get_output_msg(res),
        utils.get_from_terminal_msg(from_terminal),
        utils.get_process_time_msg(
            start_process_time, end_process_time
        ),
    )
    await msg.edit(ready_msg, parse_mode=ParseMode.HTML)
