from html import escape

from pyrogram import filters
from pyrogram.enums import ParseMode
from pyrogram.types import Message
from redis.asyncio import Redis

from src.bot.modules.ai.prefs import get_ai_preferences
from src.bot.modules.ai.prompts import TRANSLATE_SYSTEM_PROMPT
from src.bot.modules.ai.router import ai_router
from src.bot.tools import utils
from src.services.codex import CodexClient


def _looks_like_lang(token: str) -> bool:
    return len(token) <= 12 and (
        token.isalpha() or '-' in token
    )


def _parse_args(msg: Message) -> tuple[str, str]:
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


@ai_router.message(
    filters.command(['tr', 'translate'], prefixes='.')
)
async def ai_translate(
    msg: Message,
    codex: CodexClient,
    redis: Redis,
):
    """Translate text. .tr [lang] <text|reply>."""
    target, body = _parse_args(msg)
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
        model, effort, _, _ = await get_ai_preferences(
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
