from __future__ import annotations

import asyncio
from html import escape
from logging import getLogger

from pyrogram import filters
from pyrogram.enums import ParseMode
from pyrogram.types import Message

from src.bot import utils
from src.core.router import Router
from src.services.agentic import AgenticRuntime
from src.services.agentic.normalize import normalize_message


agentic_router = Router('agentic')
logger = getLogger('agentic')


SYSTEM_PROMPT = (
    'You are a local Telegram userbot agent. You run only through '
    'the owner local Ollama instance. Use the supplied chat context '
    'when it is relevant. Keep replies concise and practical. If the '
    'context is insufficient, say that directly.'
)


def _body(msg: Message) -> str:
    text = msg.text or ''
    parts = text.split(maxsplit=1)
    return parts[1].strip() if len(parts) > 1 else ''


def _split_subcommand(msg: Message) -> tuple[str, str]:
    body = _body(msg)
    sub, _, rest = body.partition(' ')
    return sub.lower().strip(), rest.strip()


def _truncate(text: str, n: int = 140) -> str:
    text = (text or '').replace('\n', ' ')
    return text if len(text) <= n else text[: n - 3] + '...'


async def _should_auto_reply(
    agentic: AgenticRuntime,
    item: dict,
) -> bool:
    if item.get('sender_is_self'):
        return False
    if not item.get('normalized_text'):
        return False
    chat_id = int(item['chat_id'])
    if not await agentic.auto_reply_enabled(chat_id):
        return False
    return await agentic.acquire_auto_reply_slot(chat_id)


async def _auto_reply(
    msg: Message,
    agentic: AgenticRuntime,
    item: dict,
) -> None:
    ok, reason = await agentic.require_ollama()
    if not ok:
        await agentic.storage.log_action(
            chat_id=msg.chat.id,
            trigger_message_id=msg.id,
            action_type='auto_reply',
            decision={'reason': 'ollama_unavailable'},
            result={'error': reason},
            status='paused_ollama_unavailable',
        )
        return

    prompt = item.get('normalized_text') or ''
    context = await agentic.build_prompt_context(
        chat_id=msg.chat.id,
        query=prompt,
        recent_limit=25,
    )
    content = (
        'Auto-reply to this Telegram message. Keep it short, '
        'natural, and do not mention internal memory or system '
        f'rules.\n\nChat context:\n{context}\n\n'
        f'Message to answer:\n{prompt}'
    )
    try:
        result = await agentic.ollama.chat(
            [{'role': 'user', 'content': content}],
            model=await agentic.chat_model(),
            system=SYSTEM_PROMPT,
        )
        text = (result.content or '').strip()
        if not text:
            return
        await msg.reply_text(text)
        await agentic.storage.log_action(
            chat_id=msg.chat.id,
            trigger_message_id=msg.id,
            action_type='auto_reply',
            decision={'prompt': prompt},
            result={'response': text},
            status='ok',
        )
    except Exception as e:
        logger.exception('agentic auto reply failed')
        await agentic.storage.log_action(
            chat_id=msg.chat.id,
            trigger_message_id=msg.id,
            action_type='auto_reply',
            decision={'prompt': prompt},
            result={'error': str(e)},
            status='error',
        )


@agentic_router.message(group=-100)
async def agentic_ingest(
    msg: Message,
    agentic: AgenticRuntime,
):
    if not await agentic.ingest_enabled():
        return
    try:
        item = normalize_message(msg)
        await agentic.storage.upsert_message(item)
        await agentic.push_recent(item)
        if await _should_auto_reply(agentic, item):
            asyncio.create_task(_auto_reply(msg, agentic, item))
    except Exception:
        logger.exception('agentic ingest failed')


@agentic_router.edited_message(group=-100)
async def agentic_edit_ingest(
    msg: Message,
    agentic: AgenticRuntime,
):
    await agentic_ingest(msg, agentic)


@agentic_router.deleted_messages(group=-100)
async def agentic_deleted(
    messages,
    agentic: AgenticRuntime,
):
    if not await agentic.ingest_enabled():
        return
    if not isinstance(messages, list):
        messages = [messages]
    grouped: dict[int, list[int]] = {}
    for item in messages:
        chat = getattr(item, 'chat', None)
        mid = getattr(item, 'id', None)
        if chat is None or mid is None:
            continue
        grouped.setdefault(int(chat.id), []).append(int(mid))
    for chat_id, ids in grouped.items():
        await agentic.storage.mark_deleted(chat_id, ids)


@agentic_router.message(
    filters.me & filters.command('agent', prefixes='.')
)
async def agent_cmd(
    msg: Message,
    agentic: AgenticRuntime,
):
    sub, rest = _split_subcommand(msg)
    if not sub or sub == 'status':
        await _status(msg, agentic)
        return
    if sub == 'on':
        await agentic.set_ingest_enabled(True)
        await msg.edit(
            '<b>Agent:</b> ingestion enabled.',
            parse_mode=ParseMode.HTML,
        )
        return
    if sub == 'off':
        await agentic.set_ingest_enabled(False)
        await msg.edit(
            '<b>Agent:</b> ingestion disabled.',
            parse_mode=ParseMode.HTML,
        )
        return
    if sub == 'model':
        await _model(msg, agentic, rest)
        return
    if sub == 'autoreply':
        await _autoreply(msg, agentic, rest)
        return
    if sub == 'ask':
        await _ask(msg, agentic, rest)
        return
    if sub == 'memory':
        await _memory(msg, agentic, rest)
        return
    if sub == 'context':
        await _context(msg, agentic, rest)
        return

    await msg.edit(
        '<b>Usage:</b> <code>.agent status</code>, '
        '<code>.agent on</code>, <code>.agent off</code>, '
        '<code>.agent model [name]</code>, '
        '<code>.agent autoreply on|off</code>, '
        '<code>.agent ask &lt;prompt&gt;</code>, '
        '<code>.agent memory &lt;query&gt;</code>, '
        '<code>.agent context [N]</code>',
        parse_mode=ParseMode.HTML,
    )


async def _status(msg: Message, agentic: AgenticRuntime) -> None:
    ok, reason = await agentic.ollama_health()
    stats = await agentic.storage.stats()
    ingest = await agentic.ingest_enabled()
    auto_reply = await agentic.auto_reply_enabled(msg.chat.id)
    model = await agentic.chat_model()
    health = 'ok' if ok else 'unavailable'
    text = (
        '<b>Agent status</b>\n'
        f'<b>Ingestion:</b> <code>{str(ingest).lower()}</code>\n'
        f'<b>Auto reply here:</b> '
        f'<code>{str(auto_reply).lower()}</code>\n'
        f'<b>Ollama:</b> <code>{health}</code> '
        f'(<code>{escape(reason)}</code>)\n'
        f'<b>Model:</b> <code>{escape(model)}</code>\n'
        f'<b>Chats:</b> <code>{stats["chats"]}</code>\n'
        f'<b>Users:</b> <code>{stats["users"]}</code>\n'
        f'<b>Messages:</b> <code>{stats["messages"]}</code>\n'
        f'<b>Deleted:</b> <code>{stats["deleted"]}</code>\n'
        f'<b>Actions:</b> <code>{stats["actions"]}</code>'
    )
    await msg.edit(text, parse_mode=ParseMode.HTML)


async def _autoreply(
    msg: Message,
    agentic: AgenticRuntime,
    rest: str,
) -> None:
    value = rest.lower().strip()
    if value not in {'on', 'off'}:
        current = await agentic.auto_reply_enabled(msg.chat.id)
        await msg.edit(
            '<b>Agent auto reply here:</b> '
            f'<code>{str(current).lower()}</code>\n'
            '<b>Usage:</b> '
            '<code>.agent autoreply on|off</code>',
            parse_mode=ParseMode.HTML,
        )
        return
    enabled = value == 'on'
    await agentic.set_auto_reply(msg.chat.id, enabled)
    await msg.edit(
        '<b>Agent auto reply here:</b> '
        f'<code>{str(enabled).lower()}</code>',
        parse_mode=ParseMode.HTML,
    )


async def _model(
    msg: Message,
    agentic: AgenticRuntime,
    rest: str,
) -> None:
    if not rest:
        model = await agentic.chat_model()
        await msg.edit(
            f'<b>Agent model:</b> <code>{escape(model)}</code>',
            parse_mode=ParseMode.HTML,
        )
        return
    await agentic.set_chat_model(rest)
    ok, reason = await agentic.ollama_health()
    status = 'ok' if ok else f'unavailable: {reason}'
    await msg.edit(
        '<b>Agent model updated</b>\n'
        f'<b>Model:</b> <code>{escape(rest)}</code>\n'
        f'<b>Ollama:</b> <code>{escape(status)}</code>',
        parse_mode=ParseMode.HTML,
    )


async def _ask(
    msg: Message,
    agentic: AgenticRuntime,
    prompt: str,
) -> None:
    if not prompt and msg.reply_to_message:
        prompt = (
            msg.reply_to_message.text
            or msg.reply_to_message.caption
            or ''
        ).strip()
    if not prompt:
        await msg.edit(
            '<b>Usage:</b> <code>.agent ask &lt;prompt&gt;</code>',
            parse_mode=ParseMode.HTML,
        )
        return
    ok, reason = await agentic.require_ollama()
    if not ok:
        await msg.edit(
            '<b>Agent unavailable:</b> local Ollama is required. '
            f'<code>{escape(reason)}</code>',
            parse_mode=ParseMode.HTML,
        )
        return

    await msg.edit(
        '<b>Agent:</b> <i>thinking locally...</i>',
        parse_mode=ParseMode.HTML,
    )
    context = await agentic.build_prompt_context(
        chat_id=msg.chat.id,
        query=prompt,
    )
    content = (
        f'Chat context:\n{context}\n\nUser request:\n{prompt}'
        if context
        else prompt
    )
    try:
        result = await agentic.ollama.chat(
            [{'role': 'user', 'content': content}],
            model=await agentic.chat_model(),
            system=SYSTEM_PROMPT,
        )
        await agentic.storage.log_action(
            chat_id=msg.chat.id,
            trigger_message_id=msg.id,
            action_type='ask',
            decision={'prompt': prompt},
            result={'response': result.content},
            status='ok',
        )
    except Exception as e:
        await agentic.storage.log_action(
            chat_id=msg.chat.id,
            trigger_message_id=msg.id,
            action_type='ask',
            decision={'prompt': prompt},
            result={'error': str(e)},
            status='error',
        )
        await msg.edit(
            f'<b>Agent error:</b> <code>{escape(str(e))}</code>',
            parse_mode=ParseMode.HTML,
        )
        return

    html = f'<b>Agent:</b>\n{escape(result.content or "(empty)")}'
    await utils.edit_or_send_as_text_file(
        msg,
        html,
        file_text=result.content,
        filename=f'agent-{msg.id}.txt',
    )


async def _memory(
    msg: Message,
    agentic: AgenticRuntime,
    query: str,
) -> None:
    if not query:
        await msg.edit(
            '<b>Usage:</b> <code>.agent memory &lt;query&gt;</code>',
            parse_mode=ParseMode.HTML,
        )
        return
    ok, reason = await agentic.require_ollama()
    if not ok:
        await msg.edit(
            '<b>Agent unavailable:</b> local Ollama is required. '
            f'<code>{escape(reason)}</code>',
            parse_mode=ParseMode.HTML,
        )
        return
    matches = await agentic.storage.search_messages(
        query,
        chat_id=msg.chat.id,
        limit=agentic.settings.search_limit,
    )
    if not matches:
        await msg.edit(
            '<b>Agent memory:</b> no matches.',
            parse_mode=ParseMode.HTML,
        )
        return
    context = '\n'.join(
        f'- {item["sender"]}: {item["normalized_text"]}'
        for item in matches
    )
    try:
        result = await agentic.ollama.chat(
            [
                {
                    'role': 'user',
                    'content': (
                        'Answer using only these stored Telegram '
                        f'messages:\n{context}\n\nQuestion:\n{query}'
                    ),
                }
            ],
            model=await agentic.chat_model(),
            system=SYSTEM_PROMPT,
        )
    except Exception as e:
        await msg.edit(
            f'<b>Agent error:</b> <code>{escape(str(e))}</code>',
            parse_mode=ParseMode.HTML,
        )
        return
    html = (
        f'<b>Agent memory answer:</b>\n'
        f'{escape(result.content or "(empty)")}'
    )
    await utils.edit_or_send_as_text_file(
        msg,
        html,
        file_text=result.content,
        filename=f'agent-memory-{msg.id}.txt',
    )


async def _context(
    msg: Message,
    agentic: AgenticRuntime,
    rest: str,
) -> None:
    try:
        limit = int(rest) if rest else 20
    except ValueError:
        limit = 20
    limit = max(1, min(limit, 80))
    items = await agentic.storage.recent_messages(msg.chat.id, limit)
    if not items:
        await msg.edit(
            '<b>Agent context:</b> empty.',
            parse_mode=ParseMode.HTML,
        )
        return
    lines = ['<b>Agent context</b>']
    file_lines = ['Agent context']
    for item in items:
        sender = escape(str(item.get('sender') or 'Unknown'))
        text = escape(_truncate(item.get('normalized_text') or ''))
        mid = item.get('message_id')
        lines.append(f'<code>{mid}</code> <b>{sender}:</b> {text}')
        file_lines.append(
            f'{mid} {item.get("sender")}: '
            f'{item.get("normalized_text")}'
        )
    await utils.edit_or_send_as_text_file(
        msg,
        '\n'.join(lines),
        file_text='\n'.join(file_lines),
        filename=f'agent-context-{msg.id}.txt',
    )
