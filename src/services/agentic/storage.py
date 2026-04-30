from __future__ import annotations

import json
import re
import time
from typing import Any

from sqlalchemy import func, select, text, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
)

from src.db.models import (
    AgentAction,
    AgentTrace,
    Chat,
    MemoryFact,
    Message,
    User,
)


TOKEN_RE = re.compile(r'[\w\-]{2,}', re.UNICODE)


class AgenticStorage:
    def __init__(
        self,
        engine: AsyncEngine,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self._engine = engine
        self._sf = session_factory

    # ── schema bootstrap ────────────────────────────────────────────

    async def init(self) -> None:
        """Create tables that are not managed by Alembic migrations
        (FTS5 virtual table) and ensure the schema is up to date for
        fresh installs that skip the migration step."""
        from src.db.base import Base

        async with self._sf() as session:
            await session.execute(
                text(
                    """
                    CREATE VIRTUAL TABLE IF NOT EXISTS message_fts
                    USING fts5(
                        chat_id UNINDEXED,
                        message_id UNINDEXED,
                        normalized_text
                    )
                    """
                )
            )
            await session.commit()

        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    # ── upserts ─────────────────────────────────────────────────────

    async def upsert_message(self, item: dict[str, Any]) -> None:
        now = int(time.time())
        chat_id = int(item['chat_id'])
        message_id = int(item['message_id'])
        ntext = item.get('normalized_text') or ''
        raw = json.dumps(
            item.get('raw') or {}, ensure_ascii=False
        )

        async with self._sf() as session:
            async with session.begin():
                await session.execute(
                    sqlite_insert(Chat)
                    .values(
                        chat_id=chat_id,
                        type=item.get('chat_type') or '',
                        title=item.get('chat_title'),
                        username=item.get('chat_username'),
                        first_seen_at=now,
                        last_seen_at=now,
                    )
                    .on_conflict_do_update(
                        index_elements=['chat_id'],
                        set_={
                            'type': item.get('chat_type') or '',
                            'title': item.get('chat_title'),
                            'username': item.get('chat_username'),
                            'last_seen_at': now,
                        },
                    )
                )

                user_id = item.get('sender_user_id')
                if user_id is not None:
                    await session.execute(
                        sqlite_insert(User)
                        .values(
                            user_id=int(user_id),
                            is_self=bool(
                                item.get('sender_is_self')
                            ),
                            is_bot=bool(item.get('sender_is_bot')),
                            username=item.get('sender_username'),
                            first_name=item.get(
                                'sender_first_name'
                            ),
                            last_name=item.get('sender_last_name'),
                            first_seen_at=now,
                            last_seen_at=now,
                        )
                        .on_conflict_do_update(
                            index_elements=['user_id'],
                            set_={
                                'is_self': bool(
                                    item.get('sender_is_self')
                                ),
                                'is_bot': bool(
                                    item.get('sender_is_bot')
                                ),
                                'username': item.get(
                                    'sender_username'
                                ),
                                'first_name': item.get(
                                    'sender_first_name'
                                ),
                                'last_name': item.get(
                                    'sender_last_name'
                                ),
                                'last_seen_at': now,
                            },
                        )
                    )

                await session.execute(
                    sqlite_insert(Message)
                    .values(
                        chat_id=chat_id,
                        message_id=message_id,
                        sender_user_id=item.get('sender_user_id'),
                        sender_chat_id=item.get('sender_chat_id'),
                        reply_to_message_id=item.get(
                            'reply_to_message_id'
                        ),
                        thread_id=item.get('thread_id'),
                        date_ts=item.get('date_ts') or now,
                        edit_date_ts=item.get('edit_date_ts'),
                        text=item.get('text'),
                        caption=item.get('caption'),
                        normalized_text=ntext,
                        media_type=item.get('media_type'),
                        raw_json=raw,
                        deleted_at=None,
                        facts_extracted=False,
                    )
                    .on_conflict_do_update(
                        index_elements=['chat_id', 'message_id'],
                        set_={
                            'sender_user_id': item.get(
                                'sender_user_id'
                            ),
                            'sender_chat_id': item.get(
                                'sender_chat_id'
                            ),
                            'reply_to_message_id': item.get(
                                'reply_to_message_id'
                            ),
                            'thread_id': item.get('thread_id'),
                            'date_ts': item.get('date_ts') or now,
                            'edit_date_ts': item.get(
                                'edit_date_ts'
                            ),
                            'text': item.get('text'),
                            'caption': item.get('caption'),
                            'normalized_text': ntext,
                            'media_type': item.get('media_type'),
                            'raw_json': raw,
                            'deleted_at': None,
                        },
                    )
                )

                await session.execute(
                    text(
                        'DELETE FROM message_fts'
                        ' WHERE chat_id = :cid'
                        ' AND message_id = :mid'
                    ),
                    {'cid': chat_id, 'mid': message_id},
                )
                if ntext:
                    await session.execute(
                        text(
                            'INSERT INTO message_fts'
                            ' (chat_id, message_id, normalized_text)'
                            ' VALUES (:cid, :mid, :txt)'
                        ),
                        {
                            'cid': chat_id,
                            'mid': message_id,
                            'txt': ntext,
                        },
                    )

    async def mark_deleted(
        self, chat_id: int, message_ids: list[int]
    ) -> int:
        if not message_ids:
            return 0
        now = int(time.time())
        count = 0
        async with self._sf() as session:
            async with session.begin():
                for mid in message_ids:
                    res = await session.execute(
                        update(Message)
                        .where(
                            Message.chat_id == chat_id,
                            Message.message_id == mid,
                        )
                        .values(deleted_at=now)
                    )
                    count += res.rowcount
                    await session.execute(
                        text(
                            'DELETE FROM message_fts'
                            ' WHERE chat_id = :cid'
                            ' AND message_id = :mid'
                        ),
                        {'cid': chat_id, 'mid': mid},
                    )
        return count

    # ── fact / profile storage ───────────────────────────────────────

    async def upsert_fact(
        self,
        scope_type: str,
        scope_id: str,
        key: str,
        value: str,
        confidence: float,
    ) -> None:
        now = int(time.time())
        async with self._sf() as session:
            async with session.begin():
                await session.execute(
                    sqlite_insert(MemoryFact)
                    .values(
                        scope_type=scope_type,
                        scope_id=scope_id,
                        key=key,
                        value=value,
                        confidence=confidence,
                        created_at=now,
                        updated_at=now,
                    )
                    .on_conflict_do_update(
                        index_elements=[
                            'scope_type',
                            'scope_id',
                            'key',
                        ],
                        set_={
                            'value': value,
                            'confidence': confidence,
                            'updated_at': now,
                        },
                    )
                )

    async def get_facts(
        self, scope_type: str, scope_id: str
    ) -> list[dict[str, Any]]:
        async with self._sf() as session:
            rows = (
                await session.execute(
                    select(MemoryFact)
                    .where(
                        MemoryFact.scope_type == scope_type,
                        MemoryFact.scope_id == scope_id,
                    )
                    .order_by(MemoryFact.updated_at.desc())
                )
            ).scalars().all()
        return [_fact_to_dict(r) for r in rows]

    async def update_profile_summary(
        self, user_id: int, summary: str
    ) -> None:
        async with self._sf() as session:
            async with session.begin():
                await session.execute(
                    update(User)
                    .where(User.user_id == user_id)
                    .values(profile_summary=summary)
                )

    async def get_user(
        self, user_id: int
    ) -> dict[str, Any] | None:
        async with self._sf() as session:
            row = (
                await session.execute(
                    select(User).where(User.user_id == user_id)
                )
            ).scalar_one_or_none()
        return _user_to_dict(row) if row else None

    async def pending_for_extraction(
        self, limit: int = 50
    ) -> list[dict[str, Any]]:
        async with self._sf() as session:
            rows = (
                await session.execute(
                    select(Message, User.first_name, User.last_name, User.username)
                    .outerjoin(
                        User,
                        Message.sender_user_id == User.user_id,
                    )
                    .where(
                        Message.facts_extracted.is_(False),
                        Message.deleted_at.is_(None),
                        Message.normalized_text != '',
                        Message.normalized_text.isnot(None),
                        Message.sender_user_id.isnot(None),
                    )
                    .order_by(Message.date_ts.asc())
                    .limit(limit)
                )
            ).all()
        return [
            _message_row_to_dict(msg, fn, ln, un)
            for msg, fn, ln, un in rows
        ]

    async def mark_extracted(
        self,
        ids: list[tuple[int, int]],
    ) -> None:
        if not ids:
            return
        async with self._sf() as session:
            async with session.begin():
                for chat_id, message_id in ids:
                    await session.execute(
                        update(Message)
                        .where(
                            Message.chat_id == chat_id,
                            Message.message_id == message_id,
                        )
                        .values(facts_extracted=True)
                    )

    async def users_with_new_facts(
        self, since_ts: int
    ) -> list[int]:
        async with self._sf() as session:
            rows = (
                await session.execute(
                    select(MemoryFact.scope_id)
                    .where(
                        MemoryFact.scope_type == 'user',
                        MemoryFact.updated_at > since_ts,
                    )
                    .distinct()
                )
            ).all()
        return [int(r[0]) for r in rows]

    # ── reads ────────────────────────────────────────────────────────

    async def recent_messages(
        self, chat_id: int, limit: int = 40
    ) -> list[dict[str, Any]]:
        async with self._sf() as session:
            rows = (
                await session.execute(
                    select(
                        Message,
                        User.first_name,
                        User.last_name,
                        User.username,
                    )
                    .outerjoin(
                        User,
                        Message.sender_user_id == User.user_id,
                    )
                    .where(
                        Message.chat_id == chat_id,
                        Message.deleted_at.is_(None),
                    )
                    .order_by(Message.message_id.desc())
                    .limit(limit)
                )
            ).all()
        items = [
            _message_row_to_dict(msg, fn, ln, un)
            for msg, fn, ln, un in rows
        ]
        items.reverse()
        return items

    async def get_message(
        self, chat_id: int, message_id: int
    ) -> dict[str, Any] | None:
        async with self._sf() as session:
            row = (
                await session.execute(
                    select(
                        Message,
                        User.first_name,
                        User.last_name,
                        User.username,
                    )
                    .outerjoin(
                        User,
                        Message.sender_user_id == User.user_id,
                    )
                    .where(
                        Message.chat_id == chat_id,
                        Message.message_id == message_id,
                        Message.deleted_at.is_(None),
                    )
                )
            ).first()
        if row is None:
            return None
        msg, fn, ln, un = row
        return _message_row_to_dict(msg, fn, ln, un)

    async def messages_around(
        self,
        chat_id: int,
        message_id: int,
        *,
        before: int = 10,
        after: int = 10,
    ) -> list[dict[str, Any]]:
        before = max(0, min(before, 100))
        after = max(0, min(after, 100))
        base = (
            select(
                Message,
                User.first_name,
                User.last_name,
                User.username,
            )
            .outerjoin(
                User,
                Message.sender_user_id == User.user_id,
            )
            .where(
                Message.chat_id == chat_id,
                Message.deleted_at.is_(None),
            )
        )
        async with self._sf() as session:
            before_rows = (
                await session.execute(
                    base.where(Message.message_id < message_id)
                    .order_by(Message.message_id.desc())
                    .limit(before)
                )
            ).all()
            current = (
                await session.execute(
                    base.where(Message.message_id == message_id)
                )
            ).first()
            after_rows = (
                await session.execute(
                    base.where(Message.message_id > message_id)
                    .order_by(Message.message_id.asc())
                    .limit(after)
                )
            ).all()

        result: list[dict[str, Any]] = []
        for row in reversed(before_rows):
            msg, fn, ln, un = row
            result.append(_message_row_to_dict(msg, fn, ln, un))
        if current:
            msg, fn, ln, un = current
            result.append(_message_row_to_dict(msg, fn, ln, un))
        for row in after_rows:
            msg, fn, ln, un = row
            result.append(_message_row_to_dict(msg, fn, ln, un))
        return result

    async def user_messages(
        self,
        user_id: int,
        *,
        chat_id: int | None = None,
        limit: int = 30,
    ) -> list[dict[str, Any]]:
        limit = max(1, min(limit, 100))
        stmt = (
            select(
                Message,
                User.first_name,
                User.last_name,
                User.username,
            )
            .outerjoin(
                User,
                Message.sender_user_id == User.user_id,
            )
            .where(
                Message.sender_user_id == user_id,
                Message.deleted_at.is_(None),
            )
        )
        if chat_id is not None:
            stmt = stmt.where(Message.chat_id == chat_id)
        stmt = (
            stmt.order_by(Message.message_id.desc()).limit(limit)
        )
        async with self._sf() as session:
            rows = (await session.execute(stmt)).all()
        items = [
            _message_row_to_dict(msg, fn, ln, un)
            for msg, fn, ln, un in rows
        ]
        items.reverse()
        return items

    async def search_messages(
        self,
        query: str,
        *,
        chat_id: int | None = None,
        limit: int = 12,
    ) -> list[dict[str, Any]]:
        match = _fts_query(query)
        if not match:
            return []
        params: dict[str, Any] = {
            'match': match,
            'limit': int(limit),
        }
        where_extra = ''
        if chat_id is not None:
            where_extra = ' AND f.chat_id = :chat_id'
            params['chat_id'] = int(chat_id)

        sql = text(
            f"""
            SELECT
                m.chat_id, m.message_id, m.sender_user_id,
                m.sender_chat_id, m.reply_to_message_id,
                m.thread_id, m.date_ts, m.edit_date_ts,
                m.text, m.caption, m.normalized_text,
                m.media_type,
                u.first_name, u.last_name, u.username
            FROM message_fts f
            JOIN messages m
              ON m.chat_id = f.chat_id
             AND m.message_id = f.message_id
            LEFT JOIN users u ON u.user_id = m.sender_user_id
            WHERE f.normalized_text MATCH :match
              AND m.deleted_at IS NULL
              {where_extra}
            ORDER BY bm25(message_fts) ASC, m.message_id DESC
            LIMIT :limit
            """
        )
        async with self._sf() as session:
            rows = (await session.execute(sql, params)).all()
        return [_fts_row_to_dict(r) for r in rows]

    async def list_chats(
        self,
        *,
        query: str | None = None,
        limit: int = 30,
    ) -> list[dict[str, Any]]:
        limit = max(1, min(limit, 100))
        msg_count = (
            select(func.count())
            .where(
                Message.chat_id == Chat.chat_id,
                Message.deleted_at.is_(None),
            )
            .correlate(Chat)
            .scalar_subquery()
        )
        stmt = select(Chat, msg_count.label('message_count'))
        if query:
            needle = f'%{query.strip()}%'
            stmt = stmt.where(
                Chat.title.like(needle)
                | Chat.username.like(needle)
            )
        stmt = stmt.order_by(Chat.last_seen_at.desc()).limit(
            limit
        )
        async with self._sf() as session:
            rows = (await session.execute(stmt)).all()
        return [
            _chat_to_dict(chat, mc) for chat, mc in rows
        ]

    async def chat_stats(
        self, chat_id: int
    ) -> dict[str, Any]:
        async with self._sf() as session:
            chat = (
                await session.execute(
                    select(Chat).where(
                        Chat.chat_id == chat_id
                    )
                )
            ).scalar_one_or_none()

            messages = (
                await session.execute(
                    select(func.count()).where(
                        Message.chat_id == chat_id,
                        Message.deleted_at.is_(None),
                    )
                )
            ).scalar_one()

            deleted = (
                await session.execute(
                    select(func.count()).where(
                        Message.chat_id == chat_id,
                        Message.deleted_at.isnot(None),
                    )
                )
            ).scalar_one()

            users = (
                await session.execute(
                    select(
                        func.count(
                            Message.sender_user_id.distinct()
                        )
                    ).where(
                        Message.chat_id == chat_id,
                        Message.sender_user_id.isnot(None),
                        Message.deleted_at.is_(None),
                    )
                )
            ).scalar_one()

        return {
            'chat': _chat_to_dict(chat) if chat else None,
            'messages': int(messages),
            'deleted': int(deleted),
            'users': int(users),
        }

    async def stats(self) -> dict[str, int]:
        async with self._sf() as session:
            chats = (
                await session.execute(select(func.count(Chat.chat_id)))
            ).scalar_one()
            users = (
                await session.execute(select(func.count(User.user_id)))
            ).scalar_one()
            messages = (
                await session.execute(
                    select(func.count()).where(
                        Message.deleted_at.is_(None)
                    )
                )
            ).scalar_one()
            deleted = (
                await session.execute(
                    select(func.count()).where(
                        Message.deleted_at.isnot(None)
                    )
                )
            ).scalar_one()
            actions = (
                await session.execute(
                    select(func.count(AgentAction.id))
                )
            ).scalar_one()
            traces = (
                await session.execute(
                    select(func.count(AgentTrace.id))
                )
            ).scalar_one()
        return {
            'chats': int(chats),
            'users': int(users),
            'messages': int(messages),
            'deleted': int(deleted),
            'actions': int(actions),
            'traces': int(traces),
        }

    # ── logging ──────────────────────────────────────────────────────

    async def log_action(
        self,
        *,
        chat_id: int,
        trigger_message_id: int | None,
        action_type: str,
        decision: dict[str, Any],
        result: dict[str, Any],
        status: str,
    ) -> None:
        now = int(time.time())
        async with self._sf() as session:
            async with session.begin():
                session.add(
                    AgentAction(
                        chat_id=int(chat_id),
                        trigger_message_id=trigger_message_id,
                        action_type=action_type,
                        decision_json=json.dumps(
                            decision, ensure_ascii=False
                        ),
                        result_json=json.dumps(
                            result, ensure_ascii=False
                        ),
                        status=status,
                        created_at=now,
                    )
                )

    async def log_trace(
        self,
        *,
        trace_id: str,
        chat_id: int,
        trigger_message_id: int | None,
        source: str,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        now = int(time.time())
        async with self._sf() as session:
            async with session.begin():
                session.add(
                    AgentTrace(
                        trace_id=trace_id,
                        chat_id=int(chat_id),
                        trigger_message_id=trigger_message_id,
                        source=source,
                        event_type=event_type,
                        payload_json=json.dumps(
                            payload, ensure_ascii=False
                        ),
                        created_at=now,
                    )
                )

    async def recent_traces(
        self,
        *,
        limit: int = 30,
        chat_id: int | None = None,
        trace_id: str | None = None,
    ) -> list[dict[str, Any]]:
        limit = max(1, min(limit, 200))
        stmt = select(AgentTrace)
        if trace_id:
            stmt = stmt.where(AgentTrace.trace_id == trace_id)
        elif chat_id is not None:
            stmt = stmt.where(AgentTrace.chat_id == chat_id)
        stmt = stmt.order_by(AgentTrace.id.desc()).limit(limit)
        async with self._sf() as session:
            rows = (await session.execute(stmt)).scalars().all()
        items = [_trace_to_dict(r) for r in rows]
        items.reverse()
        return items


# ── row → dict helpers ───────────────────────────────────────────────


def _display_name(
    first_name: str | None,
    last_name: str | None,
    username: str | None,
) -> str:
    full = ' '.join(
        p for p in (first_name, last_name) if p
    ).strip()
    return full or username or 'Unknown'


def _message_row_to_dict(
    msg: Message,
    first_name: str | None,
    last_name: str | None,
    username: str | None,
) -> dict[str, Any]:
    return {
        'chat_id': msg.chat_id,
        'message_id': msg.message_id,
        'sender_user_id': msg.sender_user_id,
        'sender': _display_name(first_name, last_name, username),
        'date_ts': msg.date_ts,
        'text': msg.text,
        'caption': msg.caption,
        'normalized_text': msg.normalized_text or '',
        'media_type': msg.media_type,
    }


def _fts_row_to_dict(row: Any) -> dict[str, Any]:
    return {
        'chat_id': row.chat_id,
        'message_id': row.message_id,
        'sender_user_id': row.sender_user_id,
        'sender': _display_name(
            row.first_name, row.last_name, row.username
        ),
        'date_ts': row.date_ts,
        'text': row.text,
        'caption': row.caption,
        'normalized_text': row.normalized_text or '',
        'media_type': row.media_type,
    }


def _chat_to_dict(
    chat: Chat, message_count: int | None = None
) -> dict[str, Any]:
    d: dict[str, Any] = {
        'chat_id': chat.chat_id,
        'type': chat.type,
        'title': chat.title,
        'username': chat.username,
        'first_seen_at': chat.first_seen_at,
        'last_seen_at': chat.last_seen_at,
        'memory_enabled': chat.memory_enabled,
        'auto_reply_enabled': chat.auto_reply_enabled,
    }
    if message_count is not None:
        d['message_count'] = int(message_count)
    return d


def _user_to_dict(user: User) -> dict[str, Any]:
    return {
        'user_id': user.user_id,
        'is_self': user.is_self,
        'is_bot': user.is_bot,
        'username': user.username,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'first_seen_at': user.first_seen_at,
        'last_seen_at': user.last_seen_at,
        'profile_summary': user.profile_summary,
    }


def _fact_to_dict(fact: MemoryFact) -> dict[str, Any]:
    return {
        'id': fact.id,
        'scope_type': fact.scope_type,
        'scope_id': fact.scope_id,
        'key': fact.key,
        'value': fact.value,
        'confidence': fact.confidence,
        'created_at': fact.created_at,
        'updated_at': fact.updated_at,
    }


def _trace_to_dict(trace: AgentTrace) -> dict[str, Any]:
    try:
        payload = json.loads(trace.payload_json)
    except Exception:
        payload = {}
    return {
        'id': trace.id,
        'trace_id': trace.trace_id,
        'chat_id': trace.chat_id,
        'trigger_message_id': trace.trigger_message_id,
        'source': trace.source,
        'event_type': trace.event_type,
        'payload': payload,
        'created_at': trace.created_at,
    }


def _fts_query(query: str) -> str:
    terms = TOKEN_RE.findall(query.lower())[:8]
    return ' OR '.join(f'"{t}"' for t in terms)
