import io
import re
from html import escape, unescape

from pyrogram.enums import ParseMode
from pyrogram.types import Message


MAX_TEXT_MESSAGE_LENGTH = 3800
HTML_TAG_RE = re.compile(r'<[^>]+>')


def html_to_plain_text(text: str) -> str:
    return unescape(HTML_TAG_RE.sub('', text))


async def edit_or_send_as_text_file(
    msg: Message,
    text: str,
    *,
    file_text: str | None = None,
    filename: str = 'response.txt',
    parse_mode: ParseMode | None = ParseMode.HTML,
) -> None:
    if len(text) <= MAX_TEXT_MESSAGE_LENGTH:
        await msg.edit(text, parse_mode=parse_mode)
        return

    payload = file_text or html_to_plain_text(text)
    document = io.BytesIO(payload.encode('utf-8'))
    document.name = filename

    await msg.edit(
        '<b>Response is too long for Telegram.</b>\n'
        f'<b>Sent as file:</b> <code>{escape(filename)}</code>',
        parse_mode=ParseMode.HTML,
    )
    await msg.reply_document(document=document)
