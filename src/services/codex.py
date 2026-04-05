import base64
import hashlib
import json
import secrets
import time

from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

import httpx


AUTHORIZE_URL = 'https://auth.openai.com/oauth/authorize'
TOKEN_URL = 'https://auth.openai.com/oauth/token'
RESPONSES_URL = 'https://chatgpt.com/backend-api/codex/responses'
CLIENT_ID = 'app_EMoamEEZ73f0CkXaXp7hrann'
REDIRECT_URI = 'http://localhost:1455/auth/callback'
SCOPE = 'openid profile email offline_access'
JWT_CLAIM_PATH = 'https://api.openai.com/auth'
TOKEN_REFRESH_WINDOW = 60


def _b64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode().rstrip('=')


def _decode_jwt_payload(token: str) -> dict[str, Any]:
    parts = token.split('.')
    if len(parts) != 3:
        raise ValueError('Invalid access token')
    payload = parts[1]
    padding = '=' * (-len(payload) % 4)
    decoded = base64.urlsafe_b64decode(payload + padding)
    return json.loads(decoded.decode('utf-8'))


def _extract_account_id(access_token: str) -> str:
    payload = _decode_jwt_payload(access_token)
    account_id = (
        payload.get(JWT_CLAIM_PATH, {})
        .get('chatgpt_account_id')
    )
    if not isinstance(account_id, str) or not account_id:
        raise ValueError('Failed to extract accountId from token')
    return account_id


def _build_pkce_pair() -> tuple[str, str]:
    verifier = _b64url_encode(secrets.token_bytes(32))
    challenge = _b64url_encode(
        hashlib.sha256(verifier.encode('utf-8')).digest()
    )
    return verifier, challenge


def _extract_response_text(response: dict[str, Any]) -> str:
    output = response.get('output')
    if not isinstance(output, list):
        return ''

    parts: list[str] = []
    for item in output:
        if not isinstance(item, dict):
            continue
        if item.get('type') != 'message':
            continue
        content = item.get('content')
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get('type') in {'output_text', 'refusal'}:
                text = block.get('text')
                if isinstance(text, str) and text:
                    parts.append(text)
    return ''.join(parts)


class CodexAuthStore:
    def __init__(self, file_path: str):
        self._path = Path(file_path)

    @property
    def path(self) -> str:
        return str(self._path)

    def _load(self) -> dict[str, Any]:
        if not self._path.exists():
            return {}
        with self._path.open('r', encoding='utf-8') as fp:
            return json.load(fp)

    def _save(self, data: dict[str, Any]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open('w', encoding='utf-8') as fp:
            json.dump(data, fp, ensure_ascii=False, indent=2)

    def get_pending(self) -> dict[str, Any] | None:
        data = self._load()
        pending = data.get('pending')
        return pending if isinstance(pending, dict) else None

    def set_pending(self, pending: dict[str, Any]) -> None:
        data = self._load()
        data['pending'] = pending
        self._save(data)

    def get_credentials(self) -> dict[str, Any] | None:
        data = self._load()
        credentials = data.get('credentials')
        return (
            credentials
            if isinstance(credentials, dict)
            else None
        )

    def set_credentials(self, credentials: dict[str, Any]) -> None:
        data = self._load()
        data['credentials'] = credentials
        data.pop('pending', None)
        self._save(data)

    def clear_all(self) -> None:
        self._save({})


class CodexClient:
    def __init__(
        self,
        model: str = 'gpt-5.4',
        reasoning_effort: str = 'medium',
        credentials_path: str = '.config/codex-oauth.json',
    ):
        self._model = model
        self._reasoning_effort = reasoning_effort
        self._store = CodexAuthStore(credentials_path)
        self._http = httpx.AsyncClient(
            timeout=httpx.Timeout(90.0, connect=15.0),
        )

    @property
    def model(self) -> str:
        return self._model

    @property
    def reasoning_effort(self) -> str:
        return self._reasoning_effort

    def begin_oauth(self) -> str:
        verifier, challenge = _build_pkce_pair()
        state = secrets.token_hex(16)
        self._store.set_pending(
            {
                'verifier': verifier,
                'state': state,
                'created_at': int(time.time()),
            }
        )
        params = {
            'response_type': 'code',
            'client_id': CLIENT_ID,
            'redirect_uri': REDIRECT_URI,
            'scope': SCOPE,
            'code_challenge': challenge,
            'code_challenge_method': 'S256',
            'state': state,
            'id_token_add_organizations': 'true',
            'codex_cli_simplified_flow': 'true',
            'originator': 'pi',
        }
        return f'{AUTHORIZE_URL}?{urlencode(params)}'

    async def complete_oauth(self, authorization_input: str) -> dict[str, Any]:
        pending = self._store.get_pending()
        if not pending:
            raise RuntimeError(
                'No active OAuth flow. Run .codexlogin first.'
            )

        parsed = self._parse_authorization_input(
            authorization_input
        )
        state = parsed.get('state')
        if state and state != pending.get('state'):
            raise RuntimeError('OAuth state mismatch')

        code = parsed.get('code')
        if not code:
            raise RuntimeError('Authorization code not found')

        credentials = await self._exchange_code(
            code=code,
            verifier=str(pending['verifier']),
        )
        self._store.set_credentials(credentials)
        return credentials

    def logout(self) -> None:
        self._store.clear_all()

    def get_auth_status(self) -> dict[str, Any]:
        credentials = self._store.get_credentials()
        pending = self._store.get_pending()
        return {
            'authenticated': credentials is not None,
            'pending': pending is not None,
            'expires': credentials.get('expires')
            if credentials
            else None,
            'account_id': credentials.get('account_id')
            if credentials
            else None,
            'credentials_path': self._store.path,
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
        credentials = await self._ensure_valid_credentials()
        selected_model = model or self._model
        selected_effort = (
            reasoning_effort or self._reasoning_effort
        )
        body = self._build_body(
            messages=messages,
            system_instruction=system_instruction,
            session_id=session_id,
            model=selected_model,
            reasoning_effort=selected_effort,
        )
        try:
            return await self._stream_response(
                credentials=credentials,
                body=body,
                session_id=session_id,
            )
        except httpx.HTTPStatusError as error:
            if error.response.status_code != 401:
                raise
            refreshed = await self._refresh_credentials(
                credentials['refresh']
            )
            self._store.set_credentials(refreshed)
            return await self._stream_response(
                credentials=refreshed,
                body=body,
                session_id=session_id,
            )

    def _parse_authorization_input(
        self,
        authorization_input: str,
    ) -> dict[str, str]:
        value = authorization_input.strip()
        if not value:
            return {}

        try:
            parsed_url = urlparse(value)
            if parsed_url.scheme and parsed_url.netloc:
                params = parse_qs(parsed_url.query)
                if params:
                    return {
                        key: values[0]
                        for key, values in params.items()
                        if values
                    }
        except ValueError:
            pass

        if value.startswith('code=') or '&code=' in value:
            params = parse_qs(value)
            return {
                key: values[0]
                for key, values in params.items()
                if values
            }

        if '#' in value:
            code, state = value.split('#', 1)
            return {'code': code, 'state': state}

        return {'code': value}

    async def _exchange_code(
        self,
        code: str,
        verifier: str,
    ) -> dict[str, Any]:
        response = await self._http.post(
            TOKEN_URL,
            data={
                'grant_type': 'authorization_code',
                'client_id': CLIENT_ID,
                'code': code,
                'code_verifier': verifier,
                'redirect_uri': REDIRECT_URI,
            },
            headers={
                'Content-Type': 'application/x-www-form-urlencoded',
            },
        )
        response.raise_for_status()
        payload = response.json()
        access_token = payload.get('access_token')
        refresh_token = payload.get('refresh_token')
        expires_in = payload.get('expires_in')
        if (
            not isinstance(access_token, str)
            or not isinstance(refresh_token, str)
            or not isinstance(expires_in, int)
        ):
            raise RuntimeError('Invalid token response')

        return {
            'access': access_token,
            'refresh': refresh_token,
            'expires': int(time.time()) + expires_in,
            'account_id': _extract_account_id(access_token),
        }

    async def _refresh_credentials(
        self,
        refresh_token: str,
    ) -> dict[str, Any]:
        response = await self._http.post(
            TOKEN_URL,
            data={
                'grant_type': 'refresh_token',
                'refresh_token': refresh_token,
                'client_id': CLIENT_ID,
            },
            headers={
                'Content-Type': 'application/x-www-form-urlencoded',
            },
        )
        response.raise_for_status()
        payload = response.json()
        access_token = payload.get('access_token')
        next_refresh_token = payload.get('refresh_token')
        expires_in = payload.get('expires_in')
        if (
            not isinstance(access_token, str)
            or not isinstance(next_refresh_token, str)
            or not isinstance(expires_in, int)
        ):
            raise RuntimeError('Invalid refresh response')

        return {
            'access': access_token,
            'refresh': next_refresh_token,
            'expires': int(time.time()) + expires_in,
            'account_id': _extract_account_id(access_token),
        }

    async def _ensure_valid_credentials(self) -> dict[str, Any]:
        credentials = self._store.get_credentials()
        if not credentials:
            raise RuntimeError(
                'Codex OAuth is not configured. Run .codexlogin first.'
            )

        expires = credentials.get('expires')
        if (
            isinstance(expires, int)
            and expires > int(time.time()) + TOKEN_REFRESH_WINDOW
        ):
            return credentials

        refreshed = await self._refresh_credentials(
            str(credentials['refresh'])
        )
        self._store.set_credentials(refreshed)
        return refreshed

    def _build_body(
        self,
        messages: list[dict[str, str]],
        system_instruction: str | None,
        session_id: str | None,
        model: str,
        reasoning_effort: str,
    ) -> dict[str, Any]:
        input_messages: list[dict[str, Any]] = []
        for index, message in enumerate(messages):
            role = message.get('role')
            text = message.get('text', '')
            if role == 'user':
                input_messages.append(
                    {
                        'role': 'user',
                        'content': [
                            {
                                'type': 'input_text',
                                'text': text,
                            }
                        ],
                    }
                )
                continue

            input_messages.append(
                {
                    'type': 'message',
                    'role': 'assistant',
                    'content': [
                        {
                            'type': 'output_text',
                            'text': text,
                            'annotations': [],
                        }
                    ],
                    'status': 'completed',
                    'id': f'msg_{index}',
                }
            )

        body: dict[str, Any] = {
            'model': model,
            'store': False,
            'stream': True,
            'input': input_messages,
            'text': {'verbosity': 'medium'},
            'include': ['reasoning.encrypted_content'],
            'tool_choice': 'auto',
            'parallel_tool_calls': True,
        }
        if system_instruction:
            body['instructions'] = system_instruction
        if session_id:
            body['prompt_cache_key'] = session_id
        if reasoning_effort:
            body['reasoning'] = {
                'effort': self._clamp_reasoning_effort(
                    reasoning_effort
                ),
                'summary': 'auto',
            }
        return body

    def _clamp_reasoning_effort(
        self,
        reasoning_effort: str,
    ) -> str:
        if reasoning_effort == 'minimal':
            return 'low'
        return reasoning_effort

    def _build_headers(
        self,
        credentials: dict[str, Any],
        session_id: str | None,
    ) -> dict[str, str]:
        headers = {
            'Authorization': f"Bearer {credentials['access']}",
            'chatgpt-account-id': str(credentials['account_id']),
            'originator': 'pi',
            'User-Agent': 'UserBot Codex OAuth',
            'OpenAI-Beta': 'responses=experimental',
            'accept': 'text/event-stream',
            'content-type': 'application/json',
        }
        if session_id:
            headers['session_id'] = session_id
        return headers

    async def _stream_response(
        self,
        credentials: dict[str, Any],
        body: dict[str, Any],
        session_id: str | None,
    ) -> str:
        headers = self._build_headers(credentials, session_id)
        text_parts: list[str] = []
        final_response: dict[str, Any] | None = None
        async with self._http.stream(
            'POST',
            RESPONSES_URL,
            headers=headers,
            json=body,
        ) as response:
            if response.status_code >= 400:
                detail = await response.aread()
                message = detail.decode('utf-8', errors='replace')
                raise httpx.HTTPStatusError(
                    message,
                    request=response.request,
                    response=response,
                )

            event_lines: list[str] = []
            async for line in response.aiter_lines():
                if not line:
                    final_response = self._process_sse_event(
                        event_lines,
                        text_parts,
                        final_response,
                    )
                    event_lines = []
                    continue
                if line.startswith('data:'):
                    event_lines.append(line[5:].strip())

            if event_lines:
                final_response = self._process_sse_event(
                    event_lines,
                    text_parts,
                    final_response,
                )

        text = ''.join(text_parts).strip()
        if text:
            return text
        if final_response:
            fallback = _extract_response_text(final_response).strip()
            if fallback:
                return fallback
        raise RuntimeError('Codex returned an empty response')

    def _process_sse_event(
        self,
        event_lines: list[str],
        text_parts: list[str],
        final_response: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        if not event_lines:
            return final_response

        payload = '\n'.join(event_lines).strip()
        if not payload or payload == '[DONE]':
            return final_response

        event = json.loads(payload)
        event_type = event.get('type')
        if event_type == 'error':
            message = event.get('message') or 'Codex error'
            raise RuntimeError(str(message))
        if event_type == 'response.failed':
            error = event.get('response', {}).get('error', {})
            message = error.get('message') or 'Codex response failed'
            raise RuntimeError(str(message))
        if event_type in {
            'response.output_text.delta',
            'response.refusal.delta',
        }:
            delta = event.get('delta')
            if isinstance(delta, str):
                text_parts.append(delta)
            return final_response
        if event_type in {
            'response.completed',
            'response.done',
            'response.incomplete',
        }:
            response = event.get('response')
            if isinstance(response, dict):
                return response
        return final_response
