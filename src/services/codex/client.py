import json
import secrets
import time
from typing import Any, Awaitable, Callable

import httpx
from redis.asyncio import Redis

from src.services.codex.constants import (
    DEFAULT_AUTH_KEY,
    DEFAULT_MODEL,
    DEFAULT_REASONING_EFFORT,
    TOKEN_REFRESH_WINDOW,
)
from src.services.codex.oauth import (
    build_authorize_url,
    exchange_code,
    parse_authorization_input,
    refresh_credentials,
)
from src.services.codex.store import CodexAuthStore
from src.services.codex.stream import (
    build_body,
    stream_response,
)
from src.services.codex.tokens import build_pkce_pair


def _extract_function_calls(
    response: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    if not response:
        return []
    output = response.get('output')
    if not isinstance(output, list):
        return []
    return [
        item
        for item in output
        if isinstance(item, dict)
        and item.get('type') == 'function_call'
    ]


def _summarize_output(
    response: dict[str, Any] | None,
) -> str:
    if not response:
        return 'no response'
    output = response.get('output')
    if not isinstance(output, list):
        return f'output={output!r}'
    types = [
        item.get('type')
        for item in output
        if isinstance(item, dict)
    ]
    status = response.get('status')
    incomplete = response.get('incomplete_details')
    return (
        f'status={status!r} types={types!r} '
        f'incomplete={incomplete!r}'
    )


def _passthrough_items(
    response: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """Items from the model's previous turn that must be echoed back
    in the next request so reasoning state and pending tool calls are
    preserved across turns."""
    if not response:
        return []
    output = response.get('output')
    if not isinstance(output, list):
        return []
    items: list[dict[str, Any]] = []
    for item in output:
        if not isinstance(item, dict):
            continue
        if item.get('type') in {'reasoning', 'function_call'}:
            items.append(item)
    return items


class CodexClient:
    def __init__(
        self,
        redis: Redis,
        model: str = DEFAULT_MODEL,
        reasoning_effort: str = DEFAULT_REASONING_EFFORT,
        auth_key: str = DEFAULT_AUTH_KEY,
    ):
        self._model = model
        self._reasoning_effort = reasoning_effort
        self._store = CodexAuthStore(redis, auth_key)
        self._http = httpx.AsyncClient(
            timeout=httpx.Timeout(90.0, connect=15.0),
        )

    @property
    def model(self) -> str:
        return self._model

    @property
    def reasoning_effort(self) -> str:
        return self._reasoning_effort

    async def begin_oauth(self) -> str:
        verifier, challenge = build_pkce_pair()
        state = secrets.token_hex(16)
        await self._store.set_pending(
            {
                'verifier': verifier,
                'state': state,
                'created_at': int(time.time()),
            }
        )
        return build_authorize_url(challenge, state)

    async def complete_oauth(
        self,
        authorization_input: str,
    ) -> dict[str, Any]:
        pending = await self._store.get_pending()
        if not pending:
            raise RuntimeError(
                'No active OAuth flow. Run .codexlogin first.'
            )

        parsed = parse_authorization_input(authorization_input)
        state = parsed.get('state')
        if state and state != pending.get('state'):
            raise RuntimeError('OAuth state mismatch')

        code = parsed.get('code')
        if not code:
            raise RuntimeError('Authorization code not found')

        credentials = await exchange_code(
            self._http,
            code=code,
            verifier=str(pending['verifier']),
        )
        await self._store.set_credentials(credentials)
        return credentials

    async def logout(self) -> None:
        await self._store.clear_all()

    async def get_auth_status(self) -> dict[str, Any]:
        credentials = await self._store.get_credentials()
        pending = await self._store.get_pending()
        return {
            'authenticated': credentials is not None,
            'pending': pending is not None,
            'expires': credentials.get('expires')
            if credentials
            else None,
            'account_id': credentials.get('account_id')
            if credentials
            else None,
            'store_key': self._store.key,
        }

    async def generate(
        self,
        prompt: str,
        system_instruction: str | None = None,
        session_id: str | None = None,
        model: str | None = None,
        reasoning_effort: str | None = None,
    ) -> str:
        return await self.chat(
            messages=[{'role': 'user', 'text': prompt}],
            system_instruction=system_instruction,
            session_id=session_id,
            model=model,
            reasoning_effort=reasoning_effort,
        )

    async def chat(
        self,
        messages: list[dict[str, str]],
        system_instruction: str | None = None,
        session_id: str | None = None,
        model: str | None = None,
        reasoning_effort: str | None = None,
    ) -> str:
        text, _ = await self._run_stream(
            messages=messages,
            system_instruction=system_instruction,
            session_id=session_id,
            model=model,
            reasoning_effort=reasoning_effort,
        )
        if not text:
            raise RuntimeError('Codex returned an empty response')
        return text

    async def chat_with_tools(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]],
        dispatch: Callable[
            [str, dict[str, Any]], Awaitable[str]
        ],
        system_instruction: str | None = None,
        session_id: str | None = None,
        model: str | None = None,
        reasoning_effort: str | None = None,
        max_steps: int = 4,
    ) -> str:
        """Run a multi-turn loop that lets the model call tools.

        ``dispatch(name, args)`` runs the requested tool and returns
        a string the model will see as the tool's output. It should
        also persist any side-effect artifacts (e.g. images) itself.
        """
        extra_input: list[dict[str, Any]] = []
        last_text = ''
        last_response: dict[str, Any] | None = None
        tools_executed = False
        for _ in range(max_steps):
            text, response = await self._run_stream(
                messages=messages,
                system_instruction=system_instruction,
                session_id=session_id,
                model=model,
                reasoning_effort=reasoning_effort,
                tools=tools,
                extra_input=extra_input,
            )
            if text:
                last_text = text
            last_response = response

            calls = _extract_function_calls(response)
            if not calls:
                if last_text:
                    return last_text
                if tools_executed:
                    return ''
                debug = _summarize_output(response)
                raise RuntimeError(
                    f'Codex returned an empty response ({debug})'
                )

            for item in _passthrough_items(response):
                extra_input.append(item)

            tools_executed = True
            for call in calls:
                try:
                    args = (
                        json.loads(call.get('arguments') or '{}')
                        if isinstance(call.get('arguments'), str)
                        else (call.get('arguments') or {})
                    )
                except json.JSONDecodeError as e:
                    output = f'invalid arguments: {e}'
                else:
                    try:
                        output = await dispatch(
                            call.get('name', ''), args
                        )
                    except Exception as e:
                        output = f'error: {e}'
                extra_input.append(
                    {
                        'type': 'function_call_output',
                        'call_id': call.get('call_id'),
                        'output': output,
                    }
                )
        if last_text:
            return last_text
        debug = _summarize_output(last_response)
        raise RuntimeError(
            f'Codex tool loop exceeded max steps ({debug})'
        )

    async def _run_stream(
        self,
        messages: list[dict[str, str]],
        system_instruction: str | None,
        session_id: str | None,
        model: str | None,
        reasoning_effort: str | None,
        tools: list[dict[str, Any]] | None = None,
        extra_input: list[dict[str, Any]] | None = None,
    ) -> tuple[str, dict[str, Any] | None]:
        credentials = await self._ensure_valid_credentials()
        body = build_body(
            messages=messages,
            system_instruction=system_instruction,
            session_id=session_id,
            model=model or self._model,
            reasoning_effort=(
                reasoning_effort or self._reasoning_effort
            ),
            tools=tools,
            extra_input=extra_input,
        )
        try:
            return await stream_response(
                self._http,
                credentials=credentials,
                body=body,
                session_id=session_id,
            )
        except httpx.HTTPStatusError as error:
            if error.response.status_code != 401:
                raise
            refreshed = await refresh_credentials(
                self._http, credentials['refresh']
            )
            await self._store.set_credentials(refreshed)
            return await stream_response(
                self._http,
                credentials=refreshed,
                body=body,
                session_id=session_id,
            )

    async def _ensure_valid_credentials(
        self,
    ) -> dict[str, Any]:
        credentials = await self._store.get_credentials()
        if not credentials:
            pending = await self._store.get_pending()
            if pending:
                raise RuntimeError(
                    'Codex OAuth is pending. Finish it with '
                    '.codexauth <redirect_url>.'
                )
            raise RuntimeError(
                'Codex OAuth is not configured. '
                'Run .codexlogin first.'
            )

        expires = credentials.get('expires')
        if (
            isinstance(expires, int)
            and expires
            > int(time.time()) + TOKEN_REFRESH_WINDOW
        ):
            return credentials

        refreshed = await refresh_credentials(
            self._http, str(credentials['refresh'])
        )
        await self._store.set_credentials(refreshed)
        return refreshed
