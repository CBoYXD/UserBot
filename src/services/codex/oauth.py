import time
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

import httpx

from src.services.codex.constants import (
    AUTHORIZE_URL,
    CLIENT_ID,
    REDIRECT_URI,
    SCOPE,
    TOKEN_URL,
)
from src.services.codex.tokens import extract_account_id


def build_authorize_url(challenge: str, state: str) -> str:
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


def parse_authorization_input(
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


async def exchange_code(
    http: httpx.AsyncClient,
    code: str,
    verifier: str,
) -> dict[str, Any]:
    response = await http.post(
        TOKEN_URL,
        data={
            'grant_type': 'authorization_code',
            'client_id': CLIENT_ID,
            'code': code,
            'code_verifier': verifier,
            'redirect_uri': REDIRECT_URI,
        },
        headers={
            'Content-Type': (
                'application/x-www-form-urlencoded'
            ),
        },
    )
    response.raise_for_status()
    return _credentials_from_response(response.json())


async def refresh_credentials(
    http: httpx.AsyncClient,
    refresh_token: str,
) -> dict[str, Any]:
    response = await http.post(
        TOKEN_URL,
        data={
            'grant_type': 'refresh_token',
            'refresh_token': refresh_token,
            'client_id': CLIENT_ID,
        },
        headers={
            'Content-Type': (
                'application/x-www-form-urlencoded'
            ),
        },
    )
    response.raise_for_status()
    return _credentials_from_response(response.json())


def _credentials_from_response(
    payload: dict[str, Any],
) -> dict[str, Any]:
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
        'account_id': extract_account_id(access_token),
    }
