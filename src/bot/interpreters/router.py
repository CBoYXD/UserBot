import io
import sys
from time import process_time

from meval import meval
from pyrogram.enums import ParseMode
from pyrogram.types import Message
from redis.asyncio import Redis

from src.core import utils
from src.core.acl import cmd
from src.core.router import Router
from src.services.code_pars.piston import PistonClient
from src.bot.interpreters import storage
from src.bot.interpreters.parsing import (
    extract_code_subcommand,
    extract_named_code,
    extract_python_code,
    extract_run_code,
    extract_snippet_name_from_text,
)


intrp_router = Router('intrp')


# ---------- .run ----------

@intrp_router.message(cmd('interpreters', 'run'))
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


# ---------- .py ----------

@intrp_router.message(cmd('interpreters', 'py'))
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


# ---------- .code ----------

def _code_help_text() -> str:
    return (
        'Usage: .code <save|run|show|ls|rm> ...\n'
        '.code save <name> <language> <code>\n'
        '.code run <name>\n'
        '.code show <name>\n'
        '.code ls\n'
        '.code rm <name>'
    )


@intrp_router.message(cmd('interpreters', 'code'))
async def code_command(
    msg: Message,
    piston: PistonClient,
    redis: Redis,
):
    try:
        subcommand, remainder = extract_code_subcommand(msg)
        if subcommand == 'save':
            await _code_save(msg, redis, remainder)
            return
        if subcommand == 'run':
            await _code_run(msg, piston, redis, remainder)
            return
        if subcommand == 'show':
            await _code_show(msg, redis, remainder)
            return
        if subcommand == 'ls':
            await _code_list(msg, redis)
            return
        if subcommand == 'rm':
            await _code_delete(msg, redis, remainder)
            return
        raise ValueError(_code_help_text())
    except Exception as e:
        await msg.edit(
            f'<b>Error:</b> <code>{e}</code>',
            parse_mode=ParseMode.HTML,
        )


async def _code_save(
    msg: Message,
    redis: Redis,
    remainder: str,
) -> None:
    name, parse_code = extract_named_code(msg, remainder)
    await storage.save_snippet(redis, name, parse_code)
    await msg.edit(
        '<b>Saved code</b>\n'
        f'<b>Name:</b> <code>{name}</code>\n'
        f'<b>Language:</b> <code>{parse_code.language}</code>',
        parse_mode=ParseMode.HTML,
    )


async def _code_run(
    msg: Message,
    piston: PistonClient,
    redis: Redis,
    remainder: str,
) -> None:
    name = extract_snippet_name_from_text(remainder)
    parse_code = await storage.load_snippet(redis, name)
    start = process_time()
    result = await piston.execute(parse_code)
    end = process_time()

    ready_msg = utils.get_ready_msg(
        f'<b>Snippet:</b> <code>{name}</code>',
        utils.get_input_msg(
            parse_code.language,
            parse_code.code,
        ),
        utils.get_output_msg(result.output),
        utils.get_process_time_msg(start, end),
    )
    ready_text = utils.get_ready_text(
        f'Snippet: {name}',
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
        filename=f'code-run-{name}-{msg.id}.txt',
    )


async def _code_show(
    msg: Message,
    redis: Redis,
    remainder: str,
) -> None:
    name = extract_snippet_name_from_text(remainder)
    parse_code = await storage.load_snippet(redis, name)
    ready_msg = utils.get_ready_msg(
        f'<b>Snippet:</b> <code>{name}</code>',
        utils.get_input_msg(
            parse_code.language,
            parse_code.code,
        ),
    )
    ready_text = utils.get_ready_text(
        f'Snippet: {name}',
        utils.get_input_text(
            parse_code.language,
            parse_code.code,
        ),
    )
    await utils.edit_or_send_as_text_file(
        msg,
        ready_msg,
        file_text=ready_text,
        filename=f'code-show-{name}-{msg.id}.txt',
    )


async def _code_list(msg: Message, redis: Redis) -> None:
    snippets = await storage.list_snippets(redis)
    if not snippets:
        await msg.edit(
            '<b>Saved code:</b> empty.',
            parse_mode=ParseMode.HTML,
        )
        return

    lines = [
        f'<code>{name}</code> <i>({language})</i>'
        for name, language in snippets
    ]
    ready_msg = '<b>Saved code</b>\n' + '\n'.join(lines)
    ready_text = utils.get_ready_text(
        'Saved code',
        '\n'.join(
            f'{name} ({language})'
            for name, language in snippets
        ),
    )
    await utils.edit_or_send_as_text_file(
        msg,
        ready_msg,
        file_text=ready_text,
        filename=f'code-list-{msg.id}.txt',
    )


async def _code_delete(
    msg: Message,
    redis: Redis,
    remainder: str,
) -> None:
    name = extract_snippet_name_from_text(remainder)
    if not await storage.delete_snippet(redis, name):
        raise ValueError(
            f'Snippet "{name}" was not found.'
        )
    await msg.edit(
        '<b>Deleted code</b>\n'
        f'<b>Name:</b> <code>{name}</code>',
        parse_mode=ParseMode.HTML,
    )
