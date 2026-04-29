from html import escape

from pyrogram import Client, filters
from pyrogram.enums import ParseMode
from pyrogram.types import Message
from redis.asyncio import Redis

from src.bot.modules.ai.prefs import get_ai_preferences
from src.bot.modules.ai.prompts import TLDR_SYSTEM_PROMPT
from src.bot.modules.ai.router import ai_router
from src.bot.tools import utils
from src.services.codex import CodexClient


def _sender_name(m: Message) -> str:
    sender = m.from_user
    if sender is not None:
        full = (
            (sender.first_name or '')
            + (
                ' ' + sender.last_name
                if sender.last_name
                else ''
            )
        ).strip()
        return full or sender.username or 'User'
    return getattr(m.sender_chat, 'title', 'Channel')


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

        model, effort, _, _ = await get_ai_preferences(
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
