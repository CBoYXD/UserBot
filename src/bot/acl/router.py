from html import escape

from pyrogram import Client, filters
from pyrogram.enums import ParseMode
from pyrogram.types import Message
from redis.asyncio import Redis

from src.services.acl import registry, storage
from src.core.router import Router


acl_router = Router('acl')
acl_router.router_filters = filters.me


def _user_label(u) -> str:
    name = (
        (u.first_name or '')
        + (' ' + u.last_name if u.last_name else '')
    ).strip()
    if u.username:
        return f'@{u.username}'
    return name or str(u.id)


async def _resolve_user(
    client: Client,
    msg: Message,
    token: str | None,
) -> tuple[int | None, str]:
    """Returns (user_id, label) or (None, error message)."""
    if msg.reply_to_message and msg.reply_to_message.from_user:
        u = msg.reply_to_message.from_user
        return u.id, _user_label(u)
    if not token:
        return (
            None,
            'specify @username, user_id, or reply to a message',
        )
    try:
        u = await client.get_users(token.lstrip('@'))
        return u.id, _user_label(u)
    except Exception:
        try:
            return int(token), token
        except ValueError:
            return None, f'cannot resolve user {token!r}'


def _split_args(msg: Message) -> tuple[str | None, str | None]:
    """Returns (user_token, scope_token).

    If the command is a reply, the first argument is the scope.
    Otherwise the first argument is the user, the second is the scope.
    """
    text = (msg.text or '').split(maxsplit=1)
    if len(text) < 2:
        return None, None
    body = text[1].strip()
    if not body:
        return None, None
    if msg.reply_to_message:
        return None, body
    parts = body.split(maxsplit=1)
    if len(parts) == 1:
        return parts[0], None
    return parts[0], parts[1].strip()


def _modules_hint() -> str:
    mods = ', '.join(sorted(registry.MODULES))
    return f'<b>Modules:</b> <code>{escape(mods)}</code>'


@acl_router.message(filters.command('allow', prefixes='.'))
async def allow_cmd(
    msg: Message, client: Client, redis: Redis
):
    user_token, scope_token = _split_args(msg)
    if not scope_token:
        await msg.edit(
            '<b>Usage:</b> '
            '<code>.allow @user &lt;module|cmd|*&gt;</code> '
            'or reply with <code>.allow &lt;scope&gt;</code>\n'
            + _modules_hint(),
            parse_mode=ParseMode.HTML,
        )
        return

    user_id, label = await _resolve_user(client, msg, user_token)
    if user_id is None:
        await msg.edit(
            f'<b>Allow:</b> {escape(label)}',
            parse_mode=ParseMode.HTML,
        )
        return

    scope = registry.normalize_scope(scope_token)
    if scope is None:
        await msg.edit(
            '<b>Allow:</b> unknown scope '
            f'<code>{escape(scope_token)}</code>.\n'
            + _modules_hint(),
            parse_mode=ParseMode.HTML,
        )
        return

    added = await storage.grant(redis, user_id, scope)
    state = 'granted' if added else 'already granted'
    danger = (
        ' ⚠️ <i>code-exec access</i>'
        if scope in registry.DANGEROUS_SCOPES
        else ''
    )
    await msg.edit(
        f'<b>Allow:</b> {state} '
        f'<code>{escape(scope)}</code> to '
        f'<code>{escape(label)}</code>{danger}',
        parse_mode=ParseMode.HTML,
    )


@acl_router.message(filters.command('disallow', prefixes='.'))
async def disallow_cmd(
    msg: Message, client: Client, redis: Redis
):
    user_token, scope_token = _split_args(msg)
    user_id, label = await _resolve_user(client, msg, user_token)
    if user_id is None:
        await msg.edit(
            f'<b>Disallow:</b> {escape(label)}',
            parse_mode=ParseMode.HTML,
        )
        return

    if not scope_token:
        n = await storage.revoke_all(redis, user_id)
        await msg.edit(
            f'<b>Disallow:</b> revoked <code>{n}</code> '
            f'grants from <code>{escape(label)}</code>',
            parse_mode=ParseMode.HTML,
        )
        return

    scope = registry.normalize_scope(scope_token)
    if scope is None:
        await msg.edit(
            '<b>Disallow:</b> unknown scope '
            f'<code>{escape(scope_token)}</code>.',
            parse_mode=ParseMode.HTML,
        )
        return

    removed = await storage.revoke(redis, user_id, scope)
    state = 'revoked' if removed else 'was not granted'
    await msg.edit(
        f'<b>Disallow:</b> {state} '
        f'<code>{escape(scope)}</code> from '
        f'<code>{escape(label)}</code>',
        parse_mode=ParseMode.HTML,
    )


@acl_router.message(filters.command('allowed', prefixes='.'))
async def allowed_cmd(
    msg: Message, client: Client, redis: Redis
):
    text = (msg.text or '').split(maxsplit=1)
    arg = text[1].strip() if len(text) > 1 else ''

    if msg.reply_to_message or arg:
        user_id, label = await _resolve_user(
            client, msg, arg or None
        )
        if user_id is None:
            await msg.edit(
                f'<b>Allowed:</b> {escape(label)}',
                parse_mode=ParseMode.HTML,
            )
            return
        grants = await storage.list_grants(redis, user_id)
        if not grants:
            await msg.edit(
                f'<b>Allowed:</b> <code>{escape(label)}</code> '
                f'has no grants.',
                parse_mode=ParseMode.HTML,
            )
            return
        body = '\n'.join(
            f'<code>{escape(g)}</code>' for g in sorted(grants)
        )
        await msg.edit(
            f'<b>Allowed for {escape(label)}</b>\n{body}',
            parse_mode=ParseMode.HTML,
        )
        return

    user_ids = await storage.list_users(redis)
    if not user_ids:
        await msg.edit(
            '<b>Allowed:</b> nobody.',
            parse_mode=ParseMode.HTML,
        )
        return

    lines: list[str] = []
    for uid in user_ids:
        try:
            u = await client.get_users(uid)
            label = _user_label(u)
        except Exception:
            label = str(uid)
        grants = await storage.list_grants(redis, uid)
        scopes = ', '.join(sorted(grants))
        lines.append(
            f'<code>{escape(label)}</code> '
            f'(<code>{uid}</code>): {escape(scopes)}'
        )
    await msg.edit(
        '<b>Allowed</b>\n' + '\n'.join(lines),
        parse_mode=ParseMode.HTML,
    )
