from html import escape
from pyrogram import filters
from pyrogram.types import Message
from pyrogram.enums import ParseMode
from ..tools.router import Router
from ...services.openai import OpenAIClient


ai_router = Router('ai')
ai_router.router_filters = filters.me

SYSTEM_PROMPT = (
    'You are a helpful AI assistant integrated into a '
    'Telegram userbot. Keep responses concise and useful. '
    'Use plain text formatting suitable for Telegram.'
)

# Chat history per chat_id, stored in memory
_chat_histories: dict[int, list[dict]] = {}
MAX_HISTORY = 20


@ai_router.message(
    filters.command('аі', prefixes='.')
    | filters.command('ai', prefixes='.')
)
async def ai_ask(msg: Message, openai: OpenAIClient):
    """Single question to the AI model."""
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
        response = await openai.generate(
            prompt=prompt,
            system_instruction=SYSTEM_PROMPT,
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
    filters.command('чат', prefixes='.')
    | filters.command('chat', prefixes='.')
)
async def ai_chat(msg: Message, openai: OpenAIClient):
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

    # Trim history
    if len(history) > MAX_HISTORY:
        history[:] = history[-MAX_HISTORY:]

    await msg.edit(
        '<b>AI:</b> <i>Thinking...</i>',
        parse_mode=ParseMode.HTML,
    )

    try:
        response = await openai.chat(
            messages=history,
            system_instruction=SYSTEM_PROMPT,
        )
        history.append(
            {'role': 'assistant', 'text': response}
        )

        text = (
            f'<b>You:</b> {escape(prompt)}\n\n'
            f'<b>AI:</b>\n{escape(response)}'
        )
        await msg.edit(text, parse_mode=ParseMode.HTML)
    except Exception as e:
        history.pop()  # Remove failed user message
        await msg.edit(
            f'<b>AI Error:</b> <code>{escape(str(e))}</code>',
            parse_mode=ParseMode.HTML,
        )


@ai_router.message(
    filters.command('чатклір', prefixes='.')
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
    filters.command('аімодель', prefixes='.')
    | filters.command('aimodel', prefixes='.')
)
async def ai_model_info(
    msg: Message, openai: OpenAIClient
):
    """Show current AI model."""
    await msg.edit(
        f'<b>AI Model:</b> <code>'
        f'{escape(openai.model)}</code>',
        parse_mode=ParseMode.HTML,
    )


def _extract_prompt(msg: Message) -> str:
    """Extract prompt text from message (after command)."""
    text = msg.text or ''
    # Remove the command part (first word)
    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        # Check if replying to a message
        if msg.reply_to_message:
            return msg.reply_to_message.text or ''
        return ''
    prompt = parts[1].strip()
    # Also append reply text if replying
    if msg.reply_to_message and msg.reply_to_message.text:
        prompt += '\n\n' + msg.reply_to_message.text
    return prompt
