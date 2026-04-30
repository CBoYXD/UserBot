from redis.asyncio import Redis


USERS_KEY = 'acl:users'


def _user_key(user_id: int) -> str:
    return f'acl:user:{user_id}'


async def grant(redis: Redis, user_id: int, scope: str) -> bool:
    """Returns True if the scope was newly added."""
    added = await redis.sadd(_user_key(user_id), scope)
    if added:
        await redis.sadd(USERS_KEY, str(user_id))
    return bool(added)


async def revoke(redis: Redis, user_id: int, scope: str) -> bool:
    removed = await redis.srem(_user_key(user_id), scope)
    if removed and not await redis.scard(_user_key(user_id)):
        await redis.srem(USERS_KEY, str(user_id))
    return bool(removed)


async def revoke_all(redis: Redis, user_id: int) -> int:
    count = await redis.scard(_user_key(user_id))
    await redis.delete(_user_key(user_id))
    await redis.srem(USERS_KEY, str(user_id))
    return int(count)


async def list_grants(redis: Redis, user_id: int) -> set[str]:
    raw = await redis.smembers(_user_key(user_id))
    return {x.decode('utf-8') for x in raw}


async def list_users(redis: Redis) -> list[int]:
    raw = await redis.smembers(USERS_KEY)
    return sorted(int(x.decode('utf-8')) for x in raw)


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
