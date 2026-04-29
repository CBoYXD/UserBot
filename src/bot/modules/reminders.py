import asyncio
import json
import logging
import re
import time
from datetime import datetime, timedelta
from html import escape

from pyrogram import Client, filters
from pyrogram.enums import ParseMode
from pyrogram.types import Message
from redis.asyncio import Redis

from src.bot.tools.router import Router


reminders_router = Router('reminders')
reminders_router.router_filters = filters.me

REMINDERS_KEY = 'reminders:list'
REMINDERS_QUEUE = 'reminders:queue'
REMINDERS_NEXT_ID = 'reminders:next_id'
REMINDERS_LOOP_FLAG = 'reminders:_loop_started'

DURATION_RE = re.compile(
    r'^(?P<n>\d+)(?P<u>[smhdw])$',
    re.IGNORECASE,
)
HHMM_RE = re.compile(r'^(?P<h>\d{1,2}):(?P<m>\d{2})$')

_logger = logging.getLogger('reminders')
_loop_task: asyncio.Task | None = None


def _parse_when(token: str) -> int:
    """Return absolute unix ts for when the reminder fires."""
    token = token.strip()
    now = int(time.time())

    m = DURATION_RE.match(token)
    if m:
        n = int(m.group('n'))
        unit = m.group('u').lower()
        seconds = {
            's': 1,
            'm': 60,
            'h': 3600,
            'd': 86400,
            'w': 604800,
        }[unit]
        return now + n * seconds

    m = HHMM_RE.match(token)
    if m:
        h, mm = int(m.group('h')), int(m.group('m'))
        if not (0 <= h < 24 and 0 <= mm < 60):
            raise ValueError('Invalid HH:MM')
        target = datetime.now().replace(
            hour=h, minute=mm, second=0, microsecond=0
        )
        if target.timestamp() <= now:
            target += timedelta(days=1)
        return int(target.timestamp())

    try:
        dt = datetime.fromisoformat(token)
        ts = int(dt.timestamp())
        if ts <= now:
            raise ValueError('Datetime is in the past')
        return ts
    except ValueError:
        pass

    raise ValueError(
        'Use Nm/Nh/Nd/Nw, HH:MM, or YYYY-MM-DD HH:MM'
    )


def _parse_command(text: str) -> tuple[str, str]:
    """Split body into (when_token, message_text)."""
    parts = text.strip().split(maxsplit=1)
    if not parts:
        raise ValueError('Empty')
    when = parts[0]
    body = parts[1] if len(parts) > 1 else ''
    if when.startswith(('"', "'")):
        # support quoted ISO datetimes
        quote = when[0]
        rest = text[1:]
        end = rest.find(quote)
        if end == -1:
            raise ValueError('Unterminated quoted datetime')
        when = rest[:end]
        body = rest[end + 1 :].strip()
    return when, body


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
        when_token, text_body = _parse_command(body)
        ts = _parse_when(when_token)
    except ValueError as e:
        await msg.edit(
            f'<b>Reminder error:</b> <code>{escape(str(e))}</code>',
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

    rid = int(await redis.incr(REMINDERS_NEXT_ID))
    payload = json.dumps(
        {
            'chat_id': msg.chat.id,
            'reply_to': msg.id,
            'text': text_body,
            'ts': ts,
        },
        ensure_ascii=False,
    )
    await redis.hset(REMINDERS_KEY, str(rid), payload)
    await redis.zadd(REMINDERS_QUEUE, {str(rid): ts})

    when_str = datetime.fromtimestamp(ts).strftime(
        '%Y-%m-%d %H:%M:%S'
    )
    delta = max(0, ts - int(time.time()))
    await msg.edit(
        f'<b>Reminder</b> <code>#{rid}</code> set for '
        f'<code>{escape(when_str)}</code> '
        f'(in {_humanize(delta)}).',
        parse_mode=ParseMode.HTML,
    )

    ensure_loop(redis, client)


async def _reminder_list(msg: Message, redis: Redis):
    raw = await redis.hgetall(REMINDERS_KEY)
    if not raw:
        await msg.edit(
            '<b>Reminders:</b> empty.',
            parse_mode=ParseMode.HTML,
        )
        return
    items: list[tuple[int, dict]] = []
    for k, v in raw.items():
        try:
            items.append(
                (int(k.decode('utf-8')), json.loads(v))
            )
        except Exception:
            continue
    items.sort(key=lambda x: x[1].get('ts', 0))
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


async def _reminder_rm(
    msg: Message, redis: Redis, rid: str
):
    rid = rid.strip()
    if not rid:
        await msg.edit(
            '<b>Usage:</b> <code>.r rm &lt;id&gt;</code>',
            parse_mode=ParseMode.HTML,
        )
        return
    deleted = await redis.hdel(REMINDERS_KEY, rid)
    await redis.zrem(REMINDERS_QUEUE, rid)
    if not deleted:
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


def _humanize(seconds: int) -> str:
    if seconds < 60:
        return f'{seconds}s'
    if seconds < 3600:
        return f'{seconds // 60}m'
    if seconds < 86400:
        return f'{seconds // 3600}h {(seconds % 3600) // 60}m'
    return f'{seconds // 86400}d {(seconds % 86400) // 3600}h'


def ensure_loop(redis: Redis, client: Client) -> None:
    global _loop_task
    if _loop_task is not None and not _loop_task.done():
        return
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    _loop_task = loop.create_task(_reminder_loop(redis, client))


async def _reminder_loop(redis: Redis, client: Client):
    _logger.info('Reminder loop started')
    while True:
        try:
            now = int(time.time())
            due = await redis.zrangebyscore(
                REMINDERS_QUEUE, 0, now, start=0, num=20
            )
            for raw_id in due:
                rid = (
                    raw_id.decode('utf-8')
                    if isinstance(raw_id, (bytes, bytearray))
                    else str(raw_id)
                )
                payload = await redis.hget(REMINDERS_KEY, rid)
                if payload:
                    try:
                        data = json.loads(payload)
                        await client.send_message(
                            chat_id=data['chat_id'],
                            text=(
                                f'⏰ **Reminder #{rid}**\n'
                                f'{data.get("text", "")}'
                            ),
                            reply_to_message_id=data.get(
                                'reply_to'
                            ),
                        )
                    except Exception as e:
                        _logger.warning(
                            'Failed to send reminder %s: %s',
                            rid,
                            e,
                        )
                    await redis.hdel(REMINDERS_KEY, rid)
                await redis.zrem(REMINDERS_QUEUE, rid)
        except Exception as e:
            _logger.exception('Reminder loop error: %s', e)
        await asyncio.sleep(5)


async def start_reminder_loop(
    redis: Redis, client: Client
) -> None:
    """Public entry to start the loop at app boot."""
    ensure_loop(redis, client)
