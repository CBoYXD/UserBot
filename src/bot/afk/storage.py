import time

from redis.asyncio import Redis


AFK_ENABLED_KEY = 'afk:enabled'
AFK_REASON_KEY = 'afk:reason'
AFK_SINCE_KEY = 'afk:since'
AFK_REPLY_TTL = 600


async def enable(redis: Redis, reason: str) -> None:
    await redis.set(AFK_ENABLED_KEY, '1')
    await redis.set(AFK_REASON_KEY, reason)
    await redis.set(AFK_SINCE_KEY, str(int(time.time())))


async def disable(redis: Redis) -> bool:
    """Returns True if AFK was enabled before."""
    was = await redis.get(AFK_ENABLED_KEY)
    await redis.delete(
        AFK_ENABLED_KEY, AFK_REASON_KEY, AFK_SINCE_KEY
    )
    return bool(was)


async def is_enabled(redis: Redis) -> bool:
    return bool(await redis.get(AFK_ENABLED_KEY))


async def get_state(
    redis: Redis,
) -> tuple[str, int]:
    """Return (reason, since_ts)."""
    raw_reason = await redis.get(AFK_REASON_KEY)
    raw_since = await redis.get(AFK_SINCE_KEY)
    reason = raw_reason.decode('utf-8') if raw_reason else ''
    since = (
        int(raw_since.decode('utf-8')) if raw_since else 0
    )
    return reason, since


async def mark_replied(redis: Redis, user_id: int) -> bool:
    """Mark user as replied; return True if first reply."""
    key = f'afk:replied:{user_id}'
    if await redis.get(key):
        return False
    await redis.set(key, '1', ex=AFK_REPLY_TTL)
    return True


def humanize(seconds: int) -> str:
    if seconds < 60:
        return f'{seconds}s'
    if seconds < 3600:
        return f'{seconds // 60}m'
    if seconds < 86400:
        return f'{seconds // 3600}h'
    return f'{seconds // 86400}d'
