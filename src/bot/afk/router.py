import time
from html import escape

from pyrogram import filters
from pyrogram.enums import ChatType, ParseMode
from pyrogram.types import Message
from redis.asyncio import Redis

from src.core.router import Router
from src.bot.afk import storage


afk_router = Router('afk')


@afk_router.message(
    filters.me & filters.command('afk', prefixes='.')
)
async def afk_on(msg: Message, redis: Redis):
    text = msg.text or ''
    parts = text.split(maxsplit=1)
    reason = parts[1].strip() if len(parts) > 1 else ''
    await storage.enable(redis, reason)
    msg_text = '<b>AFK:</b> on.'
    if reason:
        msg_text += f' <i>{escape(reason)}</i>'
    await msg.edit(msg_text, parse_mode=ParseMode.HTML)


@afk_router.message(
    filters.me & filters.command('unafk', prefixes='.')
)
async def afk_off(msg: Message, redis: Redis):
    was = await storage.disable(redis)
    text = '<b>AFK:</b> off.' if was else (
        '<b>AFK:</b> already off.'
    )
    await msg.edit(text, parse_mode=ParseMode.HTML)


@afk_router.message(
    ~filters.me
    & filters.private
    & ~filters.bot
    & ~filters.service
)
async def afk_auto_reply(msg: Message, redis: Redis):
    if not await storage.is_enabled(redis):
        return
    if msg.chat.type != ChatType.PRIVATE:
        return
    user_id = msg.from_user.id if msg.from_user else 0
    if not user_id:
        return
    if not await storage.mark_replied(redis, user_id):
        return

    reason, since = await storage.get_state(redis)
    text = '🚫 AFK'
    if since:
        text += f' for {storage.humanize(int(time.time()) - since)}'
    text += '.'
    if reason:
        text += f'\nReason: {reason}'
    text += '\n_(automated reply)_'
    try:
        await msg.reply_text(text)
    except Exception:
        pass


@afk_router.message(filters.me & filters.outgoing, group=99)
async def afk_auto_off(msg: Message, redis: Redis):
    """Auto-disable AFK on any outgoing manual message."""
    text = msg.text or msg.caption or ''
    if text.startswith('.'):
        return
    if not await storage.is_enabled(redis):
        return
    await storage.disable(redis)
