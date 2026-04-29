import json
import re
import time
from html import escape

from pyrogram import filters
from pyrogram.enums import ParseMode
from pyrogram.types import Message
from redis.asyncio import Redis

from src.bot.tools import utils
from src.bot.tools.router import Router


notes_router = Router('notes')
notes_router.router_filters = filters.me

NOTES_KEY = 'notes:list'
NOTES_NEXT_ID = 'notes:next_id'
TAG_RE = re.compile(r'#([\w\-_]+)', re.UNICODE)


def _extract_body(msg: Message) -> str:
    text = msg.text or ''
    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        return ''
    return parts[1].strip()


async def _next_id(redis: Redis) -> int:
    return int(await redis.incr(NOTES_NEXT_ID))


@notes_router.message(filters.command('note', prefixes='.'))
async def note_cmd(msg: Message, redis: Redis):
    body = _extract_body(msg)
    sub, _, rest = body.partition(' ')
    sub = sub.lower().strip()

    if sub == 'show':
        await _note_show(msg, redis, rest.strip())
        return
    if sub == 'rm':
        await _note_rm(msg, redis, rest.strip())
        return
    if sub == 'find':
        await _note_find(msg, redis, rest.strip())
        return

    text = body
    if not text and msg.reply_to_message:
        text = (
            msg.reply_to_message.text
            or msg.reply_to_message.caption
            or ''
        ).strip()
    if not text:
        await msg.edit(
            '<b>Usage:</b> <code>.note &lt;text&gt;</code>, '
            '<code>.note show &lt;id&gt;</code>, '
            '<code>.note rm &lt;id&gt;</code>, '
            '<code>.note find &lt;query&gt;</code>',
            parse_mode=ParseMode.HTML,
        )
        return

    nid = await _next_id(redis)
    tags = sorted(set(TAG_RE.findall(text)))
    payload = json.dumps(
        {
            'text': text,
            'ts': int(time.time()),
            'tags': tags,
        },
        ensure_ascii=False,
    )
    await redis.hset(NOTES_KEY, str(nid), payload)
    tags_str = (
        ' ' + ' '.join(f'#{t}' for t in tags) if tags else ''
    )
    await msg.edit(
        f'<b>Note saved</b> <code>#{nid}</code>{escape(tags_str)}',
        parse_mode=ParseMode.HTML,
    )


@notes_router.message(filters.command('notes', prefixes='.'))
async def notes_list(msg: Message, redis: Redis):
    body = _extract_body(msg)
    raw = await redis.hgetall(NOTES_KEY)
    if not raw:
        await msg.edit(
            '<b>Notes:</b> empty.',
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
    items.sort(key=lambda x: x[0])

    if body:
        tag = body.lstrip('#').lower()
        items = [
            it
            for it in items
            if tag in (t.lower() for t in it[1].get('tags', []))
        ]
        if not items:
            await msg.edit(
                f'<b>Notes:</b> no notes for '
                f'<code>#{escape(tag)}</code>.',
                parse_mode=ParseMode.HTML,
            )
            return

    lines = []
    for nid, data in items:
        text = (data.get('text') or '').replace('\n', ' ')
        if len(text) > 80:
            text = text[:77] + '...'
        lines.append(
            f'<code>#{nid}</code> {escape(text)}'
        )
    text = '<b>Notes</b>\n' + '\n'.join(lines)
    file_text = '\n'.join(
        f'#{nid} {(data.get("text") or "")}'
        for nid, data in items
    )
    await utils.edit_or_send_as_text_file(
        msg,
        text,
        file_text=file_text,
        filename=f'notes-{msg.id}.txt',
    )


async def _note_show(msg: Message, redis: Redis, rest: str):
    nid = rest.lstrip('#').strip()
    if not nid:
        await msg.edit(
            '<b>Usage:</b> <code>.note show &lt;id&gt;</code>',
            parse_mode=ParseMode.HTML,
        )
        return
    raw = await redis.hget(NOTES_KEY, nid)
    if not raw:
        await msg.edit(
            f'<b>Note</b> <code>#{escape(nid)}</code> not found.',
            parse_mode=ParseMode.HTML,
        )
        return
    data = json.loads(raw)
    tags = data.get('tags') or []
    tag_line = (
        '<b>Tags:</b> '
        + ' '.join(f'<code>#{escape(t)}</code>' for t in tags)
        + '\n'
        if tags
        else ''
    )
    body = (
        f'<b>Note</b> <code>#{escape(nid)}</code>\n'
        f'{tag_line}\n'
        f'{escape(data.get("text") or "")}'
    )
    await utils.edit_or_send_as_text_file(
        msg,
        body,
        file_text=data.get('text') or '',
        filename=f'note-{nid}.txt',
    )


async def _note_rm(msg: Message, redis: Redis, rest: str):
    nid = rest.lstrip('#').strip()
    if not nid:
        await msg.edit(
            '<b>Usage:</b> <code>.note rm &lt;id&gt;</code>',
            parse_mode=ParseMode.HTML,
        )
        return
    deleted = await redis.hdel(NOTES_KEY, nid)
    if not deleted:
        await msg.edit(
            f'<b>Note</b> <code>#{escape(nid)}</code> not found.',
            parse_mode=ParseMode.HTML,
        )
        return
    await msg.edit(
        f'<b>Note</b> <code>#{escape(nid)}</code> removed.',
        parse_mode=ParseMode.HTML,
    )


async def _note_find(msg: Message, redis: Redis, rest: str):
    query = rest.strip().lower()
    if not query:
        await msg.edit(
            '<b>Usage:</b> <code>.note find &lt;query&gt;</code>',
            parse_mode=ParseMode.HTML,
        )
        return
    raw = await redis.hgetall(NOTES_KEY)
    matches: list[tuple[int, str]] = []
    for k, v in raw.items():
        try:
            data = json.loads(v)
        except Exception:
            continue
        text = (data.get('text') or '').lower()
        if query in text:
            matches.append(
                (int(k.decode('utf-8')), data.get('text') or '')
            )
    if not matches:
        await msg.edit(
            f'<b>Notes:</b> no matches for '
            f'<code>{escape(query)}</code>.',
            parse_mode=ParseMode.HTML,
        )
        return
    matches.sort(key=lambda x: x[0])
    lines = []
    for nid, text in matches:
        text = text.replace('\n', ' ')
        if len(text) > 80:
            text = text[:77] + '...'
        lines.append(f'<code>#{nid}</code> {escape(text)}')
    body = (
        f'<b>Notes matching</b> <code>{escape(query)}</code>\n'
        + '\n'.join(lines)
    )
    file_text = '\n'.join(
        f'#{nid} {text}' for nid, text in matches
    )
    await utils.edit_or_send_as_text_file(
        msg,
        body,
        file_text=file_text,
        filename=f'notes-find-{msg.id}.txt',
    )
