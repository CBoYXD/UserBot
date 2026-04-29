import json

from redis.asyncio import Redis

from src.services.code_pars.base import ParseCode


CODE_SNIPPETS_KEY = 'storage:code:snippets'


async def save_snippet(
    redis: Redis, name: str, parse_code: ParseCode
) -> None:
    payload = json.dumps(
        {
            'language': parse_code.language,
            'code': parse_code.code,
        },
        ensure_ascii=False,
    )
    await redis.hset(CODE_SNIPPETS_KEY, name, payload)


async def load_snippet(
    redis: Redis,
    name: str,
) -> ParseCode:
    raw_payload = await redis.hget(
        CODE_SNIPPETS_KEY,
        name,
    )
    if raw_payload is None:
        raise ValueError(f'Snippet "{name}" was not found.')

    payload = json.loads(raw_payload.decode('utf-8'))
    language = str(payload.get('language', '')).strip()
    code = str(payload.get('code', ''))
    if not language or not code:
        raise ValueError(f'Snippet "{name}" is invalid.')
    return ParseCode(language=language, code=code)


async def delete_snippet(redis: Redis, name: str) -> bool:
    return bool(await redis.hdel(CODE_SNIPPETS_KEY, name))


async def list_snippets(
    redis: Redis,
) -> list[tuple[str, str]]:
    raw_items = await redis.hgetall(CODE_SNIPPETS_KEY)
    snippets: list[tuple[str, str]] = []
    for raw_name, raw_payload in raw_items.items():
        name = raw_name.decode('utf-8')
        payload = json.loads(raw_payload.decode('utf-8'))
        language = str(payload.get('language', 'text'))
        snippets.append((name, language))
    snippets.sort(key=lambda item: item[0])
    return snippets
