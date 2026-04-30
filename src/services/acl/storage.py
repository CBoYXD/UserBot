from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from redis.asyncio import Redis

from src.db.models.acl import AclGrant


_session_factory: async_sessionmaker[AsyncSession] | None = None


def init_storage(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    global _session_factory
    _session_factory = session_factory


def _sf() -> async_sessionmaker[AsyncSession]:
    if _session_factory is None:
        raise RuntimeError('ACL storage not initialised')
    return _session_factory


async def grant(redis: Redis, user_id: int, scope: str) -> bool:
    """Returns True if the scope was newly added."""
    async with _sf()() as session:
        async with session.begin():
            result = await session.execute(
                sqlite_insert(AclGrant)
                .values(user_id=int(user_id), scope=scope)
                .on_conflict_do_nothing()
            )
            return result.rowcount > 0


async def revoke(redis: Redis, user_id: int, scope: str) -> bool:
    async with _sf()() as session:
        async with session.begin():
            result = await session.execute(
                delete(AclGrant).where(
                    AclGrant.user_id == int(user_id),
                    AclGrant.scope == scope,
                )
            )
            return result.rowcount > 0


async def revoke_all(redis: Redis, user_id: int) -> int:
    async with _sf()() as session:
        async with session.begin():
            result = await session.execute(
                delete(AclGrant).where(
                    AclGrant.user_id == int(user_id)
                )
            )
            return int(result.rowcount)


async def list_grants(
    redis: Redis, user_id: int
) -> set[str]:
    async with _sf()() as session:
        rows = (
            await session.execute(
                select(AclGrant.scope).where(
                    AclGrant.user_id == int(user_id)
                )
            )
        ).scalars().all()
    return set(rows)


async def list_users(redis: Redis) -> list[int]:
    async with _sf()() as session:
        rows = (
            await session.execute(
                select(AclGrant.user_id)
                .distinct()
                .order_by(AclGrant.user_id)
            )
        ).scalars().all()
    return [int(r) for r in rows]


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
