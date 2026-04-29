import time
from datetime import datetime
from html import escape

from pyrogram import Client, filters
from pyrogram.enums import ParseMode
from pyrogram.types import Message
from redis.asyncio import Redis

from src.bot.modules.reminders import parser, storage
from src.bot.modules.reminders.loop import ensure_loop
from src.bot.modules.reminders.router import reminders_router


@reminders_router.message(filters.command('r', prefixes='.'))
async def reminder_cmd(
    msg: Message,
    redis: Redis,
    client: Client,
):
    text = msg.text or ''
    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        await msg.edit(
            '<b>Usage:</b> '
            '<code>.r &lt;Nm|Nh|Nd|Nw|HH:MM&gt; &lt;text&gt;</code>\n'
            '<code>.r ls</code>, <code>.r rm &lt;id&gt;</code>',
            parse_mode=ParseMode.HTML,
        )
        return
    body = parts[1].strip()

    if body.lower() == 'ls':
        await _reminder_list(msg, redis)
        return
    if body.lower().startswith('rm'):
        rest = body[2:].strip().lstrip('#')
        await _reminder_rm(msg, redis, rest)
        return

    try:
        when_token, text_body = parser.parse_command(body)
        ts = parser.parse_when(when_token)
    except ValueError as e:
        await msg.edit(
            f'<b>Reminder error:</b> '
            f'<code>{escape(str(e))}</code>',
            parse_mode=ParseMode.HTML,
        )
        return

    if not text_body and msg.reply_to_message:
        text_body = (
            msg.reply_to_message.text
            or msg.reply_to_message.caption
            or ''
        ).strip()
    if not text_body:
        text_body = '(no text)'

    rid = await storage.next_id(redis)
    await storage.add(
        redis,
        rid,
        chat_id=msg.chat.id,
        reply_to=msg.id,
        text=text_body,
        ts=ts,
    )

    when_str = datetime.fromtimestamp(ts).strftime(
        '%Y-%m-%d %H:%M:%S'
    )
    delta = max(0, ts - int(time.time()))
    await msg.edit(
        f'<b>Reminder</b> <code>#{rid}</code> set for '
        f'<code>{escape(when_str)}</code> '
        f'(in {parser.humanize(delta)}).',
        parse_mode=ParseMode.HTML,
    )

    ensure_loop(redis, client)


async def _reminder_list(msg: Message, redis: Redis):
    items = await storage.all_reminders(redis)
    if not items:
        await msg.edit(
            '<b>Reminders:</b> empty.',
            parse_mode=ParseMode.HTML,
        )
        return
    lines = []
    for rid, data in items:
        when_str = datetime.fromtimestamp(
            data.get('ts', 0)
        ).strftime('%Y-%m-%d %H:%M')
        text = (data.get('text') or '').replace('\n', ' ')
        if len(text) > 60:
            text = text[:57] + '...'
        lines.append(
            f'<code>#{rid}</code> '
            f'<code>{escape(when_str)}</code> '
            f'{escape(text)}'
        )
    await msg.edit(
        '<b>Reminders</b>\n' + '\n'.join(lines),
        parse_mode=ParseMode.HTML,
    )


async def _reminder_rm(msg: Message, redis: Redis, rid: str):
    rid = rid.strip()
    if not rid:
        await msg.edit(
            '<b>Usage:</b> <code>.r rm &lt;id&gt;</code>',
            parse_mode=ParseMode.HTML,
        )
        return
    if not await storage.delete(redis, rid):
        await msg.edit(
            f'<b>Reminder</b> <code>#{escape(rid)}</code> '
            'not found.',
            parse_mode=ParseMode.HTML,
        )
        return
    await msg.edit(
        f'<b>Reminder</b> <code>#{escape(rid)}</code> removed.',
        parse_mode=ParseMode.HTML,
    )
