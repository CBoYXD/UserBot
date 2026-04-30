import base64
import hashlib
import json
import secrets
from typing import Any

from src.services.codex.constants import JWT_CLAIM_PATH


def b64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode().rstrip('=')


def decode_jwt_payload(token: str) -> dict[str, Any]:
    parts = token.split('.')
    if len(parts) != 3:
        raise ValueError('Invalid access token')
    payload = parts[1]
    padding = '=' * (-len(payload) % 4)
    decoded = base64.urlsafe_b64decode(payload + padding)
    return json.loads(decoded.decode('utf-8'))


def extract_account_id(access_token: str) -> str:
    payload = decode_jwt_payload(access_token)
    account_id = (
        payload.get(JWT_CLAIM_PATH, {})
        .get('chatgpt_account_id')
    )
    if not isinstance(account_id, str) or not account_id:
        raise ValueError(
            'Failed to extract accountId from token'
        )
    return account_id


def build_pkce_pair() -> tuple[str, str]:
    verifier = b64url_encode(secrets.token_bytes(32))
    challenge = b64url_encode(
        hashlib.sha256(verifier.encode('utf-8')).digest()
    )
    return verifier, challenge
