from __future__ import annotations

import json
from typing import Any, Awaitable, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from src.services.agentic.runtime import AgenticRuntime


ToolDispatch = Callable[[str, dict[str, Any]], Awaitable[str]]


def _tool(
    name: str,
    description: str,
    properties: dict[str, Any],
    required: list[str] | None = None,
) -> dict[str, Any]:
    return {
        'type': 'function',
        'function': {
            'name': name,
            'description': description,
            'parameters': {
                'type': 'object',
                'properties': properties,
                'required': required or [],
            },
        },
    }


READONLY_TOOL_SPECS: list[dict[str, Any]] = [
    _tool(
        'list_chats',
        'List locally indexed Telegram chats ordered by recent activity.',
        {
            'query': {
                'type': 'string',
                'description': 'Optional title or username substring.',
            },
            'limit': {
                'type': 'integer',
                'description': 'Maximum chats to return, 1-100.',
            },
        },
    ),
    _tool(
        'global_stats',
        'Return global counts for locally indexed chats, users, messages, '
        'deleted messages, and agent actions.',
        {},
    ),
    _tool(
        'chat_stats',
        'Return local indexing stats for one chat.',
        {
            'chat_id': {
                'type': 'integer',
                'description': (
                    'Telegram chat id. Omit to use the current chat.'
                ),
            },
        },
    ),
    _tool(
        'recent_messages',
        'Read recent locally indexed messages from a chat.',
        {
            'chat_id': {
                'type': 'integer',
                'description': (
                    'Telegram chat id. Omit to use the current chat.'
                ),
            },
            'limit': {
                'type': 'integer',
                'description': 'Maximum messages to return, 1-100.',
            },
        },
    ),
    _tool(
        'search_messages',
        'Full-text search locally indexed Telegram messages.',
        {
            'query': {
                'type': 'string',
                'description': 'Search query.',
            },
            'chat_id': {
                'type': 'integer',
                'description': (
                    'Telegram chat id. Omit to search all allowed chats.'
                ),
            },
            'limit': {
                'type': 'integer',
                'description': 'Maximum messages to return, 1-100.',
            },
        },
        required=['query'],
    ),
    _tool(
        'get_message',
        'Read one locally indexed Telegram message by id.',
        {
            'message_id': {
                'type': 'integer',
                'description': 'Telegram message id.',
            },
            'chat_id': {
                'type': 'integer',
                'description': (
                    'Telegram chat id. Omit to use the current chat.'
                ),
            },
        },
        required=['message_id'],
    ),
    _tool(
        'messages_around',
        'Read messages around a locally indexed Telegram message.',
        {
            'message_id': {
                'type': 'integer',
                'description': 'Center Telegram message id.',
            },
            'chat_id': {
                'type': 'integer',
                'description': (
                    'Telegram chat id. Omit to use the current chat.'
                ),
            },
            'before': {
                'type': 'integer',
                'description': 'Messages before the center, 0-100.',
            },
            'after': {
                'type': 'integer',
                'description': 'Messages after the center, 0-100.',
            },
        },
        required=['message_id'],
    ),
    _tool(
        'user_messages',
        'Read recent locally indexed messages from one Telegram user.',
        {
            'user_id': {
                'type': 'integer',
                'description': 'Telegram user id.',
            },
            'chat_id': {
                'type': 'integer',
                'description': (
                    'Optional chat id. Omit to search all allowed chats.'
                ),
            },
            'limit': {
                'type': 'integer',
                'description': 'Maximum messages to return, 1-100.',
            },
        },
        required=['user_id'],
    ),
]


def build_readonly_tools(
    agentic: AgenticRuntime,
    *,
    current_chat_id: int,
    allow_global: bool,
) -> tuple[list[dict[str, Any]], ToolDispatch]:
    def chat_id_from_args(args: dict[str, Any]) -> int:
        raw = args.get('chat_id')
        if raw is None:
            return int(current_chat_id)
        chat_id = int(raw)
        if not allow_global and chat_id != int(current_chat_id):
            raise ValueError('tool is restricted to the current chat')
        return chat_id

    async def dispatch(name: str, args: dict[str, Any]) -> str:
        if name == 'list_chats':
            if not allow_global:
                data = await agentic.storage.chat_stats(
                    current_chat_id
                )
                return _json({'current_chat': data})
            data = await agentic.storage.list_chats(
                query=_optional_str(args.get('query')),
                limit=_limit(args.get('limit'), default=30),
            )
            return _json({'chats': data})

        if name == 'global_stats':
            if not allow_global:
                data = await agentic.storage.chat_stats(
                    current_chat_id
                )
                return _json({'current_chat': data})
            return _json(await agentic.storage.stats())

        if name == 'chat_stats':
            return _json(
                await agentic.storage.chat_stats(
                    chat_id_from_args(args)
                )
            )

        if name == 'recent_messages':
            data = await agentic.storage.recent_messages(
                chat_id_from_args(args),
                _limit(args.get('limit'), default=40),
            )
            return _json({'messages': data})

        if name == 'search_messages':
            query = str(args.get('query') or '').strip()
            if not query:
                return _json({'error': 'query is required'})
            chat_id = args.get('chat_id')
            if chat_id is None and allow_global:
                resolved_chat_id = None
            else:
                resolved_chat_id = chat_id_from_args(args)
            data = await agentic.storage.search_messages(
                query,
                chat_id=resolved_chat_id,
                limit=_limit(args.get('limit'), default=20),
            )
            return _json({'messages': data})

        if name == 'get_message':
            data = await agentic.storage.get_message(
                chat_id_from_args(args),
                int(args.get('message_id')),
            )
            return _json({'message': data})

        if name == 'messages_around':
            data = await agentic.storage.messages_around(
                chat_id_from_args(args),
                int(args.get('message_id')),
                before=_limit(
                    args.get('before'),
                    default=10,
                    minimum=0,
                ),
                after=_limit(
                    args.get('after'),
                    default=10,
                    minimum=0,
                ),
            )
            return _json({'messages': data})

        if name == 'user_messages':
            chat_id = args.get('chat_id')
            if chat_id is None and allow_global:
                resolved_chat_id = None
            else:
                resolved_chat_id = chat_id_from_args(args)
            data = await agentic.storage.user_messages(
                int(args.get('user_id')),
                chat_id=resolved_chat_id,
                limit=_limit(args.get('limit'), default=30),
            )
            return _json({'messages': data})

        return _json({'error': f'unknown tool: {name}'})

    return READONLY_TOOL_SPECS, dispatch


def _limit(value: Any, *, default: int, minimum: int = 1) -> int:
    try:
        return max(minimum, min(int(value), 100))
    except Exception:
        return default


def _optional_str(value: Any) -> str | None:
    text = str(value or '').strip()
    return text or None


def _json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, default=str)
