from html import escape

import httpx
from pyrogram import filters
from pyrogram.enums import ParseMode
from pyrogram.types import Message

from src.bot.modules.info.router import HTTP_TIMEOUT, info_router


COINGECKO_PRICE = (
    'https://api.coingecko.com/api/v3/simple/price'
)
COINGECKO_SEARCH = (
    'https://api.coingecko.com/api/v3/search'
)

COMMON_COINS = {
    'btc': 'bitcoin',
    'eth': 'ethereum',
    'sol': 'solana',
    'bnb': 'binancecoin',
    'ada': 'cardano',
    'xrp': 'ripple',
    'doge': 'dogecoin',
    'ton': 'the-open-network',
    'matic': 'polygon-ecosystem-token',
    'dot': 'polkadot',
    'avax': 'avalanche-2',
    'ltc': 'litecoin',
    'trx': 'tron',
    'link': 'chainlink',
    'usdt': 'tether',
    'usdc': 'usd-coin',
}


def _extract_arg(msg: Message) -> str:
    text = msg.text or ''
    parts = text.split(maxsplit=1)
    return parts[1].strip() if len(parts) > 1 else ''


async def _resolve_coin_id(
    http: httpx.AsyncClient, query: str
) -> tuple[str, str] | None:
    """Return (coin_id, symbol) or None."""
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


def _format_price(usd: float) -> str:
    if usd >= 1:
        return f'${usd:,.2f}'
    return f'${usd:,.6f}'


@info_router.message(
    filters.command(['crypto', 'price'], prefixes='.')
)
async def crypto_cmd(msg: Message):
    arg = _extract_arg(msg)
    if not arg:
        await msg.edit(
            '<b>Usage:</b> '
            '<code>.crypto &lt;symbol&gt;</code> '
            '(e.g. <code>btc</code>, <code>eth</code>).',
            parse_mode=ParseMode.HTML,
        )
        return

    symbols = [s.strip() for s in arg.split() if s.strip()]
    await msg.edit(
        '<b>Crypto:</b> <i>fetching…</i>',
        parse_mode=ParseMode.HTML,
    )

    try:
        async with httpx.AsyncClient(
            timeout=HTTP_TIMEOUT
        ) as http:
            resolved: list[tuple[str, str]] = []
            for s in symbols[:5]:
                pair = await _resolve_coin_id(http, s)
                if pair:
                    resolved.append(pair)
            if not resolved:
                await msg.edit(
                    '<b>Crypto:</b> no coins found.',
                    parse_mode=ParseMode.HTML,
                )
                return

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
    except Exception as e:
        await msg.edit(
            f'<b>Crypto error:</b> '
            f'<code>{escape(str(e))}</code>',
            parse_mode=ParseMode.HTML,
        )
        return

    lines = []
    for cid, sym in resolved:
        info = prices.get(cid) or {}
        usd = info.get('usd')
        change = info.get('usd_24h_change')
        if usd is None:
            lines.append(
                f'<b>{escape(sym.upper())}:</b> n/a'
            )
            continue
        change_str = ''
        if change is not None:
            arrow = '🟢' if change >= 0 else '🔴'
            change_str = f' {arrow} {change:+.2f}% (24h)'
        lines.append(
            f'<b>{escape(sym.upper())}</b> '
            f'<code>{_format_price(usd)}</code>{change_str}'
        )

    await msg.edit(
        '<b>💰 Crypto</b>\n' + '\n'.join(lines),
        parse_mode=ParseMode.HTML,
    )
