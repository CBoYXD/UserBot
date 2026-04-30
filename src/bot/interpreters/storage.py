from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

import aiosqlite
from redis.asyncio import Redis

from src.services.code_pars.base import ParseCode


DB_PATH = Path('data/userbot.sqlite3')


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
        create table if not exists code_snippets (
            name text primary key,
            language text not null,
            code text not null
        )
        """
    )


async def save_snippet(
    redis: Redis, name: str, parse_code: ParseCode
) -> None:
    async with _connect() as db:
        await _init(db)
        await db.execute(
            """
            insert into code_snippets (name, language, code)
            values (?, ?, ?)
            on conflict(name) do update set
                language = excluded.language,
                code = excluded.code
            """,
            (name, parse_code.language, parse_code.code),
        )
        await db.commit()


async def load_snippet(redis: Redis, name: str) -> ParseCode:
    async with _connect() as db:
        await _init(db)
        cursor = await db.execute(
            'select language, code from code_snippets where name = ?',
            (name,),
        )
        row = await cursor.fetchone()
    if row is None:
        raise ValueError(f'Snippet "{name}" was not found.')

    language = str(row['language']).strip()
    code = str(row['code'])
    if not language or not code:
        raise ValueError(f'Snippet "{name}" is invalid.')
    return ParseCode(language=language, code=code)


async def delete_snippet(redis: Redis, name: str) -> bool:
    async with _connect() as db:
        await _init(db)
        cursor = await db.execute(
            'delete from code_snippets where name = ?',
            (name,),
        )
        await db.commit()
        return cursor.rowcount > 0


async def list_snippets(redis: Redis) -> list[tuple[str, str]]:
    async with _connect() as db:
        await _init(db)
        cursor = await db.execute(
            'select name, language from code_snippets order by name asc'
        )
        rows = await cursor.fetchall()
    return [
        (str(row['name']), str(row['language'] or 'text'))
        for row in rows
    ]
