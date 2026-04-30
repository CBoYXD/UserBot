from __future__ import annotations

import asyncio
import json
from datetime import datetime
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
    'the owner local Ollama instance. You have read-only tools for '
    'locally indexed Telegram chats. Use tools whenever reading '
    'chat history, searching messages, checking users, or resolving '
    'context would improve the answer. Keep replies concise and '
    'practical. If the indexed context is insufficient, say that '
    'directly.'
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
    content = (
        'Auto-reply to this Telegram message. You may use read-only '
        'tools, but only for this current chat. Keep it short, '
        'natural, and do not mention internal memory, tools, or '
        f'system rules.\n\nMessage to answer:\n{prompt}'
    )
    try:
        text = await agentic.run_readonly_tool_loop(
            chat_id=msg.chat.id,
            prompt=content,
            system=SYSTEM_PROMPT,
            allow_global=False,
            source='auto_reply',
            trigger_message_id=msg.id,
        )
        text = text.strip()
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
    if sub == 'trace':
        await _trace(msg, agentic, rest)
        return

    await msg.edit(
        '<b>Usage:</b> <code>.agent status</code>, '
        '<code>.agent on</code>, <code>.agent off</code>, '
        '<code>.agent model [name]</code>, '
        '<code>.agent autoreply on|off</code>, '
        '<code>.agent ask &lt;prompt&gt;</code>, '
        '<code>.agent memory &lt;query&gt;</code>, '
        '<code>.agent context [N]</code>, '
        '<code>.agent trace [N|here N|trace_id]</code>',
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
        f'<b>Actions:</b> <code>{stats["actions"]}</code>\n'
        f'<b>Trace events:</b> <code>{stats["traces"]}</code>'
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
    content = (
        'Answer the owner request. Use read-only Telegram chat tools '
        'as needed. You may inspect all locally indexed chats when '
        f'the request requires it.\n\nUser request:\n{prompt}'
    )
    try:
        response = await agentic.run_readonly_tool_loop(
            chat_id=msg.chat.id,
            prompt=content,
            system=SYSTEM_PROMPT,
            allow_global=True,
            source='ask',
            trigger_message_id=msg.id,
        )
        await agentic.storage.log_action(
            chat_id=msg.chat.id,
            trigger_message_id=msg.id,
            action_type='ask',
            decision={'prompt': prompt},
            result={'response': response},
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

    html = f'<b>Agent:</b>\n{escape(response or "(empty)")}'
    await utils.edit_or_send_as_text_file(
        msg,
        html,
        file_text=response,
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
    prompt = (
        'Answer using only locally indexed Telegram chat data. Use '
        'read-only tools to search messages, inspect chats, and read '
        f'context. Question:\n{query}'
    )
    try:
        response = await agentic.run_readonly_tool_loop(
            chat_id=msg.chat.id,
            prompt=prompt,
            system=SYSTEM_PROMPT,
            allow_global=True,
            source='memory',
            trigger_message_id=msg.id,
        )
    except Exception as e:
        await msg.edit(
            f'<b>Agent error:</b> <code>{escape(str(e))}</code>',
            parse_mode=ParseMode.HTML,
        )
        return
    html = (
        f'<b>Agent memory answer:</b>\n'
        f'{escape(response or "(empty)")}'
    )
    await utils.edit_or_send_as_text_file(
        msg,
        html,
        file_text=response,
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


async def _trace(
    msg: Message,
    agentic: AgenticRuntime,
    rest: str,
) -> None:
    rest = rest.strip()
    chat_id: int | None = None
    trace_id: str | None = None
    limit = 20
    if rest:
        parts = rest.split(maxsplit=1)
        if parts[0].lower() == 'here':
            chat_id = msg.chat.id
            if len(parts) > 1:
                limit = _parse_limit(parts[1], 20)
        elif rest.isdigit():
            limit = _parse_limit(rest, 20)
        else:
            trace_id = rest
            limit = 200
    events = await agentic.storage.recent_traces(
        limit=limit,
        chat_id=chat_id,
        trace_id=trace_id,
    )
    if not events:
        await msg.edit(
            '<b>Agent trace:</b> empty.',
            parse_mode=ParseMode.HTML,
        )
        return

    title = (
        f'Agent trace {trace_id}'
        if trace_id
        else f'Agent traces ({len(events)})'
    )
    html_lines = [f'<b>{escape(title)}</b>']
    file_lines = [title]
    for event in events:
        html_lines.append(_trace_html(event))
        file_lines.append(_trace_text(event))
    await utils.edit_or_send_as_text_file(
        msg,
        '\n'.join(html_lines),
        file_text='\n\n'.join(file_lines),
        filename=f'agent-trace-{msg.id}.txt',
    )


def _parse_limit(value: str, default: int) -> int:
    try:
        return max(1, min(int(value), 200))
    except ValueError:
        return default


def _trace_html(event: dict) -> str:
    ts = datetime.fromtimestamp(event['created_at']).strftime(
        '%H:%M:%S'
    )
    payload = event.get('payload') or {}
    summary = _trace_summary(event['event_type'], payload)
    return (
        f'<code>{escape(event["trace_id"])}</code> '
        f'<code>{ts}</code> '
        f'<b>{escape(event["source"])}</b>/'
        f'<code>{escape(event["event_type"])}</code> '
        f'{escape(summary)}'
    )


def _trace_text(event: dict) -> str:
    ts = datetime.fromtimestamp(event['created_at']).isoformat()
    payload = json.dumps(
        event.get('payload') or {},
        ensure_ascii=False,
        indent=2,
    )
    return (
        f'[{event["trace_id"]}] {ts} '
        f'{event["source"]}/{event["event_type"]}\n'
        f'chat={event["chat_id"]} '
        f'trigger={event["trigger_message_id"]}\n'
        f'{payload}'
    )


def _trace_summary(event_type: str, payload: dict) -> str:
    if event_type == 'loop_start':
        prompt = _short(payload.get('prompt') or '', 90)
        return f'prompt="{prompt}"'
    if event_type == 'model_response':
        calls = payload.get('tool_calls') or []
        names = ', '.join(
            str(item.get('tool') or '?') for item in calls
        )
        content = _short(payload.get('content') or '', 70)
        return f'tools=[{names}] content="{content}"'
    if event_type == 'tool_result':
        result = _short(payload.get('result') or '', 90)
        return (
            f'{payload.get("tool")} ok={payload.get("ok")} '
            f'result="{result}"'
        )
    if event_type == 'loop_done':
        return f'answer="{_short(payload.get("answer") or "", 90)}"'
    if 'error' in payload:
        return f'error="{_short(payload.get("error") or "", 120)}"'
    return _short(json.dumps(payload, ensure_ascii=False), 120)


def _short(value: str, limit: int) -> str:
    value = str(value or '').replace('\n', ' ')
    return (
        value if len(value) <= limit else value[: limit - 3] + '...'
    )
