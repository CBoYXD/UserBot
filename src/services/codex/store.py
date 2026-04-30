import json
from typing import Any

from redis.asyncio import Redis

from src.services.codex.constants import DEFAULT_AUTH_KEY


class CodexAuthStore:
    def __init__(
        self,
        redis: Redis,
        key: str = DEFAULT_AUTH_KEY,
    ):
        self._redis = redis
        self._key = key

    @property
    def key(self) -> str:
        return self._key

    async def get_pending(self) -> dict[str, Any] | None:
        return await self._get_json_field('pending')

    async def set_pending(
        self, pending: dict[str, Any]
    ) -> None:
        await self._set_json_field('pending', pending)

    async def get_credentials(self) -> dict[str, Any] | None:
        return await self._get_json_field('credentials')

    async def set_credentials(
        self, credentials: dict[str, Any]
    ) -> None:
        await self._redis.hset(
            self._key,
            mapping={
                'credentials': json.dumps(
                    credentials,
                    ensure_ascii=False,
                )
            },
        )
        await self._redis.hdel(self._key, 'pending')

    async def clear_all(self) -> None:
        await self._redis.delete(self._key)

    async def _get_json_field(
        self,
        field: str,
    ) -> dict[str, Any] | None:
        raw = await self._redis.hget(self._key, field)
        if raw is None:
            return None
        value = json.loads(raw.decode('utf-8'))
        return value if isinstance(value, dict) else None

    async def _set_json_field(
        self,
        field: str,
        value: dict[str, Any],
    ) -> None:
        await self._redis.hset(
            self._key,
            field,
            json.dumps(value, ensure_ascii=False),
        )
