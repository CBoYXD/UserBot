import time
from html import escape

from pyrogram import filters
from pyrogram.enums import ChatType, ParseMode
from pyrogram.types import Message
from redis.asyncio import Redis

from src.bot.tools.router import Router


afk_router = Router('afk')

AFK_ENABLED_KEY = 'afk:enabled'
AFK_REASON_KEY = 'afk:reason'
AFK_SINCE_KEY = 'afk:since'
AFK_REPLY_TTL = 600


def _humanize(seconds: int) -> str:
    if seconds < 60:
        return f'{seconds}s'
    if seconds < 3600:
        return f'{seconds // 60}m'
    if seconds < 86400:
        return f'{seconds // 3600}h'
    return f'{seconds // 86400}d'


@afk_router.message(
    filters.me & filters.command('afk', prefixes='.')
)
async def afk_on(msg: Message, redis: Redis):
    text = msg.text or ''
    parts = text.split(maxsplit=1)
    reason = parts[1].strip() if len(parts) > 1 else ''
    await redis.set(AFK_ENABLED_KEY, '1')
    await redis.set(AFK_REASON_KEY, reason)
    await redis.set(AFK_SINCE_KEY, str(int(time.time())))
    msg_text = '<b>AFK:</b> on.'
    if reason:
        msg_text += f' <i>{escape(reason)}</i>'
    await msg.edit(msg_text, parse_mode=ParseMode.HTML)


@afk_router.message(
    filters.me & filters.command('unafk', prefixes='.')
)
async def afk_off(msg: Message, redis: Redis):
    was = await redis.get(AFK_ENABLED_KEY)
    await redis.delete(
        AFK_ENABLED_KEY, AFK_REASON_KEY, AFK_SINCE_KEY
    )
    if was:
        await msg.edit(
            '<b>AFK:</b> off.', parse_mode=ParseMode.HTML
        )
    else:
        await msg.edit(
            '<b>AFK:</b> already off.',
            parse_mode=ParseMode.HTML,
        )


@afk_router.message(
    ~filters.me
    & filters.private
    & ~filters.bot
    & ~filters.service
)
async def afk_auto_reply(msg: Message, redis: Redis):
    enabled = await redis.get(AFK_ENABLED_KEY)
    if not enabled:
        return
    if msg.chat.type != ChatType.PRIVATE:
        return

    user_id = msg.from_user.id if msg.from_user else 0
    if not user_id:
        return
    rate_key = f'afk:replied:{user_id}'
    if await redis.get(rate_key):
        return
    await redis.set(rate_key, '1', ex=AFK_REPLY_TTL)

    raw_reason = await redis.get(AFK_REASON_KEY)
    raw_since = await redis.get(AFK_SINCE_KEY)
    reason = (
        raw_reason.decode('utf-8') if raw_reason else ''
    )
    since = (
        int(raw_since.decode('utf-8')) if raw_since else 0
    )

    text = '🚫 AFK'
    if since:
        text += f' for {_humanize(int(time.time()) - since)}'
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
    enabled = await redis.get(AFK_ENABLED_KEY)
    if not enabled:
        return
    await redis.delete(
        AFK_ENABLED_KEY, AFK_REASON_KEY, AFK_SINCE_KEY
    )
