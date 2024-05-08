from pyrogram.types import Message
from redis.asyncio import Redis
from ...services.code_pars.base import ParseCommands


def get_input_msg(language: str, code: str) -> str:
    return (
        '<b>Input:</b>'
        + '\n'
        + f'<pre language="{language}">{code}</pre>'
    )


def get_output_msg(code: str) -> str:
    return '<b>Output:</b>\n' + f'<pre language="output">{code}</pre>'


def get_process_time_msg(start_time: int, end_time: int) -> str:
    return f'<b>Process time: {end_time-start_time}</b>'


def get_from_terminal_msg(output: str) -> str:
    if bool(output):
        return '<b>From terminal:</b>\n'
        +f'<pre language="output">{from_terminal}</pre>'
    else:
        return ''


def get_terminal_output() -> str:
    pass


def get_msg_text(msg: Message):
    return (
        msg.text
        if msg.reply_to_message is None
        else msg.text + '\n' + msg.reply_to_message.text
    )


def get_ready_msg(*args: list):
    return '\n\n'.join([arg for arg in args if bool(arg)])


async def exec_use_file(redis: Redis, name_of_file: str) -> str:
    return await redis.get(name_of_file)
