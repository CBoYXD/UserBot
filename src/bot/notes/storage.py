import json
import re
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

import aiosqlite
from redis.asyncio import Redis


DB_PATH = Path('data/userbot.sqlite3')
TAG_RE = re.compile(r'#([\w\-_]+)', re.UNICODE)


@asynccontextmanager
async def _connect() -> AsyncIterator[aiosqlite.Connection]:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(str(DB_PATH)) as db:
        db.row_factory = aiosqlite.Row
        await db.execute('pragma journal_mode=wal')
        yield db


async def _init(db: aiosqlite.Connection) -> None:
    await db.execute(
        """
        create table if not exists notes (
            id integer primary key autoincrement,
            text text not null,
            ts integer not null,
            tags_json text not null default '[]'
        )
        """
    )


async def next_id(redis: Redis) -> int:
    async with _connect() as db:
        await _init(db)
        cursor = await db.execute(
            'insert into notes (text, ts, tags_json) values (?, ?, ?)',
            ('', int(time.time()), '[]'),
        )
        await db.commit()
        return int(cursor.lastrowid)


async def save(redis: Redis, nid: int, text: str) -> list[str]:
    tags = sorted(set(TAG_RE.findall(text)))
    async with _connect() as db:
        await _init(db)
        await db.execute(
            """
            update notes
            set text = ?, ts = ?, tags_json = ?
            where id = ?
            """,
            (
                text,
                int(time.time()),
                json.dumps(tags, ensure_ascii=False),
                int(nid),
            ),
        )
        await db.commit()
    return tags


async def get(redis: Redis, nid: str) -> dict | None:
    note_id = _parse_id(nid)
    if note_id is None:
        return None
    async with _connect() as db:
        await _init(db)
        cursor = await db.execute(
            'select * from notes where id = ? and text != ?',
            (note_id, ''),
        )
        row = await cursor.fetchone()
    return _row_to_note(row) if row else None


async def delete(redis: Redis, nid: str) -> bool:
    note_id = _parse_id(nid)
    if note_id is None:
        return False
    async with _connect() as db:
        await _init(db)
        cursor = await db.execute(
            'delete from notes where id = ?',
            (note_id,),
        )
        await db.commit()
        return cursor.rowcount > 0


async def all_notes(redis: Redis) -> list[tuple[int, dict]]:
    async with _connect() as db:
        await _init(db)
        cursor = await db.execute(
            'select * from notes where text != ? order by id asc',
            ('',),
        )
        rows = await cursor.fetchall()
    return [(int(row['id']), _row_to_note(row)) for row in rows]


def _row_to_note(row: aiosqlite.Row) -> dict:
    try:
        tags = json.loads(row['tags_json'])
    except Exception:
        tags = []
    return {
        'text': row['text'],
        'ts': row['ts'],
        'tags': tags,
    }


def _parse_id(value: str) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
