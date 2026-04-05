from html import escape

from pyrogram import filters
from pyrogram.enums import ParseMode
from pyrogram.types import Message

from ..tools.router import Router
from ...services.codex import CodexClient


ai_router = Router('ai')
ai_router.router_filters = filters.me

SYSTEM_PROMPT = (
    'You are a helpful AI assistant integrated into a '
    'Telegram userbot. Keep responses concise and useful. '
    'Use plain text formatting suitable for Telegram.'
)

_chat_histories: dict[int, list[dict[str, str]]] = {}
MAX_HISTORY = 20


@ai_router.message(
    filters.command('Р°С–', prefixes='.')
    | filters.command('ai', prefixes='.')
)
async def ai_ask(msg: Message, codex: CodexClient):
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
        response = await codex.generate(
            prompt=prompt,
            system_instruction=SYSTEM_PROMPT,
            session_id=f'tg:{msg.chat.id}:ask',
        )
        text = (
            f'<b>Q:</b> {escape(prompt)}\n\n'
            f'<b>AI:</b>\n{escape(response)}'
        )
        await msg.edit(text, parse_mode=ParseMode.HTML)
    except Exception as e:
        await msg.edit(
            f'<b>AI Error:</b> <code>{escape(str(e))}</code>',
            parse_mode=ParseMode.HTML,
        )


@ai_router.message(
    filters.command('С‡Р°С‚', prefixes='.')
    | filters.command('chat', prefixes='.')
)
async def ai_chat(msg: Message, codex: CodexClient):
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
        response = await codex.chat(
            messages=history,
            system_instruction=SYSTEM_PROMPT,
            session_id=f'tg:{chat_id}:chat',
        )
        history.append({'role': 'assistant', 'text': response})
        text = (
            f'<b>You:</b> {escape(prompt)}\n\n'
            f'<b>AI:</b>\n{escape(response)}'
        )
        await msg.edit(text, parse_mode=ParseMode.HTML)
    except Exception as e:
        history.pop()
        await msg.edit(
            f'<b>AI Error:</b> <code>{escape(str(e))}</code>',
            parse_mode=ParseMode.HTML,
        )


@ai_router.message(
    filters.command('С‡Р°С‚РєР»С–СЂ', prefixes='.')
    | filters.command('chatclear', prefixes='.')
)
async def ai_chat_clear(msg: Message):
    """Clear chat history for current chat."""
    chat_id = msg.chat.id
    _chat_histories.pop(chat_id, None)
    await msg.edit(
        '<b>AI:</b> Chat history cleared.',
        parse_mode=ParseMode.HTML,
    )


@ai_router.message(
    filters.command('Р°С–РјРѕРґРµР»СЊ', prefixes='.')
    | filters.command('aimodel', prefixes='.')
)
async def ai_model_info(msg: Message, codex: CodexClient):
    """Show current AI model."""
    await msg.edit(
        f'<b>AI Model:</b> <code>{escape(codex.model)}</code>',
        parse_mode=ParseMode.HTML,
    )


@ai_router.message(filters.command('codexlogin', prefixes='.'))
async def codex_login(msg: Message, codex: CodexClient):
    """Start Codex OAuth flow."""
    url = codex.begin_oauth()
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
async def codex_auth(msg: Message, codex: CodexClient):
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
        await msg.edit(
            '<b>Codex OAuth:</b> connected.\n'
            f'<b>Model:</b> <code>{escape(codex.model)}</code>\n'
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
async def codex_status(msg: Message, codex: CodexClient):
    """Show Codex auth status."""
    status = codex.get_auth_status()
    if not status['authenticated']:
        pending = 'yes' if status['pending'] else 'no'
        await msg.edit(
            '<b>Codex OAuth:</b> not connected.\n'
            f'<b>Pending flow:</b> <code>{pending}</code>\n'
            f'<b>Store:</b> <code>{escape(status["credentials_path"])}</code>',
            parse_mode=ParseMode.HTML,
        )
        return

    await msg.edit(
        '<b>Codex OAuth:</b> connected.\n'
        f'<b>Model:</b> <code>{escape(codex.model)}</code>\n'
        f'<b>Account:</b> <code>{escape(str(status["account_id"]))}</code>\n'
        f'<b>Expires:</b> <code>{escape(str(status["expires"]))}</code>\n'
        f'<b>Store:</b> <code>{escape(status["credentials_path"])}</code>',
        parse_mode=ParseMode.HTML,
    )


@ai_router.message(filters.command('codexlogout', prefixes='.'))
async def codex_logout(msg: Message, codex: CodexClient):
    """Clear Codex auth state."""
    codex.logout()
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
