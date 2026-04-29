import io
import sys
from time import process_time

from meval import meval
from pyrogram import filters
from pyrogram.enums import ParseMode
from pyrogram.types import Message

from src.bot.modules.interpreters.parsing import extract_python_code
from src.bot.modules.interpreters.router import intrp_router
from src.bot.tools import utils


@intrp_router.message(filters.command('py', prefixes='.'))
async def exec_python_code(msg: Message):
    try:
        code = extract_python_code(msg)

        old_stdout = sys.stdout
        sys.stdout = captured = io.StringIO()

        start = process_time()
        try:
            res = await meval(
                code,
                globs=globals(),
                msg=msg,
                intrp_router=intrp_router,
            )
        finally:
            sys.stdout = old_stdout

        end = process_time()
        terminal_output = captured.getvalue()

        ready_msg = utils.get_ready_msg(
            utils.get_input_msg('python', code),
            utils.get_output_msg(res),
            utils.get_from_terminal_msg(terminal_output),
            utils.get_process_time_msg(start, end),
        )
        ready_text = utils.get_ready_text(
            utils.get_input_text('python', code),
            utils.get_output_text(res),
            utils.get_from_terminal_text(terminal_output),
            utils.get_process_time_text(start, end),
        )
        await utils.edit_or_send_as_text_file(
            msg,
            ready_msg,
            file_text=ready_text,
            filename=f'python-output-{msg.id}.txt',
        )
    except Exception as e:
        await msg.edit(
            f'<b>Error:</b> <code>{e}</code>',
            parse_mode=ParseMode.HTML,
        )
