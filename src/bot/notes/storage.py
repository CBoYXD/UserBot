import json
import re
import time

from redis.asyncio import Redis


NOTES_KEY = 'notes:list'
NOTES_NEXT_ID = 'notes:next_id'
TAG_RE = re.compile(r'#([\w\-_]+)', re.UNICODE)


async def next_id(redis: Redis) -> int:
    return int(await redis.incr(NOTES_NEXT_ID))


async def save(
    redis: Redis, nid: int, text: str
) -> list[str]:
    tags = sorted(set(TAG_RE.findall(text)))
    payload = json.dumps(
        {
            'text': text,
            'ts': int(time.time()),
            'tags': tags,
        },
        ensure_ascii=False,
    )
    await redis.hset(NOTES_KEY, str(nid), payload)
    return tags


async def get(redis: Redis, nid: str) -> dict | None:
    raw = await redis.hget(NOTES_KEY, nid)
    if not raw:
        return None
    return json.loads(raw)


async def delete(redis: Redis, nid: str) -> bool:
    return bool(await redis.hdel(NOTES_KEY, nid))


async def all_notes(
    redis: Redis,
) -> list[tuple[int, dict]]:
    raw = await redis.hgetall(NOTES_KEY)
    items: list[tuple[int, dict]] = []
    for k, v in raw.items():
        try:
            items.append(
                (int(k.decode('utf-8')), json.loads(v))
            )
        except Exception:
            continue
    items.sort(key=lambda x: x[0])
    return items
