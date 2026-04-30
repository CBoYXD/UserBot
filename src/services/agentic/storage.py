from __future__ import annotations

import json
import re
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator

import aiosqlite


TOKEN_RE = re.compile(r'[\w\-]{2,}', re.UNICODE)


class AgenticStorage:
    def __init__(self, db_path: str):
        self.path = Path(db_path)

    async def init(self) -> None:
        async with self._connect() as db:
            await db.executescript(
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

                create table if not exists agent_traces (
                    id integer primary key autoincrement,
                    trace_id text not null,
                    chat_id integer not null,
                    trigger_message_id integer,
                    source text not null,
                    event_type text not null,
                    payload_json text not null default '{}',
                    created_at integer not null
                );

                create index if not exists idx_agent_traces_trace_id
                on agent_traces(trace_id, id);

                create index if not exists idx_agent_traces_chat_id
                on agent_traces(chat_id, id);
                """
            )
            await db.commit()

    async def upsert_message(self, item: dict[str, Any]) -> None:
        now = int(time.time())
        chat_id = int(item['chat_id'])
        message_id = int(item['message_id'])
        text = item.get('normalized_text') or ''
        async with self._connect() as db:
            await db.execute(
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
                await db.execute(
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
            await db.execute(
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
            await db.execute(
                """
                delete from message_fts
                where chat_id = ? and message_id = ?
                """,
                (chat_id, message_id),
            )
            if text:
                await db.execute(
                    """
                    insert into message_fts (
                        chat_id, message_id, normalized_text
                    )
                    values (?, ?, ?)
                    """,
                    (chat_id, message_id, text),
                )
            await db.commit()

    async def mark_deleted(
        self, chat_id: int, message_ids: list[int]
    ) -> int:
        if not message_ids:
            return 0
        now = int(time.time())
        async with self._connect() as db:
            count = 0
            for mid in message_ids:
                cursor = await db.execute(
                    """
                    update messages
                    set deleted_at = ?
                    where chat_id = ? and message_id = ?
                    """,
                    (now, chat_id, int(mid)),
                )
                await db.execute(
                    """
                    delete from message_fts
                    where chat_id = ? and message_id = ?
                    """,
                    (chat_id, int(mid)),
                )
                count += cursor.rowcount
            await db.commit()
            return count

    async def recent_messages(
        self, chat_id: int, limit: int = 40
    ) -> list[dict[str, Any]]:
        async with self._connect() as db:
            cursor = await db.execute(
                """
                select m.*, u.first_name, u.last_name, u.username
                from messages m
                left join users u on u.user_id = m.sender_user_id
                where m.chat_id = ? and m.deleted_at is null
                order by m.message_id desc
                limit ?
                """,
                (int(chat_id), int(limit)),
            )
            rows = await cursor.fetchall()
        items = [self._row_to_message(row) for row in rows]
        items.reverse()
        return items

    async def get_message(
        self, chat_id: int, message_id: int
    ) -> dict[str, Any] | None:
        async with self._connect() as db:
            cursor = await db.execute(
                """
                select m.*, u.first_name, u.last_name, u.username
                from messages m
                left join users u on u.user_id = m.sender_user_id
                where m.chat_id = ?
                  and m.message_id = ?
                  and m.deleted_at is null
                """,
                (int(chat_id), int(message_id)),
            )
            row = await cursor.fetchone()
        return self._row_to_message(row) if row else None

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
        async with self._connect() as db:
            before_cursor = await db.execute(
                """
                select m.*, u.first_name, u.last_name, u.username
                from messages m
                left join users u on u.user_id = m.sender_user_id
                where m.chat_id = ?
                  and m.message_id < ?
                  and m.deleted_at is null
                order by m.message_id desc
                limit ?
                """,
                (int(chat_id), int(message_id), before),
            )
            before_rows = await before_cursor.fetchall()
            current_cursor = await db.execute(
                """
                select m.*, u.first_name, u.last_name, u.username
                from messages m
                left join users u on u.user_id = m.sender_user_id
                where m.chat_id = ?
                  and m.message_id = ?
                  and m.deleted_at is null
                """,
                (int(chat_id), int(message_id)),
            )
            current_row = await current_cursor.fetchone()
            after_cursor = await db.execute(
                """
                select m.*, u.first_name, u.last_name, u.username
                from messages m
                left join users u on u.user_id = m.sender_user_id
                where m.chat_id = ?
                  and m.message_id > ?
                  and m.deleted_at is null
                order by m.message_id asc
                limit ?
                """,
                (int(chat_id), int(message_id), after),
            )
            after_rows = await after_cursor.fetchall()
        rows = list(reversed(before_rows))
        if current_row:
            rows.append(current_row)
        rows.extend(after_rows)
        return [self._row_to_message(row) for row in rows]

    async def list_chats(
        self,
        *,
        query: str | None = None,
        limit: int = 30,
    ) -> list[dict[str, Any]]:
        limit = max(1, min(limit, 100))
        params: list[Any] = []
        where = ''
        if query:
            needle = f'%{query.strip()}%'
            where = 'where title like ? or username like ?'
            params.extend([needle, needle])
        params.append(limit)
        async with self._connect() as db:
            cursor = await db.execute(
                f"""
                select c.*,
                       (
                         select count(*)
                         from messages m
                         where m.chat_id = c.chat_id
                           and m.deleted_at is null
                       ) as message_count
                from chats c
                {where}
                order by c.last_seen_at desc
                limit ?
                """,
                params,
            )
            rows = await cursor.fetchall()
        return [self._row_to_chat(row) for row in rows]

    async def chat_stats(self, chat_id: int) -> dict[str, Any]:
        async with self._connect() as db:
            chat_cursor = await db.execute(
                'select * from chats where chat_id = ?',
                (int(chat_id),),
            )
            chat = await chat_cursor.fetchone()
            messages = await self._count(
                db,
                'messages',
                f'chat_id = {int(chat_id)} and deleted_at is null',
            )
            deleted = await self._count(
                db,
                'messages',
                f'chat_id = {int(chat_id)} and deleted_at is not null',
            )
            users_cursor = await db.execute(
                """
                select count(distinct sender_user_id)
                from messages
                where chat_id = ?
                  and sender_user_id is not null
                  and deleted_at is null
                """,
                (int(chat_id),),
            )
            users_row = await users_cursor.fetchone()
        return {
            'chat': self._row_to_chat(chat) if chat else None,
            'messages': messages,
            'deleted': deleted,
            'users': int(users_row[0]) if users_row else 0,
        }

    async def user_messages(
        self,
        user_id: int,
        *,
        chat_id: int | None = None,
        limit: int = 30,
    ) -> list[dict[str, Any]]:
        limit = max(1, min(limit, 100))
        params: list[Any] = [int(user_id)]
        where = 'm.sender_user_id = ? and m.deleted_at is null'
        if chat_id is not None:
            where += ' and m.chat_id = ?'
            params.append(int(chat_id))
        params.append(limit)
        async with self._connect() as db:
            cursor = await db.execute(
                f"""
                select m.*, u.first_name, u.last_name, u.username
                from messages m
                left join users u on u.user_id = m.sender_user_id
                where {where}
                order by m.message_id desc
                limit ?
                """,
                params,
            )
            rows = await cursor.fetchall()
        items = [self._row_to_message(row) for row in rows]
        items.reverse()
        return items

    async def search_messages(
        self,
        query: str,
        *,
        chat_id: int | None = None,
        limit: int = 12,
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
        async with self._connect() as db:
            cursor = await db.execute(sql, params)
            rows = await cursor.fetchall()
        return [self._row_to_message(row) for row in rows]

    async def stats(self) -> dict[str, int]:
        async with self._connect() as db:
            chats = await self._count(db, 'chats')
            users = await self._count(db, 'users')
            messages = await self._count(
                db,
                'messages',
                'deleted_at is null',
            )
            deleted = await self._count(
                db,
                'messages',
                'deleted_at is not null',
            )
            actions = await self._count(db, 'agent_actions')
            traces = await self._count(db, 'agent_traces')
        return {
            'chats': chats,
            'users': users,
            'messages': messages,
            'deleted': deleted,
            'actions': actions,
            'traces': traces,
        }

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
        async with self._connect() as db:
            await db.execute(
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
            await db.commit()

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
        async with self._connect() as db:
            await db.execute(
                """
                insert into agent_traces (
                    trace_id, chat_id, trigger_message_id,
                    source, event_type, payload_json, created_at
                )
                values (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    trace_id,
                    int(chat_id),
                    trigger_message_id,
                    source,
                    event_type,
                    json.dumps(payload, ensure_ascii=False),
                    int(time.time()),
                ),
            )
            await db.commit()

    async def recent_traces(
        self,
        *,
        limit: int = 30,
        chat_id: int | None = None,
        trace_id: str | None = None,
    ) -> list[dict[str, Any]]:
        limit = max(1, min(limit, 200))
        params: list[Any] = []
        where = ''
        if trace_id:
            where = 'where trace_id = ?'
            params.append(trace_id)
        elif chat_id is not None:
            where = 'where chat_id = ?'
            params.append(int(chat_id))
        params.append(limit)
        async with self._connect() as db:
            cursor = await db.execute(
                f"""
                select *
                from agent_traces
                {where}
                order by id desc
                limit ?
                """,
                params,
            )
            rows = await cursor.fetchall()
        items = [self._row_to_trace(row) for row in rows]
        items.reverse()
        return items

    @asynccontextmanager
    async def _connect(
        self,
    ) -> AsyncIterator[aiosqlite.Connection]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(str(self.path)) as db:
            db.row_factory = aiosqlite.Row
            await db.execute('pragma journal_mode=wal')
            await db.execute('pragma foreign_keys=on')
            yield db

    @staticmethod
    async def _count(
        db: aiosqlite.Connection,
        table: str,
        where: str | None = None,
    ) -> int:
        sql = f'select count(*) from {table}'
        if where is not None:
            sql += f' where {where}'
        cursor = await db.execute(sql)
        row = await cursor.fetchone()
        return int(row[0])

    @staticmethod
    def _fts_query(query: str) -> str:
        terms = TOKEN_RE.findall(query.lower())
        terms = terms[:8]
        return ' OR '.join(f'"{term}"' for term in terms)

    @staticmethod
    def _row_to_message(row: aiosqlite.Row) -> dict[str, Any]:
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

    @staticmethod
    def _row_to_chat(row: aiosqlite.Row) -> dict[str, Any]:
        return {
            'chat_id': row['chat_id'],
            'type': row['type'],
            'title': row['title'],
            'username': row['username'],
            'first_seen_at': row['first_seen_at'],
            'last_seen_at': row['last_seen_at'],
            'memory_enabled': bool(row['memory_enabled']),
            'auto_reply_enabled': bool(row['auto_reply_enabled']),
            'message_count': row['message_count']
            if 'message_count' in row.keys()
            else None,
        }

    @staticmethod
    def _row_to_trace(row: aiosqlite.Row) -> dict[str, Any]:
        try:
            payload = json.loads(row['payload_json'])
        except Exception:
            payload = {}
        return {
            'id': row['id'],
            'trace_id': row['trace_id'],
            'chat_id': row['chat_id'],
            'trigger_message_id': row['trigger_message_id'],
            'source': row['source'],
            'event_type': row['event_type'],
            'payload': payload,
            'created_at': row['created_at'],
        }
