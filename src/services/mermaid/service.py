import httpx


KROKI_URL = 'https://kroki.io/mermaid/png'


class MermaidService:
    def __init__(self, timeout: float = 20.0):
        self._timeout = timeout

    async def render(self, source: str) -> bytes:
        async with httpx.AsyncClient(
            timeout=self._timeout
        ) as http:
            resp = await http.post(
                KROKI_URL,
                content=source.encode('utf-8'),
                headers={'Content-Type': 'text/plain'},
            )
            if resp.status_code >= 400:
                detail = resp.text.strip() or resp.reason_phrase
                raise ValueError(detail)
            return resp.content
