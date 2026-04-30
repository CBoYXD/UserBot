from dataclasses import dataclass


@dataclass
class CoinPrice:
    symbol: str
    usd: float | None
    change_24h: float | None
