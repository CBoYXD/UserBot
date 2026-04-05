import io
import json
import re
import sys
from time import process_time

from meval import meval
from pyrogram import filters
from pyrogram.enums import ParseMode
from pyrogram.types import Message
from redis.asyncio import Redis

from src.bot.tools import utils
from src.bot.tools.router import Router
from src.services.code_pars.base import ParseCode
from src.services.code_pars.piston import PistonClient


intrp_router = Router('intrp')
intrp_router.router_filters = filters.me
CODE_SNIPPETS_KEY = 'storage:code:snippets'
CODE_BLOCK_RE = re.compile(
    r'^```(?P<language>[a-zA-Z0-9_+.#-]+)?\n'
    r'(?P<code>.*)\n```$',
    re.DOTALL,
)


@intrp_router.message(filters.command('run', prefixes='.'))
async def exec_code(
    msg: Message,
    piston: PistonClient,
):
    try:
        parse_code = _extract_run_code(msg)
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
        await msg.edit(
            ready_msg,
            parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        await msg.edit(
            f'<b>Error:</b> <code>{e}</code>',
            parse_mode=ParseMode.HTML,
        )


@intrp_router.message(filters.command('py', prefixes='.'))
async def exec_python_code(msg: Message):
    try:
        code = _extract_python_code(msg)

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

        ready_msg = utils.get_ready_msg(
            utils.get_input_msg('python', code),
            utils.get_output_msg(res),
            utils.get_from_terminal_msg(terminal_output),
            utils.get_process_time_msg(start, end),
        )
        await msg.edit(
            ready_msg,
            parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        await msg.edit(
            f'<b>Error:</b> <code>{e}</code>',
            parse_mode=ParseMode.HTML,
        )


@intrp_router.message(filters.command('code', prefixes='.'))
async def code_command(
    msg: Message,
    piston: PistonClient,
    redis: Redis,
):
    try:
        subcommand, remainder = _extract_code_subcommand(msg)
        if subcommand == 'save':
            await _handle_code_save(
                msg,
                redis,
                remainder,
            )
            return
        if subcommand == 'run':
            await _handle_code_run(
                msg,
                piston,
                redis,
                remainder,
            )
            return
        if subcommand == 'show':
            await _handle_code_show(
                msg,
                redis,
                remainder,
            )
            return
        if subcommand == 'ls':
            await _handle_code_list(msg, redis)
            return
        if subcommand == 'rm':
            await _handle_code_delete(
                msg,
                redis,
                remainder,
            )
            return
        raise ValueError(_code_help_text())
    except Exception as e:
        await msg.edit(
            f'<b>Error:</b> <code>{e}</code>',
            parse_mode=ParseMode.HTML,
        )


def _extract_run_code(msg: Message) -> ParseCode:
    body = _extract_command_body(msg)
    reply_text = _extract_message_text(msg.reply_to_message)

    explicit_language = ''
    code_source = ''

    if body:
        if body.startswith('```'):
            code_source = body
        else:
            parts = body.split(maxsplit=1)
            explicit_language = parts[0].strip().lower()
            if len(parts) > 1:
                code_source = parts[1].strip()

    if not code_source:
        code_source = reply_text

    block_language, code = _unwrap_code_block(code_source)
    language = explicit_language or block_language
    if not language:
        raise ValueError(
            'Usage: .run <language> <code>, '
            '".run <language>\\n<code>", or reply '
            'with code to ".run <language>".'
        )
    if not code:
        raise ValueError('Code is empty.')
    return ParseCode(language=language, code=code)


def _extract_python_code(msg: Message) -> str:
    body = _extract_command_body(msg)
    code_source = body or _extract_message_text(
        msg.reply_to_message
    )
    _, code = _unwrap_code_block(code_source)
    if not code:
        raise ValueError(
            'Usage: .py <code>, ".py\\n<code>", '
            'or reply with code to ".py".'
        )
    return code


def _extract_named_code(
    msg: Message,
    remainder: str,
) -> tuple[str, ParseCode]:
    if not remainder:
        raise ValueError(
            'Usage: .code save <name> <language> <code>.'
        )

    name, _, remainder = remainder.partition(' ')
    name = name.strip().lower()
    if not name:
        raise ValueError('Snippet name is required.')

    explicit_language = ''
    code_source = ''
    remainder = remainder.strip()

    if remainder:
        if remainder.startswith('```'):
            code_source = remainder
        else:
            parts = remainder.split(maxsplit=1)
            explicit_language = parts[0].strip().lower()
            if len(parts) > 1:
                code_source = parts[1].strip()

    if not code_source:
        code_source = _extract_message_text(
            msg.reply_to_message
        )

    block_language, code = _unwrap_code_block(code_source)
    language = explicit_language or block_language
    if not language:
        raise ValueError(
            'Usage: .code save <name> <language> <code>, '
            '".code save <name> <language>\\n<code>", '
            'or reply with code to ".code save <name> <language>".'
        )
    if not code:
        raise ValueError('Code is empty.')
    return name, ParseCode(language=language, code=code)


def _extract_snippet_name(msg: Message) -> str:
    name = _extract_command_body(msg).strip().lower()
    if not name:
        raise ValueError('Snippet name is required.')
    return name


def _extract_snippet_name_from_text(text: str) -> str:
    name = text.strip().lower()
    if not name:
        raise ValueError('Snippet name is required.')
    return name


def _extract_code_subcommand(
    msg: Message,
) -> tuple[str, str]:
    body = _extract_command_body(msg)
    if not body:
        return '', ''
    command, _, remainder = body.partition(' ')
    return command.strip().lower(), remainder.strip()


def _extract_command_body(msg: Message) -> str:
    text = _extract_message_text(msg)
    if not text:
        return ''
    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        return ''
    return parts[1].strip()


def _extract_message_text(msg: Message | None) -> str:
    if msg is None:
        return ''
    return (msg.text or msg.caption or '').strip()


def _unwrap_code_block(
    text: str,
) -> tuple[str, str]:
    stripped = text.strip()
    if not stripped:
        return '', ''

    match = CODE_BLOCK_RE.match(stripped)
    if not match:
        return '', stripped

    language = (match.group('language') or '').strip().lower()
    code = match.group('code').strip()
    return language, code


async def _load_snippet(
    redis: Redis,
    name: str,
) -> ParseCode:
    raw_payload = await redis.hget(
        CODE_SNIPPETS_KEY,
        name,
    )
    if raw_payload is None:
        raise ValueError(f'Snippet "{name}" was not found.')

    payload = json.loads(raw_payload.decode('utf-8'))
    language = str(payload.get('language', '')).strip()
    code = str(payload.get('code', ''))
    if not language or not code:
        raise ValueError(
            f'Snippet "{name}" is invalid.'
        )
    return ParseCode(language=language, code=code)


async def _handle_code_save(
    msg: Message,
    redis: Redis,
    remainder: str,
) -> None:
    name, parse_code = _extract_named_code(msg, remainder)
    payload = json.dumps(
        {
            'language': parse_code.language,
            'code': parse_code.code,
        },
        ensure_ascii=False,
    )
    await redis.hset(CODE_SNIPPETS_KEY, name, payload)
    await msg.edit(
        '<b>Saved code</b>\n'
        f'<b>Name:</b> <code>{name}</code>\n'
        f'<b>Language:</b> <code>{parse_code.language}</code>',
        parse_mode=ParseMode.HTML,
    )


async def _handle_code_run(
    msg: Message,
    piston: PistonClient,
    redis: Redis,
    remainder: str,
) -> None:
    name = _extract_snippet_name_from_text(remainder)
    parse_code = await _load_snippet(redis, name)
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
    await msg.edit(
        ready_msg,
        parse_mode=ParseMode.HTML,
    )


async def _handle_code_show(
    msg: Message,
    redis: Redis,
    remainder: str,
) -> None:
    name = _extract_snippet_name_from_text(remainder)
    parse_code = await _load_snippet(redis, name)
    await msg.edit(
        utils.get_ready_msg(
            f'<b>Snippet:</b> <code>{name}</code>',
            utils.get_input_msg(
                parse_code.language,
                parse_code.code,
            ),
        ),
        parse_mode=ParseMode.HTML,
    )


async def _handle_code_list(
    msg: Message,
    redis: Redis,
) -> None:
    raw_items = await redis.hgetall(CODE_SNIPPETS_KEY)
    if not raw_items:
        await msg.edit(
            '<b>Saved code:</b> empty.',
            parse_mode=ParseMode.HTML,
        )
        return

    snippets: list[tuple[str, str]] = []
    for raw_name, raw_payload in raw_items.items():
        name = raw_name.decode('utf-8')
        payload = json.loads(raw_payload.decode('utf-8'))
        language = str(payload.get('language', 'text'))
        snippets.append((name, language))

    snippets.sort(key=lambda item: item[0])
    lines = [
        f'<code>{name}</code> <i>({language})</i>'
        for name, language in snippets
    ]
    await msg.edit(
        '<b>Saved code</b>\n' + '\n'.join(lines),
        parse_mode=ParseMode.HTML,
    )


async def _handle_code_delete(
    msg: Message,
    redis: Redis,
    remainder: str,
) -> None:
    name = _extract_snippet_name_from_text(remainder)
    deleted = await redis.hdel(CODE_SNIPPETS_KEY, name)
    if not deleted:
        raise ValueError(
            f'Snippet "{name}" was not found.'
        )
    await msg.edit(
        '<b>Deleted code</b>\n'
        f'<b>Name:</b> <code>{name}</code>',
        parse_mode=ParseMode.HTML,
    )


def _code_help_text() -> str:
    return (
        'Usage: .code <save|run|show|ls|rm> ...\n'
        '.code save <name> <language> <code>\n'
        '.code run <name>\n'
        '.code show <name>\n'
        '.code ls\n'
        '.code rm <name>'
    )
