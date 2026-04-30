from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx


@dataclass(frozen=True)
class OllamaChatResult:
    content: str
    raw: dict[str, Any]


class OllamaClient:
    def __init__(
        self,
        *,
        base_url: str,
        chat_model: str,
        embed_model: str = '',
        timeout: float = 120.0,
    ):
        self.base_url = base_url.rstrip('/')
        self.chat_model = chat_model
        self.embed_model = embed_model
        self._http = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(timeout, connect=5.0),
        )

    async def close(self) -> None:
        await self._http.aclose()

    async def health(
        self, model: str | None = None
    ) -> tuple[bool, str]:
        target = (model or self.chat_model).strip()
        if not target:
            return False, 'chat model is empty'
        try:
            names = await self.list_models()
        except Exception as e:
            return False, f'ollama unavailable: {e}'

        if target not in names:
            return False, f'local model not found: {target}'
        return True, 'ok'

    async def list_models(self) -> set[str]:
        response = await self._http.get('/api/tags')
        response.raise_for_status()
        data = response.json()
        models = data.get('models') or []
        return {
            str(item.get('name') or '').strip()
            for item in models
            if isinstance(item, dict)
            and str(item.get('name') or '').strip()
        }

    async def resolve_model(self, preferred: str) -> str | None:
        names = await self.list_models()
        if preferred in names:
            return preferred
        latest = f'{preferred}:latest'
        if latest in names:
            return latest
        for name in sorted(names):
            if name == preferred or name.startswith(f'{preferred}:'):
                return name
        return None

    async def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        model: str | None = None,
        system: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        format: dict[str, Any] | str | None = None,
        options: dict[str, Any] | None = None,
        think: bool | str | None = None,
        stream: bool = False,
    ) -> OllamaChatResult:
        payload: dict[str, Any] = {
            'model': model or self.chat_model,
            'messages': messages,
            'stream': stream,
        }
        if system:
            payload['messages'] = [
                {'role': 'system', 'content': system},
                *messages,
            ]
        if tools:
            payload['tools'] = tools
        if format is not None:
            payload['format'] = format
        if options:
            payload['options'] = options
        if think is not None:
            payload['think'] = think

        response = await self._http.post('/api/chat', json=payload)
        response.raise_for_status()
        data = response.json()
        message = data.get('message') or {}
        content = str(message.get('content') or '')
        return OllamaChatResult(content=content, raw=data)

    async def embed(
        self,
        input: str | list[str],
        *,
        model: str | None = None,
        truncate: bool = True,
    ) -> list[list[float]]:
        target = model or self.embed_model
        if not target:
            raise RuntimeError(
                'Ollama embedding model is not configured'
            )
        response = await self._http.post(
            '/api/embed',
            json={
                'model': target,
                'input': input,
                'truncate': truncate,
            },
        )
        response.raise_for_status()
        data = response.json()
        embeddings = data.get('embeddings')
        if not isinstance(embeddings, list):
            raise RuntimeError(
                'Ollama returned invalid embeddings payload'
            )
        return embeddings
