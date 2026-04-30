import io
from html import escape

from pyrogram import Client, filters
from pyrogram.enums import ParseMode
from pyrogram.types import Message

from src.core.router import Router
from src.services.quote import QuoteService


quote_router = Router('quote')
quote_router.router_filters = filters.me


@quote_router.message(
    filters.command(['q', 'quote'], prefixes='.')
)
async def quote_cmd(
    msg: Message, client: Client, quote: QuoteService
):
    target = msg.reply_to_message
    if target is None:
        await msg.edit(
            '<b>Usage:</b> reply to a message with '
            '<code>.q</code>.',
            parse_mode=ParseMode.HTML,
        )
        return

    if not (target.text or target.caption or '').strip():
        await msg.edit(
            '<b>Quote:</b> message has no text.',
            parse_mode=ParseMode.HTML,
        )
        return

    try:
        png = await quote.render_for_message(client, target)
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
