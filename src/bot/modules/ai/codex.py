from html import escape

from pyrogram import filters
from pyrogram.enums import ParseMode
from pyrogram.types import Message
from redis.asyncio import Redis

from src.bot.modules.ai.helpers import extract_prompt
from src.bot.modules.ai.prefs import (
    AI_EFFORT_KEY,
    AI_MODEL_KEY,
    ALLOWED_EFFORTS,
    get_ai_preferences,
)
from src.bot.modules.ai.router import ai_router
from src.services.codex import CodexClient


@ai_router.message(filters.command('aimodel', prefixes='.'))
async def ai_model_info(
    msg: Message,
    codex: CodexClient,
    redis: Redis,
):
    """Show current AI model and effort."""
    model, effort, model_source, effort_source = (
        await get_ai_preferences(redis, codex)
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
    model = extract_prompt(msg)
    if not model:
        current_model, _, model_source, _ = (
            await get_ai_preferences(redis, codex)
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


@ai_router.message(filters.command('codexeffort', prefixes='.'))
async def codex_effort(
    msg: Message,
    codex: CodexClient,
    redis: Redis,
):
    """Show or update the current Codex reasoning effort."""
    effort = extract_prompt(msg).lower()
    if not effort:
        _, current_effort, _, effort_source = (
            await get_ai_preferences(redis, codex)
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
    model, _, _, _ = await get_ai_preferences(redis, codex)
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
    model, effort, _, _ = await get_ai_preferences(
        redis, codex
    )
    await msg.edit(
        '<b>AI Settings Reset</b>\n'
        f'<b>Model:</b> <code>{escape(model)}</code>\n'
        f'<b>Effort:</b> <code>{escape(effort)}</code>',
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
        credentials = await codex.complete_oauth(
            authorization_input
        )
        model, effort, _, _ = await get_ai_preferences(
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
        await get_ai_preferences(redis, codex)
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
