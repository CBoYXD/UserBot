import re

from pyrogram.types import Message

from src.services.code_pars.base import ParseCode


CODE_BLOCK_RE = re.compile(
    r'^```(?P<language>[a-zA-Z0-9_+.#-]+)?\n'
    r'(?P<code>.*)\n```$',
    re.DOTALL,
)


def extract_command_body(msg: Message) -> str:
    text = extract_message_text(msg)
    if not text:
        return ''
    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        return ''
    return parts[1].strip()


def extract_message_text(msg: Message | None) -> str:
    if msg is None:
        return ''
    return (msg.text or msg.caption or '').strip()


def unwrap_code_block(text: str) -> tuple[str, str]:
    stripped = text.strip()
    if not stripped:
        return '', ''

    match = CODE_BLOCK_RE.match(stripped)
    if not match:
        return '', stripped

    language = (match.group('language') or '').strip().lower()
    code = match.group('code').strip()
    return language, code


def extract_run_code(msg: Message) -> ParseCode:
    body = extract_command_body(msg)
    reply_text = extract_message_text(msg.reply_to_message)

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

    block_language, code = unwrap_code_block(code_source)
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


def extract_python_code(msg: Message) -> str:
    body = extract_command_body(msg)
    code_source = body or extract_message_text(
        msg.reply_to_message
    )
    _, code = unwrap_code_block(code_source)
    if not code:
        raise ValueError(
            'Usage: .py <code>, ".py\\n<code>", '
            'or reply with code to ".py".'
        )
    return code


def extract_named_code(
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
        code_source = extract_message_text(
            msg.reply_to_message
        )

    block_language, code = unwrap_code_block(code_source)
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


def extract_snippet_name_from_text(text: str) -> str:
    name = text.strip().lower()
    if not name:
        raise ValueError('Snippet name is required.')
    return name


def extract_code_subcommand(
    msg: Message,
) -> tuple[str, str]:
    body = extract_command_body(msg)
    if not body:
        return '', ''
    command, _, remainder = body.partition(' ')
    return command.strip().lower(), remainder.strip()
