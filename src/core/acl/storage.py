from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

import aiosqlite
from redis.asyncio import Redis


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
        create table if not exists acl_grants (
            user_id integer not null,
            scope text not null,
            created_at integer not null default (
                cast(strftime('%s', 'now') as integer)
            ),
            primary key (user_id, scope)
        )
        """
    )


async def grant(redis: Redis, user_id: int, scope: str) -> bool:
    """Returns True if the scope was newly added."""
    async with _connect() as db:
        await _init(db)
        cursor = await db.execute(
            """
            insert or ignore into acl_grants (user_id, scope)
            values (?, ?)
            """,
            (int(user_id), scope),
        )
        await db.commit()
        return cursor.rowcount > 0


async def revoke(redis: Redis, user_id: int, scope: str) -> bool:
    async with _connect() as db:
        await _init(db)
        cursor = await db.execute(
            """
            delete from acl_grants
            where user_id = ? and scope = ?
            """,
            (int(user_id), scope),
        )
        await db.commit()
        return cursor.rowcount > 0


async def revoke_all(redis: Redis, user_id: int) -> int:
    async with _connect() as db:
        await _init(db)
        cursor = await db.execute(
            'delete from acl_grants where user_id = ?',
            (int(user_id),),
        )
        await db.commit()
        return int(cursor.rowcount)


async def list_grants(redis: Redis, user_id: int) -> set[str]:
    async with _connect() as db:
        await _init(db)
        cursor = await db.execute(
            'select scope from acl_grants where user_id = ?',
            (int(user_id),),
        )
        rows = await cursor.fetchall()
    return {str(row['scope']) for row in rows}


async def list_users(redis: Redis) -> list[int]:
    async with _connect() as db:
        await _init(db)
        cursor = await db.execute(
            """
            select distinct user_id
            from acl_grants
            order by user_id asc
            """
        )
        rows = await cursor.fetchall()
    return [int(row['user_id']) for row in rows]


async def has_grant(
    redis: Redis,
    user_id: int,
    module: str,
    commands: set[str],
) -> bool:
    grants = await list_grants(redis, user_id)
    if '*' in grants:
        return True
    if f'module:{module}' in grants:
        return True
    return any(f'cmd:{c}' in grants for c in commands)
