from html import escape

from pyrogram import Client, filters
from pyrogram.enums import ParseMode
from pyrogram.types import Message
from redis.asyncio import Redis

from src.bot.tools import utils
from src.bot.tools.router import Router
from src.services.codex import CodexClient


ai_router = Router('ai')
ai_router.router_filters = filters.me

SYSTEM_PROMPT = (
    'You are a helpful AI assistant integrated into a '
    'Telegram userbot. Keep responses concise and useful. '
    'Use plain text formatting suitable for Telegram.'
)

_chat_histories: dict[int, list[dict[str, str]]] = {}
MAX_HISTORY = 20
AI_MODEL_KEY = 'settings:ai:model'
AI_EFFORT_KEY = 'settings:ai:effort'
ALLOWED_EFFORTS = {
    'minimal',
    'low',
    'medium',
    'high',
    'xhigh',
}


@ai_router.message(filters.command('ai', prefixes='.'))
async def ai_ask(
    msg: Message,
    codex: CodexClient,
    redis: Redis,
):
    """Single question to Codex."""
    prompt = _extract_prompt(msg)
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
        model, effort, _, _ = await _get_ai_preferences(
            redis, codex
        )
        response = await codex.generate(
            prompt=prompt,
            system_instruction=SYSTEM_PROMPT,
            session_id=f'tg:{msg.chat.id}:ask',
            model=model,
            reasoning_effort=effort,
        )
        text, file_text = _build_ai_response(
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
    prompt = _extract_prompt(msg)
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
        model, effort, _, _ = await _get_ai_preferences(
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
        text, file_text = _build_ai_response(
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


@ai_router.message(filters.command('aimodel', prefixes='.'))
async def ai_model_info(
    msg: Message,
    codex: CodexClient,
    redis: Redis,
):
    """Show current AI model and effort."""
    model, effort, model_source, effort_source = (
        await _get_ai_preferences(redis, codex)
    )
    await msg.edit(
        '<b>AI Settings</b>\n'
        f'<b>Model:</b> <code>{escape(model)}</code> '
        f'({escape(model_source)})\n'
        f'<b>Effort:</b> <code>{escape(effort)}</code> '
        f'({escape(effort_source)})',
        parse_mode=ParseMode.HTML,
    )


@ai_router.message(filters.command('codexmodel', prefixes='.'))
async def codex_model(
    msg: Message,
    codex: CodexClient,
    redis: Redis,
):
    """Show or update the current Codex model."""
    model = _extract_prompt(msg)
    if not model:
        current_model, _, model_source, _ = (
            await _get_ai_preferences(redis, codex)
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
    _, effort, _, _ = await _get_ai_preferences(redis, codex)
    await msg.edit(
        '<b>AI Settings Updated</b>\n'
        f'<b>Model:</b> <code>{escape(model)}</code>\n'
        f'<b>Effort:</b> <code>{escape(effort)}</code>',
        parse_mode=ParseMode.HTML,
    )


@ai_router.message(filters.command('codexeffort', prefixes='.'))
async def codex_effort(
    msg: Message,
    codex: CodexClient,
    redis: Redis,
):
    """Show or update the current Codex reasoning effort."""
    effort = _extract_prompt(msg).lower()
    if not effort:
        _, current_effort, _, effort_source = (
            await _get_ai_preferences(redis, codex)
        )
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
    model, _, _, _ = await _get_ai_preferences(redis, codex)
    await msg.edit(
        '<b>AI Settings Updated</b>\n'
        f'<b>Model:</b> <code>{escape(model)}</code>\n'
        f'<b>Effort:</b> <code>{escape(effort)}</code>',
        parse_mode=ParseMode.HTML,
    )


@ai_router.message(filters.command('codexreset', prefixes='.'))
async def codex_reset(
    msg: Message,
    codex: CodexClient,
    redis: Redis,
):
    """Reset Redis-backed AI settings to defaults."""
    await redis.delete(AI_MODEL_KEY, AI_EFFORT_KEY)
    model, effort, _, _ = await _get_ai_preferences(
        redis, codex
    )
    await msg.edit(
        '<b>AI Settings Reset</b>\n'
        f'<b>Model:</b> <code>{escape(model)}</code>\n'
        f'<b>Effort:</b> <code>{escape(effort)}</code>',
        parse_mode=ParseMode.HTML,
    )


TLDR_SYSTEM_PROMPT = (
    'You summarize Telegram chats. Produce a concise TL;DR '
    'in the same language the chat is mostly written in. '
    'Group by topics/threads if applicable. Use plain text '
    'with short bullet lines. Keep it under 12 lines.'
)
TRANSLATE_SYSTEM_PROMPT = (
    'You are a translator. Translate the user message to '
    'the requested target language. Output only the '
    'translation, with no commentary or quotes. Preserve '
    'tone and formatting.'
)


@ai_router.message(filters.command('tldr', prefixes='.'))
async def ai_tldr(
    msg: Message,
    codex: CodexClient,
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
            text = m.text or m.caption or ''
            text = text.strip()
            if not text:
                continue
            if text.startswith('.'):
                continue
            sender = m.from_user
            if sender is not None:
                name = (
                    (sender.first_name or '')
                    + (
                        ' ' + sender.last_name
                        if sender.last_name
                        else ''
                    )
                ).strip() or (sender.username or 'User')
            else:
                name = getattr(
                    m.sender_chat, 'title', 'Channel'
                )
            history.append(f'{name}: {text}')
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

        model, effort, _, _ = await _get_ai_preferences(
            redis, codex
        )
        response = await codex.generate(
            prompt=(
                'Summarize this Telegram chat transcript:\n\n'
                + transcript
            ),
            system_instruction=TLDR_SYSTEM_PROMPT,
            session_id=f'tg:{msg.chat.id}:tldr',
            model=model,
            reasoning_effort=effort,
        )
        text = (
            f'<b>📝 TLDR ({len(history)} msgs)</b>\n\n'
            f'{escape(response)}'
        )
        file_text = (
            f'TLDR ({len(history)} msgs)\n\n{response}'
        )
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


@ai_router.message(
    filters.command(['tr', 'translate'], prefixes='.')
)
async def ai_translate(
    msg: Message,
    codex: CodexClient,
    redis: Redis,
):
    """Translate text. .tr [lang] <text|reply>."""
    text = msg.text or ''
    parts = text.split(maxsplit=2)

    target = 'English'
    body = ''
    if len(parts) >= 2 and len(parts[1]) <= 12 and (
        parts[1].isalpha() or '-' in parts[1]
    ):
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
        model, effort, _, _ = await _get_ai_preferences(
            redis, codex
        )
        response = await codex.generate(
            prompt=(
                f'Target language: {target}\n\n'
                f'Source text:\n{body}'
            ),
            system_instruction=TRANSLATE_SYSTEM_PROMPT,
            session_id=f'tg:{msg.chat.id}:tr',
            model=model,
            reasoning_effort=effort,
        )
        out = (
            f'<b>🌐 {escape(target)}</b>\n\n'
            f'{escape(response)}'
        )
        await utils.edit_or_send_as_text_file(
            msg,
            out,
            file_text=f'[{target}]\n{response}',
            filename=f'translate-{msg.id}.txt',
        )
    except Exception as e:
        await msg.edit(
            f'<b>Translate error:</b> '
            f'<code>{escape(str(e))}</code>',
            parse_mode=ParseMode.HTML,
        )


@ai_router.message(filters.command('codexlogin', prefixes='.'))
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


@ai_router.message(filters.command('codexauth', prefixes='.'))
async def codex_auth(
    msg: Message,
    codex: CodexClient,
    redis: Redis,
):
    """Complete Codex OAuth flow."""
    authorization_input = _extract_prompt(msg)
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
        credentials = await codex.complete_oauth(
            authorization_input
        )
        model, effort, _, _ = await _get_ai_preferences(
            redis, codex
        )
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


@ai_router.message(filters.command('codexstatus', prefixes='.'))
async def codex_status(
    msg: Message,
    codex: CodexClient,
    redis: Redis,
):
    """Show Codex auth status."""
    status = await codex.get_auth_status()
    model, effort, model_source, effort_source = (
        await _get_ai_preferences(redis, codex)
    )
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


@ai_router.message(filters.command('codexlogout', prefixes='.'))
async def codex_logout(msg: Message, codex: CodexClient):
    """Clear Codex auth state."""
    await codex.logout()
    await msg.edit(
        '<b>Codex OAuth:</b> cleared.',
        parse_mode=ParseMode.HTML,
    )


def _extract_prompt(msg: Message) -> str:
    """Extract prompt text from message (after command)."""
    text = msg.text or ''
    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        if msg.reply_to_message:
            return msg.reply_to_message.text or ''
        return ''
    prompt = parts[1].strip()
    if msg.reply_to_message and msg.reply_to_message.text:
        prompt += '\n\n' + msg.reply_to_message.text
    return prompt


def _build_ai_response(
    *,
    prompt_title: str,
    prompt: str,
    response: str,
) -> tuple[str, str]:
    html_text = (
        f'<b>{escape(prompt_title)}:</b> {escape(prompt)}\n\n'
        f'<b>AI:</b>\n{escape(response)}'
    )
    plain_text = (
        f'{prompt_title}:\n{prompt}\n\n'
        f'AI:\n{response}'
    )
    return html_text, plain_text


async def _get_ai_preferences(
    redis: Redis,
    codex: CodexClient,
) -> tuple[str, str, str, str]:
    raw_model = await redis.get(AI_MODEL_KEY)
    raw_effort = await redis.get(AI_EFFORT_KEY)

    model = (
        raw_model.decode('utf-8').strip()
        if raw_model
        else codex.model
    )
    effort = (
        raw_effort.decode('utf-8').strip().lower()
        if raw_effort
        else codex.reasoning_effort
    )

    if effort not in ALLOWED_EFFORTS:
        effort = codex.reasoning_effort

    model_source = 'redis' if raw_model else 'default'
    effort_source = 'redis' if raw_effort else 'default'
    return model, effort, model_source, effort_source
