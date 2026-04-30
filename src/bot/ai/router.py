import io
from html import escape

from pyrogram import Client, filters
from pyrogram.enums import ParseMode
from pyrogram.types import Message
from redis.asyncio import Redis

from src.core.acl import cmd
from src.core.router import Router
from src.bot import utils
from src.bot.ai.helpers import (
    build_ai_response,
    extract_display_prompt,
    extract_prompt,
)
from src.bot.ai.prefs import (
    AI_EFFORT_KEY,
    AI_MODEL_KEY,
    ALLOWED_EFFORTS,
    get_ai_preferences,
)
from src.bot.ai.prompts import (
    SYSTEM_PROMPT,
    TLDR_SYSTEM_PROMPT,
    TRANSLATE_SYSTEM_PROMPT,
)
from src.bot.ai.tools import build_ai_tools
from src.services.agentic import AgenticRuntime
from src.services.codex import CodexClient
from src.services.mermaid import MermaidService


ai_router = Router('ai')


_chat_histories: dict[int, list[dict[str, str]]] = {}
MAX_HISTORY = 20


async def _flush_images(
    client: Client,
    msg: Message,
    images: list[tuple[bytes, str | None]],
) -> None:
    target_id = (
        msg.reply_to_message.id if msg.reply_to_message else msg.id
    )
    for png, caption in images:
        bio = io.BytesIO(png)
        bio.name = 'mermaid.png'
        await client.send_photo(
            chat_id=msg.chat.id,
            photo=bio,
            caption=caption,
            reply_to_message_id=target_id,
        )


def _ollama_messages(
    messages: list[dict[str, str]],
) -> list[dict[str, str]]:
    return [
        {
            'role': item['role'],
            'content': item.get('content') or item.get('text') or '',
        }
        for item in messages
    ]


async def _codex_available(codex: CodexClient) -> bool:
    try:
        status = await codex.get_auth_status()
    except Exception:
        return False
    return bool(status.get('authenticated'))


async def _ollama_generate(
    agentic: AgenticRuntime,
    *,
    messages: list[dict[str, str]],
    system_instruction: str | None,
    model: str | None = None,
) -> str:
    if model is None:
        ok, reason = await agentic.require_ollama()
        model = await agentic.chat_model()
    else:
        ok, reason = await agentic.ollama.health(model)
    if not ok:
        raise RuntimeError(f'Local Ollama unavailable: {reason}')

    result = await agentic.ollama.chat(
        _ollama_messages(messages),
        model=model,
        system=system_instruction,
    )
    if not result.content:
        raise RuntimeError('Local Ollama returned an empty response')
    return result.content


async def _chat_with_fallback(
    *,
    codex: CodexClient,
    agentic: AgenticRuntime,
    redis: Redis,
    messages: list[dict[str, str]],
    system_instruction: str | None,
    session_id: str,
    tools=None,
    dispatch=None,
) -> tuple[str, str]:
    codex_error: Exception | None = None
    if await _codex_available(codex):
        try:
            model, effort, _, _ = await get_ai_preferences(
                redis, codex
            )
            if tools is not None and dispatch is not None:
                response = await codex.chat_with_tools(
                    messages=messages,
                    tools=tools,
                    dispatch=dispatch,
                    system_instruction=system_instruction,
                    session_id=session_id,
                    model=model,
                    reasoning_effort=effort,
                )
            else:
                response = await codex.chat(
                    messages=messages,
                    system_instruction=system_instruction,
                    session_id=session_id,
                    model=model,
                    reasoning_effort=effort,
                )
            return response, 'codex'
        except Exception as e:
            codex_error = e

    try:
        response = await _ollama_generate(
            agentic,
            messages=messages,
            system_instruction=system_instruction,
        )
    except Exception as e:
        if codex_error is not None:
            raise RuntimeError(
                f'Codex failed: {codex_error}; Ollama failed: {e}'
            ) from e
        raise
    return response, 'ollama'


async def _generate_with_fallback(
    *,
    codex: CodexClient,
    agentic: AgenticRuntime,
    redis: Redis,
    prompt: str,
    system_instruction: str | None,
    session_id: str,
    ollama_model: str | None = None,
) -> tuple[str, str]:
    messages = [{'role': 'user', 'text': prompt}]
    codex_error: Exception | None = None
    if await _codex_available(codex):
        try:
            model, effort, _, _ = await get_ai_preferences(
                redis, codex
            )
            response = await codex.generate(
                prompt=prompt,
                system_instruction=system_instruction,
                session_id=session_id,
                model=model,
                reasoning_effort=effort,
            )
            return response, 'codex'
        except Exception as e:
            codex_error = e

    try:
        response = await _ollama_generate(
            agentic,
            messages=messages,
            system_instruction=system_instruction,
            model=ollama_model,
        )
    except Exception as e:
        if codex_error is not None:
            raise RuntimeError(
                f'Codex failed: {codex_error}; Ollama failed: {e}'
            ) from e
        raise
    return response, 'ollama'


async def _translate_ollama_model(
    agentic: AgenticRuntime,
) -> str | None:
    try:
        return await agentic.ollama.resolve_model('translategemma')
    except Exception:
        return None


# ---------- chat ----------


@ai_router.message(cmd('ai', 'ai', 'ші'))
async def ai_ask(
    msg: Message,
    client: Client,
    codex: CodexClient,
    agentic: AgenticRuntime,
    redis: Redis,
    mermaid: MermaidService,
):
    """Single question to Codex, falling back to local Ollama."""
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

    images: list[tuple[bytes, str | None]] = []

    async def on_image(png: bytes, caption: str | None) -> None:
        images.append((png, caption))

    try:
        tools, dispatch = build_ai_tools(mermaid, on_image)
        response, _ = await _chat_with_fallback(
            codex=codex,
            agentic=agentic,
            redis=redis,
            messages=[{'role': 'user', 'text': prompt}],
            system_instruction=SYSTEM_PROMPT,
            session_id=f'tg:{msg.chat.id}:ask',
            tools=tools,
            dispatch=dispatch,
        )
        text, file_text = build_ai_response(
            prompt_title='Q',
            prompt=extract_display_prompt(msg),
            response=response,
        )
        await utils.edit_or_send_as_text_file(
            msg,
            text,
            file_text=file_text,
            filename=f'ai-response-{msg.id}.txt',
        )
        await _flush_images(client, msg, images)
    except Exception as e:
        await msg.edit(
            f'<b>AI Error:</b> <code>{escape(str(e))}</code>',
            parse_mode=ParseMode.HTML,
        )


@ai_router.message(cmd('ai', 'chat', 'чат'))
async def ai_chat(
    msg: Message,
    client: Client,
    codex: CodexClient,
    agentic: AgenticRuntime,
    redis: Redis,
    mermaid: MermaidService,
):
    """Chat with context memory. Codex first, local Ollama fallback."""
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

    images: list[tuple[bytes, str | None]] = []

    async def on_image(png: bytes, caption: str | None) -> None:
        images.append((png, caption))

    try:
        tools, dispatch = build_ai_tools(mermaid, on_image)
        response, _ = await _chat_with_fallback(
            codex=codex,
            agentic=agentic,
            redis=redis,
            messages=history,
            system_instruction=SYSTEM_PROMPT,
            session_id=f'tg:{chat_id}:chat',
            tools=tools,
            dispatch=dispatch,
        )
        history.append({'role': 'assistant', 'text': response})
        text, file_text = build_ai_response(
            prompt_title='You',
            prompt=extract_display_prompt(msg),
            response=response,
        )
        await utils.edit_or_send_as_text_file(
            msg,
            text,
            file_text=file_text,
            filename=f'chat-response-{msg.id}.txt',
        )
        await _flush_images(client, msg, images)
    except Exception as e:
        history.pop()
        await msg.edit(
            f'<b>AI Error:</b> <code>{escape(str(e))}</code>',
            parse_mode=ParseMode.HTML,
        )


@ai_router.message(cmd('ai', 'chatclear'))
async def ai_chat_clear(msg: Message):
    """Clear chat history for current chat."""
    chat_id = msg.chat.id
    _chat_histories.pop(chat_id, None)
    await msg.edit(
        '<b>AI:</b> Chat history cleared.',
        parse_mode=ParseMode.HTML,
    )


# ---------- codex settings ----------


@ai_router.message(
    filters.me & filters.command('aimodel', prefixes='.')
)
async def ai_model_info(
    msg: Message,
    codex: CodexClient,
    redis: Redis,
):
    """Show current AI model and effort."""
    (
        model,
        effort,
        model_source,
        effort_source,
    ) = await get_ai_preferences(redis, codex)
    await msg.edit(
        '<b>AI Settings</b>\n'
        f'<b>Model:</b> <code>{escape(model)}</code> '
        f'({escape(model_source)})\n'
        f'<b>Effort:</b> <code>{escape(effort)}</code> '
        f'({escape(effort_source)})',
        parse_mode=ParseMode.HTML,
    )


@ai_router.message(
    filters.me & filters.command('codexmodel', prefixes='.')
)
async def codex_model(
    msg: Message,
    codex: CodexClient,
    redis: Redis,
):
    """Show or update the current Codex model."""
    model = extract_prompt(msg)
    if not model:
        current_model, _, model_source, _ = await get_ai_preferences(
            redis, codex
        )
        await msg.edit(
            '<b>Codex model:</b> '
            f'<code>{escape(current_model)}</code> '
            f'({escape(model_source)})',
            parse_mode=ParseMode.HTML,
        )
        return

    model = model.strip()
    await redis.set(AI_MODEL_KEY, model)
    _, effort, _, _ = await get_ai_preferences(redis, codex)
    await msg.edit(
        '<b>AI Settings Updated</b>\n'
        f'<b>Model:</b> <code>{escape(model)}</code>\n'
        f'<b>Effort:</b> <code>{escape(effort)}</code>',
        parse_mode=ParseMode.HTML,
    )


@ai_router.message(
    filters.me & filters.command('codexeffort', prefixes='.')
)
async def codex_effort(
    msg: Message,
    codex: CodexClient,
    redis: Redis,
):
    """Show or update the current Codex reasoning effort."""
    effort = extract_prompt(msg).lower()
    if not effort:
        (
            _,
            current_effort,
            _,
            effort_source,
        ) = await get_ai_preferences(redis, codex)
        allowed = ', '.join(sorted(ALLOWED_EFFORTS))
        await msg.edit(
            '<b>Codex effort:</b> '
            f'<code>{escape(current_effort)}</code> '
            f'({escape(effort_source)})\n'
            f'<b>Allowed:</b> <code>{escape(allowed)}</code>',
            parse_mode=ParseMode.HTML,
        )
        return

    if effort not in ALLOWED_EFFORTS:
        allowed = ', '.join(sorted(ALLOWED_EFFORTS))
        await msg.edit(
            '<b>Invalid effort.</b>\n'
            f'<b>Allowed:</b> <code>{escape(allowed)}</code>',
            parse_mode=ParseMode.HTML,
        )
        return

    await redis.set(AI_EFFORT_KEY, effort)
    model, _, _, _ = await get_ai_preferences(redis, codex)
    await msg.edit(
        '<b>AI Settings Updated</b>\n'
        f'<b>Model:</b> <code>{escape(model)}</code>\n'
        f'<b>Effort:</b> <code>{escape(effort)}</code>',
        parse_mode=ParseMode.HTML,
    )


@ai_router.message(
    filters.me & filters.command('codexreset', prefixes='.')
)
async def codex_reset(
    msg: Message,
    codex: CodexClient,
    redis: Redis,
):
    """Reset Redis-backed AI settings to defaults."""
    await redis.delete(AI_MODEL_KEY, AI_EFFORT_KEY)
    model, effort, _, _ = await get_ai_preferences(redis, codex)
    await msg.edit(
        '<b>AI Settings Reset</b>\n'
        f'<b>Model:</b> <code>{escape(model)}</code>\n'
        f'<b>Effort:</b> <code>{escape(effort)}</code>',
        parse_mode=ParseMode.HTML,
    )


@ai_router.message(
    filters.me & filters.command('codexlogin', prefixes='.')
)
async def codex_login(msg: Message, codex: CodexClient):
    """Start Codex OAuth flow."""
    url = await codex.begin_oauth()
    await msg.edit(
        '<b>Codex OAuth</b>\n\n'
        '1. Open the URL below in your browser.\n'
        '2. Sign in with ChatGPT/Codex.\n'
        '3. Copy the full redirect URL from the address bar.\n'
        '4. Send <code>.codexauth &lt;redirect_url&gt;</code>\n\n'
        f'<code>{escape(url)}</code>',
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
    )


@ai_router.message(
    filters.me & filters.command('codexauth', prefixes='.')
)
async def codex_auth(
    msg: Message,
    codex: CodexClient,
    redis: Redis,
):
    """Complete Codex OAuth flow."""
    authorization_input = extract_prompt(msg)
    if not authorization_input:
        await msg.edit(
            '<b>Usage:</b> <code>.codexauth '
            'http://localhost:1455/auth/callback?code=...</code>',
            parse_mode=ParseMode.HTML,
        )
        return

    await msg.edit(
        '<b>Codex OAuth:</b> <i>Completing sign-in...</i>',
        parse_mode=ParseMode.HTML,
    )
    try:
        credentials = await codex.complete_oauth(authorization_input)
        model, effort, _, _ = await get_ai_preferences(redis, codex)
        await msg.edit(
            '<b>Codex OAuth:</b> connected.\n'
            f'<b>Model:</b> <code>{escape(model)}</code>\n'
            f'<b>Effort:</b> <code>{escape(effort)}</code>\n'
            f'<b>Account:</b> <code>{escape(credentials["account_id"])}</code>\n'
            f'<b>Expires:</b> <code>{escape(str(credentials["expires"]))}</code>',
            parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        await msg.edit(
            f'<b>Codex OAuth Error:</b> <code>{escape(str(e))}</code>',
            parse_mode=ParseMode.HTML,
        )


@ai_router.message(
    filters.me & filters.command('codexstatus', prefixes='.')
)
async def codex_status(
    msg: Message,
    codex: CodexClient,
    redis: Redis,
):
    """Show Codex auth status."""
    status = await codex.get_auth_status()
    (
        model,
        effort,
        model_source,
        effort_source,
    ) = await get_ai_preferences(redis, codex)
    if not status['authenticated']:
        pending = 'yes' if status['pending'] else 'no'
        await msg.edit(
            '<b>Codex OAuth:</b> not connected.\n'
            f'<b>Pending flow:</b> <code>{pending}</code>\n'
            f'<b>Model:</b> <code>{escape(model)}</code> '
            f'({escape(model_source)})\n'
            f'<b>Effort:</b> <code>{escape(effort)}</code> '
            f'({escape(effort_source)})\n'
            f'<b>Store:</b> <code>{escape(status["store_key"])}</code>',
            parse_mode=ParseMode.HTML,
        )
        return

    await msg.edit(
        '<b>Codex OAuth:</b> connected.\n'
        f'<b>Model:</b> <code>{escape(model)}</code> '
        f'({escape(model_source)})\n'
        f'<b>Effort:</b> <code>{escape(effort)}</code> '
        f'({escape(effort_source)})\n'
        f'<b>Account:</b> <code>{escape(str(status["account_id"]))}</code>\n'
        f'<b>Expires:</b> <code>{escape(str(status["expires"]))}</code>\n'
        f'<b>Store:</b> <code>{escape(status["store_key"])}</code>',
        parse_mode=ParseMode.HTML,
    )


@ai_router.message(
    filters.me & filters.command('codexlogout', prefixes='.')
)
async def codex_logout(msg: Message, codex: CodexClient):
    """Clear Codex auth state."""
    await codex.logout()
    await msg.edit(
        '<b>Codex OAuth:</b> cleared.',
        parse_mode=ParseMode.HTML,
    )


# ---------- tldr ----------


def _sender_name(m: Message) -> str:
    sender = m.from_user
    if sender is not None:
        full = (
            (sender.first_name or '')
            + (' ' + sender.last_name if sender.last_name else '')
        ).strip()
        return full or sender.username or 'User'
    return getattr(m.sender_chat, 'title', 'Channel')


@ai_router.message(cmd('ai', 'tldr', 'коротко'))
async def ai_tldr(
    msg: Message,
    codex: CodexClient,
    agentic: AgenticRuntime,
    redis: Redis,
    client: Client,
):
    """Summarize last N messages of the current chat."""
    raw = (msg.text or '').split(maxsplit=1)
    arg = raw[1].strip() if len(raw) > 1 else ''
    try:
        limit = int(arg) if arg else 50
    except ValueError:
        limit = 50
    limit = max(5, min(limit, 300))

    await msg.edit(
        f'<b>TLDR:</b> <i>reading last {limit} messages…</i>',
        parse_mode=ParseMode.HTML,
    )

    try:
        history: list[str] = []
        async for m in client.get_chat_history(
            chat_id=msg.chat.id, limit=limit + 5
        ):
            if m.id == msg.id:
                continue
            text = (m.text or m.caption or '').strip()
            if not text or text.startswith('.'):
                continue
            history.append(f'{_sender_name(m)}: {text}')
            if len(history) >= limit:
                break

        if not history:
            await msg.edit(
                '<b>TLDR:</b> no text messages to summarize.',
                parse_mode=ParseMode.HTML,
            )
            return

        history.reverse()
        transcript = '\n'.join(history)

        response, _ = await _generate_with_fallback(
            codex=codex,
            agentic=agentic,
            redis=redis,
            prompt=(
                'Summarize this Telegram chat transcript:\n\n'
                + transcript
            ),
            system_instruction=TLDR_SYSTEM_PROMPT,
            session_id=f'tg:{msg.chat.id}:tldr',
        )
        text = (
            f'<b>📝 TLDR ({len(history)} msgs)</b>\n\n'
            f'{escape(response)}'
        )
        file_text = f'TLDR ({len(history)} msgs)\n\n{response}'
        await utils.edit_or_send_as_text_file(
            msg,
            text,
            file_text=file_text,
            filename=f'tldr-{msg.id}.txt',
        )
    except Exception as e:
        await msg.edit(
            f'<b>TLDR error:</b> <code>{escape(str(e))}</code>',
            parse_mode=ParseMode.HTML,
        )


# ---------- translate ----------


def _looks_like_lang(token: str) -> bool:
    return len(token) <= 12 and (token.isalpha() or '-' in token)


def _parse_translate_args(msg: Message) -> tuple[str, str]:
    """Return (target_language, body)."""
    text = msg.text or ''
    parts = text.split(maxsplit=2)
    target = 'English'
    body = ''
    if len(parts) >= 2 and _looks_like_lang(parts[1]):
        target = parts[1]
        body = parts[2].strip() if len(parts) >= 3 else ''
    elif len(parts) >= 2:
        body = parts[1].strip()
        if len(parts) == 3:
            body = (body + ' ' + parts[2]).strip()
    if not body and msg.reply_to_message:
        body = (
            msg.reply_to_message.text
            or msg.reply_to_message.caption
            or ''
        ).strip()
    return target, body


@ai_router.message(cmd('ai', 'tr', 'translate', 'пер', 'переклад'))
async def ai_translate(
    msg: Message,
    codex: CodexClient,
    agentic: AgenticRuntime,
    redis: Redis,
):
    """Translate text. .tr [lang] <text|reply>."""
    target, body = _parse_translate_args(msg)
    if not body:
        await msg.edit(
            '<b>Usage:</b> '
            '<code>.tr [lang] &lt;text&gt;</code> '
            'or reply to a message.',
            parse_mode=ParseMode.HTML,
        )
        return

    await msg.edit(
        '<b>Translate:</b> <i>working…</i>',
        parse_mode=ParseMode.HTML,
    )

    try:
        response, _ = await _generate_with_fallback(
            codex=codex,
            agentic=agentic,
            redis=redis,
            prompt=(
                f'Target language: {target}\n\nSource text:\n{body}'
            ),
            system_instruction=TRANSLATE_SYSTEM_PROMPT,
            session_id=f'tg:{msg.chat.id}:tr',
            ollama_model=await _translate_ollama_model(agentic),
        )
        out = f'<b>🌐 {escape(target)}</b>\n\n{escape(response)}'
        await utils.edit_or_send_as_text_file(
            msg,
            out,
            file_text=f'[{target}]\n{response}',
            filename=f'translate-{msg.id}.txt',
        )
    except Exception as e:
        await msg.edit(
            f'<b>Translate error:</b> <code>{escape(str(e))}</code>',
            parse_mode=ParseMode.HTML,
        )
