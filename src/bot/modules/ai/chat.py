from html import escape

from pyrogram import filters
from pyrogram.enums import ParseMode
from pyrogram.types import Message
from redis.asyncio import Redis

from src.bot.modules.ai.helpers import build_ai_response, extract_prompt
from src.bot.modules.ai.prefs import get_ai_preferences
from src.bot.modules.ai.prompts import SYSTEM_PROMPT
from src.bot.modules.ai.router import ai_router
from src.bot.tools import utils
from src.services.codex import CodexClient


_chat_histories: dict[int, list[dict[str, str]]] = {}
MAX_HISTORY = 20


@ai_router.message(filters.command('ai', prefixes='.'))
async def ai_ask(
    msg: Message,
    codex: CodexClient,
    redis: Redis,
):
    """Single question to Codex."""
    prompt = extract_prompt(msg)
    if not prompt:
        await msg.edit(
            '<b>Usage:</b> <code>.ai your question</code>',
            parse_mode=ParseMode.HTML,
        )
        return

    await msg.edit(
        '<b>AI:</b> <i>Thinking...</i>',
        parse_mode=ParseMode.HTML,
    )

    try:
        model, effort, _, _ = await get_ai_preferences(
            redis, codex
        )
        response = await codex.generate(
            prompt=prompt,
            system_instruction=SYSTEM_PROMPT,
            session_id=f'tg:{msg.chat.id}:ask',
            model=model,
            reasoning_effort=effort,
        )
        text, file_text = build_ai_response(
            prompt_title='Q',
            prompt=prompt,
            response=response,
        )
        await utils.edit_or_send_as_text_file(
            msg,
            text,
            file_text=file_text,
            filename=f'ai-response-{msg.id}.txt',
        )
    except Exception as e:
        await msg.edit(
            f'<b>AI Error:</b> <code>{escape(str(e))}</code>',
            parse_mode=ParseMode.HTML,
        )


@ai_router.message(filters.command('chat', prefixes='.'))
async def ai_chat(
    msg: Message,
    codex: CodexClient,
    redis: Redis,
):
    """Chat with context memory per chat."""
    prompt = extract_prompt(msg)
    if not prompt:
        await msg.edit(
            '<b>Usage:</b> <code>.chat your message</code>',
            parse_mode=ParseMode.HTML,
        )
        return

    chat_id = msg.chat.id
    if chat_id not in _chat_histories:
        _chat_histories[chat_id] = []

    history = _chat_histories[chat_id]
    history.append({'role': 'user', 'text': prompt})
    if len(history) > MAX_HISTORY:
        history[:] = history[-MAX_HISTORY:]

    await msg.edit(
        '<b>AI:</b> <i>Thinking...</i>',
        parse_mode=ParseMode.HTML,
    )

    try:
        model, effort, _, _ = await get_ai_preferences(
            redis, codex
        )
        response = await codex.chat(
            messages=history,
            system_instruction=SYSTEM_PROMPT,
            session_id=f'tg:{chat_id}:chat',
            model=model,
            reasoning_effort=effort,
        )
        history.append({'role': 'assistant', 'text': response})
        text, file_text = build_ai_response(
            prompt_title='You',
            prompt=prompt,
            response=response,
        )
        await utils.edit_or_send_as_text_file(
            msg,
            text,
            file_text=file_text,
            filename=f'chat-response-{msg.id}.txt',
        )
    except Exception as e:
        history.pop()
        await msg.edit(
            f'<b>AI Error:</b> <code>{escape(str(e))}</code>',
            parse_mode=ParseMode.HTML,
        )


@ai_router.message(filters.command('chatclear', prefixes='.'))
async def ai_chat_clear(msg: Message):
    """Clear chat history for current chat."""
    chat_id = msg.chat.id
    _chat_histories.pop(chat_id, None)
    await msg.edit(
        '<b>AI:</b> Chat history cleared.',
        parse_mode=ParseMode.HTML,
    )
