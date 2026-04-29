import io
from html import escape

from pyrogram import Client, filters
from pyrogram.enums import ParseMode
from pyrogram.types import Message

from src.bot.modules.quote.avatar import fetch_avatar
from src.bot.modules.quote.render import render_quote
from src.bot.modules.quote.router import quote_router


def _display_name(target: Message) -> str:
    user = target.from_user
    if user is not None:
        full = (
            (user.first_name or '')
            + (' ' + user.last_name if user.last_name else '')
        ).strip()
        return full or user.username or 'User'
    return getattr(target.sender_chat, 'title', 'Channel')


@quote_router.message(
    filters.command(['q', 'quote'], prefixes='.')
)
async def quote_cmd(msg: Message, client: Client):
    target = msg.reply_to_message
    if target is None:
        await msg.edit(
            '<b>Usage:</b> reply to a message with '
            '<code>.q</code>.',
            parse_mode=ParseMode.HTML,
        )
        return

    text = (target.text or target.caption or '').strip()
    if not text:
        await msg.edit(
            '<b>Quote:</b> message has no text.',
            parse_mode=ParseMode.HTML,
        )
        return

    name = _display_name(target)

    try:
        avatar = await fetch_avatar(client, target.from_user)
        png = render_quote(name, text, avatar)
        bio = io.BytesIO(png)
        bio.name = 'quote.png'
        await msg.delete()
        await client.send_photo(
            chat_id=msg.chat.id,
            photo=bio,
            reply_to_message_id=target.id,
        )
    except Exception as e:
        await msg.edit(
            f'<b>Quote error:</b> <code>{escape(str(e))}</code>',
            parse_mode=ParseMode.HTML,
        )
