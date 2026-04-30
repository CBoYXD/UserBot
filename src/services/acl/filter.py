from __future__ import annotations

from pyrogram import filters as pyrofilters
from pyrogram.filters import Filter, create
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.services.acl import storage


_redis: Redis | None = None


def init_acl(
    redis: Redis,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    global _redis
    _redis = redis
    storage.init_storage(session_factory)


def acl_filter(module: str, *commands: str) -> Filter:
    """Pyrogram filter that passes for the owner or for granted users."""
    cmd_set = set(commands)

    async def _check(_, __, msg) -> bool:
        if msg.from_user is None:
            return False
        if msg.from_user.is_self:
            return True
        if _redis is None:
            return False
        return await storage.has_grant(
            _redis, msg.from_user.id, module, cmd_set
        )

    return create(_check, name=f'acl[{module}]')


def cmd(module: str, *commands: str) -> Filter:
    """Combined filter: command match (cheap) AND ACL gate (Redis call)."""
    return (
        pyrofilters.command(list(commands), prefixes='.')
        & acl_filter(module, *commands)
    )
