from __future__ import annotations

import json
import time
import uuid
from html import escape
from typing import Any

from redis.asyncio import Redis

from src.config import AgenticSettings, OllamaSettings
from src.services.agentic.storage import AgenticStorage
from src.services.agentic.tools import build_readonly_tools
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
        if not item.get('normalized_text'):
            return
        key = RECENT_KEY.format(chat_id=item['chat_id'])
        payload = {
            'message_id': item['message_id'],
            'sender_user_id': item.get('sender_user_id'),
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
        recent = await self.storage.recent_messages(
            chat_id, recent_limit
        )
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
                text = item.get('normalized_text') or ''
                lines.append(f'- {sender}: {text}')
        if matches:
            lines.append('')
            lines.append('Relevant stored messages:')
            for item in matches:
                text = item.get('normalized_text') or ''
                sender = item.get('sender') or 'Unknown'
                lines.append(f'- {sender}: {text}')
        return '\n'.join(lines)

    async def run_readonly_tool_loop(
        self,
        *,
        chat_id: int,
        prompt: str,
        system: str,
        allow_global: bool,
        source: str = 'agent',
        trigger_message_id: int | None = None,
        max_steps: int | None = None,
    ) -> str:
        ok, reason = await self.require_ollama()
        if not ok:
            raise RuntimeError(f'Local Ollama unavailable: {reason}')

        tools, dispatch = build_readonly_tools(
            self,
            current_chat_id=chat_id,
            allow_global=allow_global,
        )
        messages: list[dict[str, Any]] = [
            {'role': 'user', 'content': prompt}
        ]
        steps = max_steps or self.settings.max_agent_steps
        last_content = ''
        trace_id = uuid.uuid4().hex[:12]
        await self.storage.log_trace(
            trace_id=trace_id,
            chat_id=chat_id,
            trigger_message_id=trigger_message_id,
            source=source,
            event_type='loop_start',
            payload={
                'allow_global': allow_global,
                'max_steps': steps,
                'prompt': _preview(prompt, 1200),
            },
        )
        for _ in range(max(1, steps)):
            step = (
                len(
                    [
                        item
                        for item in messages
                        if item.get('role') == 'assistant'
                    ]
                )
                + 1
            )
            try:
                result = await self.ollama.chat(
                    messages,
                    model=await self.chat_model(),
                    system=system,
                    tools=tools,
                )
            except Exception as e:
                await self.storage.log_trace(
                    trace_id=trace_id,
                    chat_id=chat_id,
                    trigger_message_id=trigger_message_id,
                    source=source,
                    event_type='model_error',
                    payload={'step': step, 'error': str(e)},
                )
                raise
            message = result.raw.get('message') or {}
            if result.content:
                last_content = result.content
            tool_calls = message.get('tool_calls') or []
            await self.storage.log_trace(
                trace_id=trace_id,
                chat_id=chat_id,
                trigger_message_id=trigger_message_id,
                source=source,
                event_type='model_response',
                payload={
                    'step': step,
                    'content': _preview(result.content, 1200),
                    'tool_calls': [
                        _tool_call_summary(call)
                        for call in tool_calls
                    ],
                },
            )
            if not tool_calls:
                if result.content:
                    await self.storage.log_trace(
                        trace_id=trace_id,
                        chat_id=chat_id,
                        trigger_message_id=trigger_message_id,
                        source=source,
                        event_type='loop_done',
                        payload={
                            'step': step,
                            'answer': _preview(result.content, 1200),
                        },
                    )
                    return result.content
                break

            messages.append(_assistant_message(message))
            for call in tool_calls:
                name, args = _tool_call_parts(call)
                try:
                    output = await dispatch(name, args)
                    ok_result = True
                except Exception as e:
                    output = f'error: {e}'
                    ok_result = False
                await self.storage.log_trace(
                    trace_id=trace_id,
                    chat_id=chat_id,
                    trigger_message_id=trigger_message_id,
                    source=source,
                    event_type='tool_result',
                    payload={
                        'step': step,
                        'tool': name,
                        'args': args,
                        'ok': ok_result,
                        'result': _preview(output, 2000),
                    },
                )
                messages.append(
                    {
                        'role': 'tool',
                        'tool_name': name,
                        'content': output,
                    }
                )

        if last_content:
            await self.storage.log_trace(
                trace_id=trace_id,
                chat_id=chat_id,
                trigger_message_id=trigger_message_id,
                source=source,
                event_type='loop_done',
                payload={'answer': _preview(last_content, 1200)},
            )
            return last_content
        await self.storage.log_trace(
            trace_id=trace_id,
            chat_id=chat_id,
            trigger_message_id=trigger_message_id,
            source=source,
            event_type='loop_error',
            payload={'error': 'no answer'},
        )
        raise RuntimeError(
            'Local Ollama tool loop returned no answer'
        )

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


def _assistant_message(message: dict[str, Any]) -> dict[str, Any]:
    return {
        'role': 'assistant',
        'content': str(message.get('content') or ''),
        'tool_calls': message.get('tool_calls') or [],
    }


def _tool_call_parts(
    call: dict[str, Any],
) -> tuple[str, dict[str, Any]]:
    function = call.get('function') or {}
    name = str(function.get('name') or '')
    args = function.get('arguments') or {}
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except json.JSONDecodeError:
            args = {}
    if not isinstance(args, dict):
        args = {}
    return name, args


def _tool_call_summary(call: dict[str, Any]) -> dict[str, Any]:
    name, args = _tool_call_parts(call)
    return {'tool': name, 'args': args}


def _preview(value: Any, limit: int) -> str:
    text = str(value or '')
    if len(text) <= limit:
        return text
    return text[: limit - 3] + '...'
