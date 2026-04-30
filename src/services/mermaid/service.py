import base64

import httpx


MERMAID_INK_URL = 'https://mermaid.ink/img'


def _encode_source(source: str) -> str:
    raw = source.encode('utf-8')
    return (
        base64.urlsafe_b64encode(raw)
        .rstrip(b'=')
        .decode('ascii')
    )


class MermaidService:
    def __init__(self, timeout: float = 20.0):
        self._timeout = timeout

    async def render(self, source: str) -> bytes:
        encoded = _encode_source(source)
        url = f'{MERMAID_INK_URL}/{encoded}?theme=dark&bgColor=!1e1e2e'
        async with httpx.AsyncClient(
            timeout=self._timeout
        ) as http:
            resp = await http.get(url)
            if resp.status_code >= 400:
                detail = (
                    resp.text.strip()
                    or resp.reason_phrase
                    or f'HTTP {resp.status_code}'
                )
                raise ValueError(detail)
            return resp.content
