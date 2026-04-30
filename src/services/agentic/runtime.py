from __future__ import annotations

import json
import time
from html import escape
from typing import Any

from redis.asyncio import Redis

from src.config import AgenticSettings, OllamaSettings
from src.services.agentic.storage import AgenticStorage
from src.services.ollama import OllamaClient


INGEST_KEY = 'agentic:settings:ingest_enabled'
HEALTH_KEY = 'agentic:ollama:health'
MODEL_KEY = 'agentic:settings:chat_model'
RECENT_KEY = 'agentic:recent:{chat_id}'
AUTO_REPLY_KEY = 'agentic:settings:auto_reply:{chat_id}'
AUTO_REPLY_COOLDOWN_KEY = 'agentic:autoreply:cooldown:{chat_id}'


class AgenticRuntime:
    def __init__(
        self,
        *,
        redis: Redis,
        settings: AgenticSettings,
        ollama_settings: OllamaSettings,
    ):
        self.redis = redis
        self.settings = settings
        self.ollama_settings = ollama_settings
        self.storage = AgenticStorage(settings.db_path)
        self.ollama = OllamaClient(
            base_url=ollama_settings.base_url,
            chat_model=ollama_settings.chat_model,
            embed_model=ollama_settings.embed_model,
            timeout=ollama_settings.timeout,
        )

    async def start(self) -> None:
        await self.storage.init()

    async def close(self) -> None:
        await self.ollama.close()

    async def chat_model(self) -> str:
        raw = await self.redis.get(MODEL_KEY)
        if raw:
            return raw.decode('utf-8').strip()
        return self.ollama_settings.chat_model

    async def set_chat_model(self, model: str) -> None:
        await self.redis.set(MODEL_KEY, model.strip())
        await self.redis.delete(HEALTH_KEY)

    async def ingest_enabled(self) -> bool:
        raw = await self.redis.get(INGEST_KEY)
        if raw is None:
            return self.settings.ingest_enabled
        return raw.decode('utf-8') == '1'

    async def set_ingest_enabled(self, enabled: bool) -> None:
        await self.redis.set(INGEST_KEY, '1' if enabled else '0')

    async def auto_reply_enabled(self, chat_id: int) -> bool:
        raw = await self.redis.get(
            AUTO_REPLY_KEY.format(chat_id=chat_id)
        )
        if raw is None:
            return self.settings.auto_reply_default
        return raw.decode('utf-8') == '1'

    async def set_auto_reply(
        self, chat_id: int, enabled: bool
    ) -> None:
        await self.redis.set(
            AUTO_REPLY_KEY.format(chat_id=chat_id),
            '1' if enabled else '0',
        )

    async def acquire_auto_reply_slot(
        self, chat_id: int, ttl: int = 30
    ) -> bool:
        return bool(
            await self.redis.set(
                AUTO_REPLY_COOLDOWN_KEY.format(chat_id=chat_id),
                str(int(time.time())),
                ex=ttl,
                nx=True,
            )
        )

    async def ollama_health(self) -> tuple[bool, str]:
        raw = await self.redis.get(HEALTH_KEY)
        now = int(time.time())
        if raw:
            try:
                cached = json.loads(raw.decode('utf-8'))
            except Exception:
                cached = None
            if (
                isinstance(cached, dict)
                and now - int(cached.get('ts') or 0)
                <= self.ollama_settings.health_ttl
            ):
                return bool(cached.get('ok')), str(
                    cached.get('reason')
                )

        ok, reason = await self.ollama.health(await self.chat_model())
        await self.redis.set(
            HEALTH_KEY,
            json.dumps(
                {'ok': ok, 'reason': reason, 'ts': now},
                ensure_ascii=False,
            ),
            ex=max(1, self.ollama_settings.health_ttl),
        )
        return ok, reason

    async def require_ollama(self) -> tuple[bool, str]:
        if not self.settings.require_ollama:
            return True, 'not required'
        return await self.ollama_health()

    async def push_recent(self, item: dict[str, Any]) -> None:
        text = item.get('normalized_text') or ''
        if not text:
            return
        key = RECENT_KEY.format(chat_id=item['chat_id'])
        payload = {
            'message_id': item['message_id'],
            'sender': item.get('sender_name') or 'Unknown',
            'text': text,
            'ts': item.get('date_ts'),
        }
        await self.redis.lpush(
            key, json.dumps(payload, ensure_ascii=False)
        )
        await self.redis.ltrim(
            key, 0, self.settings.recent_cache_size - 1
        )

    async def recent_from_cache(
        self, chat_id: int, limit: int = 30
    ) -> list[dict[str, Any]]:
        raw_items = await self.redis.lrange(
            RECENT_KEY.format(chat_id=chat_id), 0, max(0, limit - 1)
        )
        items: list[dict[str, Any]] = []
        for raw in raw_items:
            try:
                items.append(json.loads(raw.decode('utf-8')))
            except Exception:
                continue
        items.reverse()
        return items

    async def build_prompt_context(
        self,
        *,
        chat_id: int,
        query: str,
        recent_limit: int = 30,
    ) -> str:
        recent = await self.recent_from_cache(chat_id, recent_limit)
        if not recent:
            stored = await self.storage.recent_messages(
                chat_id, recent_limit
            )
            recent = [
                {
                    'message_id': item['message_id'],
                    'sender': item['sender'],
                    'text': item['normalized_text'],
                }
                for item in stored
            ]
        matches = await self.storage.search_messages(
            query,
            chat_id=chat_id,
            limit=self.settings.search_limit,
        )
        lines: list[str] = []
        if recent:
            lines.append('Recent chat messages:')
            for item in recent[-recent_limit:]:
                sender = item.get('sender') or 'Unknown'
                text = item.get('text') or ''
                lines.append(f'- {sender}: {text}')
        if matches:
            lines.append('')
            lines.append('Relevant stored messages:')
            for item in matches:
                text = item.get('normalized_text') or ''
                sender = item.get('sender') or 'Unknown'
                lines.append(f'- {sender}: {text}')
        return '\n'.join(lines)

    @staticmethod
    def format_search_results(items: list[dict[str, Any]]) -> str:
        if not items:
            return '<b>Agent memory:</b> no matches.'
        lines = ['<b>Agent memory matches</b>']
        for item in items:
            sender = escape(str(item.get('sender') or 'Unknown'))
            text = escape(str(item.get('normalized_text') or ''))
            mid = item.get('message_id')
            lines.append(
                f'<code>{mid}</code> <b>{sender}:</b> {text}'
            )
        return '\n'.join(lines)
