from html import escape

from pyrogram.enums import ParseMode
from pyrogram.types import Message
from redis.asyncio import Redis

from src.core.acl import cmd
from src.core.router import Router
from src.bot import utils
from src.bot.notes import storage


notes_router = Router('notes')


def _extract_body(msg: Message) -> str:
    text = msg.text or ''
    parts = text.split(maxsplit=1)
    return parts[1].strip() if len(parts) > 1 else ''


def _truncate(text: str, n: int = 80) -> str:
    text = (text or '').replace('\n', ' ')
    return text if len(text) <= n else text[: n - 3] + '...'


@notes_router.message(cmd('notes', 'note', 'нотатка'))
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

    nid = await storage.next_id(redis)
    tags = await storage.save(redis, nid, text)
    tags_str = (
        ' ' + ' '.join(f'#{t}' for t in tags) if tags else ''
    )
    await msg.edit(
        f'<b>Note saved</b> <code>#{nid}</code>{escape(tags_str)}',
        parse_mode=ParseMode.HTML,
    )


@notes_router.message(cmd('notes', 'notes', 'нотатки'))
async def notes_list(msg: Message, redis: Redis):
    body = _extract_body(msg)
    items = await storage.all_notes(redis)
    if not items:
        await msg.edit(
            '<b>Notes:</b> empty.',
            parse_mode=ParseMode.HTML,
        )
        return

    if body:
        tag = body.lstrip('#').lower()
        items = [
            it
            for it in items
            if tag in (
                t.lower() for t in it[1].get('tags', [])
            )
        ]
        if not items:
            await msg.edit(
                f'<b>Notes:</b> no notes for '
                f'<code>#{escape(tag)}</code>.',
                parse_mode=ParseMode.HTML,
            )
            return

    lines = [
        f'<code>#{nid}</code> '
        f'{escape(_truncate(data.get("text") or ""))}'
        for nid, data in items
    ]
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
    data = await storage.get(redis, nid)
    if data is None:
        await msg.edit(
            f'<b>Note</b> <code>#{escape(nid)}</code> not found.',
            parse_mode=ParseMode.HTML,
        )
        return
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
    if not await storage.delete(redis, nid):
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
    items = await storage.all_notes(redis)
    matches = [
        (nid, data.get('text') or '')
        for nid, data in items
        if query in (data.get('text') or '').lower()
    ]
    if not matches:
        await msg.edit(
            f'<b>Notes:</b> no matches for '
            f'<code>{escape(query)}</code>.',
            parse_mode=ParseMode.HTML,
        )
        return
    lines = [
        f'<code>#{nid}</code> {escape(_truncate(text))}'
        for nid, text in matches
    ]
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
