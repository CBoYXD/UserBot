from __future__ import annotations

import asyncio
import json
import re
import sqlite3
import time
from pathlib import Path
from typing import Any


TOKEN_RE = re.compile(r'[\w\-]{2,}', re.UNICODE)


class AgenticStorage:
    def __init__(self, db_path: str):
        self.path = Path(db_path)

    async def init(self) -> None:
        await asyncio.to_thread(self._init_sync)

    async def upsert_message(self, item: dict[str, Any]) -> None:
        await asyncio.to_thread(self._upsert_message_sync, item)

    async def mark_deleted(
        self, chat_id: int, message_ids: list[int]
    ) -> int:
        return await asyncio.to_thread(
            self._mark_deleted_sync, chat_id, message_ids
        )

    async def recent_messages(
        self, chat_id: int, limit: int = 40
    ) -> list[dict[str, Any]]:
        return await asyncio.to_thread(
            self._recent_messages_sync, chat_id, limit
        )

    async def search_messages(
        self,
        query: str,
        *,
        chat_id: int | None = None,
        limit: int = 12,
    ) -> list[dict[str, Any]]:
        return await asyncio.to_thread(
            self._search_messages_sync, query, chat_id, limit
        )

    async def stats(self) -> dict[str, int]:
        return await asyncio.to_thread(self._stats_sync)

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
        await asyncio.to_thread(
            self._log_action_sync,
            chat_id,
            trigger_message_id,
            action_type,
            decision,
            result,
            status,
        )

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.path))
        conn.row_factory = sqlite3.Row
        conn.execute('pragma journal_mode=wal')
        conn.execute('pragma foreign_keys=on')
        return conn

    def _init_sync(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                create table if not exists chats (
                    chat_id integer primary key,
                    type text not null,
                    title text,
                    username text,
                    first_seen_at integer not null,
                    last_seen_at integer not null,
                    memory_enabled integer not null default 1,
                    auto_reply_enabled integer not null default 0,
                    metadata_json text not null default '{}'
                );

                create table if not exists users (
                    user_id integer primary key,
                    is_self integer not null default 0,
                    is_bot integer not null default 0,
                    username text,
                    first_name text,
                    last_name text,
                    first_seen_at integer not null,
                    last_seen_at integer not null,
                    profile_summary text,
                    metadata_json text not null default '{}'
                );

                create table if not exists messages (
                    chat_id integer not null,
                    message_id integer not null,
                    sender_user_id integer,
                    sender_chat_id integer,
                    reply_to_message_id integer,
                    thread_id integer,
                    date_ts integer not null,
                    edit_date_ts integer,
                    text text,
                    caption text,
                    normalized_text text,
                    media_type text,
                    entities_json text not null default '[]',
                    raw_json text not null default '{}',
                    deleted_at integer,
                    primary key (chat_id, message_id)
                );

                create virtual table if not exists message_fts
                using fts5(
                    chat_id unindexed,
                    message_id unindexed,
                    normalized_text
                );

                create table if not exists memory_summaries (
                    id integer primary key autoincrement,
                    scope_type text not null,
                    scope_id text not null,
                    kind text not null,
                    from_ts integer,
                    to_ts integer,
                    source_count integer not null,
                    summary text not null,
                    model text not null,
                    created_at integer not null
                );

                create table if not exists memory_facts (
                    id integer primary key autoincrement,
                    scope_type text not null,
                    scope_id text not null,
                    key text not null,
                    value text not null,
                    confidence real not null default 0,
                    created_at integer not null,
                    updated_at integer not null,
                    unique(scope_type, scope_id, key)
                );

                create table if not exists agent_actions (
                    id integer primary key autoincrement,
                    chat_id integer not null,
                    trigger_message_id integer,
                    action_type text not null,
                    decision_json text not null,
                    result_json text not null default '{}',
                    status text not null,
                    created_at integer not null
                );
                """
            )

    def _upsert_message_sync(self, item: dict[str, Any]) -> None:
        now = int(time.time())
        chat_id = int(item['chat_id'])
        message_id = int(item['message_id'])
        text = item.get('normalized_text') or ''
        with self._connect() as conn:
            conn.execute(
                """
                insert into chats (
                    chat_id, type, title, username,
                    first_seen_at, last_seen_at
                )
                values (?, ?, ?, ?, ?, ?)
                on conflict(chat_id) do update set
                    type = excluded.type,
                    title = excluded.title,
                    username = excluded.username,
                    last_seen_at = excluded.last_seen_at
                """,
                (
                    chat_id,
                    item.get('chat_type') or '',
                    item.get('chat_title'),
                    item.get('chat_username'),
                    now,
                    now,
                ),
            )
            user_id = item.get('sender_user_id')
            if user_id is not None:
                conn.execute(
                    """
                    insert into users (
                        user_id, is_self, is_bot, username,
                        first_name, last_name, first_seen_at,
                        last_seen_at
                    )
                    values (?, ?, ?, ?, ?, ?, ?, ?)
                    on conflict(user_id) do update set
                        is_self = excluded.is_self,
                        is_bot = excluded.is_bot,
                        username = excluded.username,
                        first_name = excluded.first_name,
                        last_name = excluded.last_name,
                        last_seen_at = excluded.last_seen_at
                    """,
                    (
                        int(user_id),
                        1 if item.get('sender_is_self') else 0,
                        1 if item.get('sender_is_bot') else 0,
                        item.get('sender_username'),
                        item.get('sender_first_name'),
                        item.get('sender_last_name'),
                        now,
                        now,
                    ),
                )
            conn.execute(
                """
                insert into messages (
                    chat_id, message_id, sender_user_id,
                    sender_chat_id, reply_to_message_id, thread_id,
                    date_ts, edit_date_ts, text, caption,
                    normalized_text, media_type, raw_json,
                    deleted_at
                )
                values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, null)
                on conflict(chat_id, message_id) do update set
                    sender_user_id = excluded.sender_user_id,
                    sender_chat_id = excluded.sender_chat_id,
                    reply_to_message_id = excluded.reply_to_message_id,
                    thread_id = excluded.thread_id,
                    date_ts = excluded.date_ts,
                    edit_date_ts = excluded.edit_date_ts,
                    text = excluded.text,
                    caption = excluded.caption,
                    normalized_text = excluded.normalized_text,
                    media_type = excluded.media_type,
                    raw_json = excluded.raw_json,
                    deleted_at = null
                """,
                (
                    chat_id,
                    message_id,
                    item.get('sender_user_id'),
                    item.get('sender_chat_id'),
                    item.get('reply_to_message_id'),
                    item.get('thread_id'),
                    item.get('date_ts') or now,
                    item.get('edit_date_ts'),
                    item.get('text'),
                    item.get('caption'),
                    text,
                    item.get('media_type'),
                    json.dumps(
                        item.get('raw') or {}, ensure_ascii=False
                    ),
                ),
            )
            conn.execute(
                """
                delete from message_fts
                where chat_id = ? and message_id = ?
                """,
                (chat_id, message_id),
            )
            if text:
                conn.execute(
                    """
                    insert into message_fts (
                        chat_id, message_id, normalized_text
                    )
                    values (?, ?, ?)
                    """,
                    (chat_id, message_id, text),
                )

    def _mark_deleted_sync(
        self, chat_id: int, message_ids: list[int]
    ) -> int:
        if not message_ids:
            return 0
        now = int(time.time())
        with self._connect() as conn:
            count = 0
            for mid in message_ids:
                cursor = conn.execute(
                    """
                    update messages
                    set deleted_at = ?
                    where chat_id = ? and message_id = ?
                    """,
                    (now, chat_id, int(mid)),
                )
                conn.execute(
                    """
                    delete from message_fts
                    where chat_id = ? and message_id = ?
                    """,
                    (chat_id, int(mid)),
                )
                count += cursor.rowcount
            return count

    def _recent_messages_sync(
        self, chat_id: int, limit: int
    ) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                select m.*, u.first_name, u.last_name, u.username
                from messages m
                left join users u on u.user_id = m.sender_user_id
                where m.chat_id = ? and m.deleted_at is null
                order by m.message_id desc
                limit ?
                """,
                (int(chat_id), int(limit)),
            ).fetchall()
        items = [self._row_to_message(row) for row in rows]
        items.reverse()
        return items

    def _search_messages_sync(
        self, query: str, chat_id: int | None, limit: int
    ) -> list[dict[str, Any]]:
        match = self._fts_query(query)
        if not match:
            return []
        params: list[Any] = [match]
        where = 'f.normalized_text match ?'
        if chat_id is not None:
            where += ' and f.chat_id = ?'
            params.append(int(chat_id))
        params.append(int(limit))
        sql = f"""
            select m.*, u.first_name, u.last_name, u.username,
                   bm25(message_fts) as rank
            from message_fts f
            join messages m
              on m.chat_id = f.chat_id
             and m.message_id = f.message_id
            left join users u on u.user_id = m.sender_user_id
            where {where} and m.deleted_at is null
            order by rank asc, m.message_id desc
            limit ?
        """
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [self._row_to_message(row) for row in rows]

    def _stats_sync(self) -> dict[str, int]:
        with self._connect() as conn:
            chats = conn.execute(
                'select count(*) from chats'
            ).fetchone()[0]
            users = conn.execute(
                'select count(*) from users'
            ).fetchone()[0]
            messages = conn.execute(
                'select count(*) from messages where deleted_at is null'
            ).fetchone()[0]
            deleted = conn.execute(
                'select count(*) from messages where deleted_at is not null'
            ).fetchone()[0]
            actions = conn.execute(
                'select count(*) from agent_actions'
            ).fetchone()[0]
        return {
            'chats': int(chats),
            'users': int(users),
            'messages': int(messages),
            'deleted': int(deleted),
            'actions': int(actions),
        }

    def _log_action_sync(
        self,
        chat_id: int,
        trigger_message_id: int | None,
        action_type: str,
        decision: dict[str, Any],
        result: dict[str, Any],
        status: str,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                insert into agent_actions (
                    chat_id, trigger_message_id, action_type,
                    decision_json, result_json, status, created_at
                )
                values (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(chat_id),
                    trigger_message_id,
                    action_type,
                    json.dumps(decision, ensure_ascii=False),
                    json.dumps(result, ensure_ascii=False),
                    status,
                    int(time.time()),
                ),
            )

    @staticmethod
    def _fts_query(query: str) -> str:
        terms = TOKEN_RE.findall(query.lower())
        terms = terms[:8]
        return ' OR '.join(f'"{term}"' for term in terms)

    @staticmethod
    def _row_to_message(row: sqlite3.Row) -> dict[str, Any]:
        sender = 'Unknown'
        first = row['first_name']
        last = row['last_name']
        username = row['username']
        full = ' '.join(
            part for part in (first, last) if part
        ).strip()
        if full:
            sender = full
        elif username:
            sender = username
        return {
            'chat_id': row['chat_id'],
            'message_id': row['message_id'],
            'sender_user_id': row['sender_user_id'],
            'sender': sender,
            'date_ts': row['date_ts'],
            'text': row['text'],
            'caption': row['caption'],
            'normalized_text': row['normalized_text'] or '',
            'media_type': row['media_type'],
        }
