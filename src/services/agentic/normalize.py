from __future__ import annotations

from datetime import datetime
from typing import Any

from pyrogram.types import Message


def _ts(value: datetime | None) -> int | None:
    if value is None:
        return None
    return int(value.timestamp())


def _sender_name(msg: Message) -> str | None:
    user = msg.from_user
    if user is not None:
        parts = [user.first_name or '', user.last_name or '']
        full = ' '.join(part for part in parts if part).strip()
        return full or user.username
    sender_chat = getattr(msg, 'sender_chat', None)
    if sender_chat is not None:
        return getattr(sender_chat, 'title', None)
    return None


def _chat_title(msg: Message) -> str | None:
    chat = msg.chat
    return (
        getattr(chat, 'title', None)
        or getattr(chat, 'first_name', None)
        or getattr(chat, 'username', None)
    )


def _media_type(msg: Message) -> str | None:
    for name in (
        'photo',
        'video',
        'document',
        'audio',
        'voice',
        'sticker',
        'animation',
        'poll',
        'location',
        'contact',
    ):
        if getattr(msg, name, None) is not None:
            return name
    return None


def normalize_text(text: str | None) -> str:
    if not text:
        return ''
    return ' '.join(text.replace('\x00', ' ').split())


def normalize_message(msg: Message) -> dict[str, Any]:
    text = msg.text or None
    caption = msg.caption or None
    body = normalize_text(text or caption)
    user = msg.from_user
    sender_chat = getattr(msg, 'sender_chat', None)
    chat = msg.chat
    reply = msg.reply_to_message

    return {
        'chat_id': int(chat.id),
        'message_id': int(msg.id),
        'chat_type': str(getattr(chat, 'type', '') or ''),
        'chat_title': _chat_title(msg),
        'chat_username': getattr(chat, 'username', None),
        'sender_user_id': int(user.id) if user else None,
        'sender_chat_id': (
            int(sender_chat.id) if sender_chat is not None else None
        ),
        'sender_name': _sender_name(msg),
        'sender_username': getattr(user, 'username', None)
        if user
        else None,
        'sender_first_name': getattr(user, 'first_name', None)
        if user
        else None,
        'sender_last_name': getattr(user, 'last_name', None)
        if user
        else None,
        'sender_is_self': bool(getattr(user, 'is_self', False))
        if user
        else False,
        'sender_is_bot': bool(getattr(user, 'is_bot', False))
        if user
        else False,
        'reply_to_message_id': int(reply.id) if reply else None,
        'thread_id': getattr(msg, 'message_thread_id', None),
        'date_ts': _ts(msg.date) or 0,
        'edit_date_ts': _ts(msg.edit_date),
        'text': text,
        'caption': caption,
        'normalized_text': body,
        'media_type': _media_type(msg),
        'raw': {
            'outgoing': bool(getattr(msg, 'outgoing', False)),
            'mentioned': bool(getattr(msg, 'mentioned', False)),
            'empty': bool(getattr(msg, 'empty', False)),
        },
    }
