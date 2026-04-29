from time import process_time

from pyrogram import filters
from pyrogram.enums import ParseMode
from pyrogram.types import Message

from src.bot.modules.interpreters.parsing import extract_run_code
from src.bot.modules.interpreters.router import intrp_router
from src.bot.tools import utils
from src.services.code_pars.piston import PistonClient


@intrp_router.message(filters.command('run', prefixes='.'))
async def exec_code(
    msg: Message,
    piston: PistonClient,
):
    try:
        parse_code = extract_run_code(msg)
        start = process_time()
        result = await piston.execute(parse_code)
        end = process_time()

        ready_msg = utils.get_ready_msg(
            utils.get_input_msg(
                parse_code.language,
                parse_code.code,
            ),
            utils.get_output_msg(result.output),
            utils.get_process_time_msg(start, end),
        )
        ready_text = utils.get_ready_text(
            utils.get_input_text(
                parse_code.language,
                parse_code.code,
            ),
            utils.get_output_text(result.output),
            utils.get_process_time_text(start, end),
        )
        await utils.edit_or_send_as_text_file(
            msg,
            ready_msg,
            file_text=ready_text,
            filename=f'run-output-{msg.id}.txt',
        )
    except Exception as e:
        await msg.edit(
            f'<b>Error:</b> <code>{e}</code>',
            parse_mode=ParseMode.HTML,
        )
