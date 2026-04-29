import json

from redis.asyncio import Redis


REMINDERS_KEY = 'reminders:list'
REMINDERS_QUEUE = 'reminders:queue'
REMINDERS_NEXT_ID = 'reminders:next_id'


async def next_id(redis: Redis) -> int:
    return int(await redis.incr(REMINDERS_NEXT_ID))


async def add(
    redis: Redis,
    rid: int,
    *,
    chat_id: int,
    reply_to: int,
    text: str,
    ts: int,
) -> None:
    payload = json.dumps(
        {
            'chat_id': chat_id,
            'reply_to': reply_to,
            'text': text,
            'ts': ts,
        },
        ensure_ascii=False,
    )
    await redis.hset(REMINDERS_KEY, str(rid), payload)
    await redis.zadd(REMINDERS_QUEUE, {str(rid): ts})


async def get(redis: Redis, rid: str) -> dict | None:
    raw = await redis.hget(REMINDERS_KEY, rid)
    if raw is None:
        return None
    return json.loads(raw)


async def delete(redis: Redis, rid: str) -> bool:
    deleted = await redis.hdel(REMINDERS_KEY, rid)
    await redis.zrem(REMINDERS_QUEUE, rid)
    return bool(deleted)


async def all_reminders(
    redis: Redis,
) -> list[tuple[int, dict]]:
    raw = await redis.hgetall(REMINDERS_KEY)
    items: list[tuple[int, dict]] = []
    for k, v in raw.items():
        try:
            items.append(
                (int(k.decode('utf-8')), json.loads(v))
            )
        except Exception:
            continue
    items.sort(key=lambda x: x[1].get('ts', 0))
    return items


async def pop_due(redis: Redis, now: int) -> list[str]:
    raw_ids = await redis.zrangebyscore(
        REMINDERS_QUEUE, 0, now, start=0, num=20
    )
    return [
        r.decode('utf-8')
        if isinstance(r, (bytes, bytearray))
        else str(r)
        for r in raw_ids
    ]
