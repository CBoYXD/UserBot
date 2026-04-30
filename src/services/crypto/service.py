import httpx

from src.services.crypto.coins import COMMON_COINS
from src.services.crypto.models import CoinPrice


COINGECKO_PRICE = (
    'https://api.coingecko.com/api/v3/simple/price'
)
COINGECKO_SEARCH = (
    'https://api.coingecko.com/api/v3/search'
)


class CryptoService:
    MAX_SYMBOLS = 5

    def __init__(self, timeout: float = 10.0):
        self._timeout = timeout

    async def fetch(self, symbols: list[str]) -> list[CoinPrice]:
        async with httpx.AsyncClient(
            timeout=self._timeout
        ) as http:
            resolved: list[tuple[str, str]] = []
            for s in symbols[: self.MAX_SYMBOLS]:
                pair = await self._resolve(http, s)
                if pair:
                    resolved.append(pair)
            if not resolved:
                return []

            ids = ','.join(cid for cid, _ in resolved)
            resp = await http.get(
                COINGECKO_PRICE,
                params={
                    'ids': ids,
                    'vs_currencies': 'usd',
                    'include_24hr_change': 'true',
                },
            )
            resp.raise_for_status()
            prices = resp.json()

        return [
            CoinPrice(
                symbol=sym,
                usd=(prices.get(cid) or {}).get('usd'),
                change_24h=(prices.get(cid) or {}).get(
                    'usd_24h_change'
                ),
            )
            for cid, sym in resolved
        ]

    @staticmethod
    async def _resolve(
        http: httpx.AsyncClient, query: str
    ) -> tuple[str, str] | None:
        q = query.strip().lower()
        if q in COMMON_COINS:
            return COMMON_COINS[q], q
        resp = await http.get(
            COINGECKO_SEARCH, params={'query': q}
        )
        resp.raise_for_status()
        coins = resp.json().get('coins') or []
        if not coins:
            return None
        top = coins[0]
        return top['id'], (top.get('symbol') or q).lower()

    @staticmethod
    def format_price(usd: float) -> str:
        if usd >= 1:
            return f'${usd:,.2f}'
        return f'${usd:,.6f}'
