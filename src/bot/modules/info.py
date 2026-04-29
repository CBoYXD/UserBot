from html import escape

import httpx
from pyrogram import filters
from pyrogram.enums import ParseMode
from pyrogram.types import Message

from src.bot.tools.router import Router


info_router = Router('info')
info_router.router_filters = filters.me

GEOCODE_URL = 'https://geocoding-api.open-meteo.com/v1/search'
WEATHER_URL = 'https://api.open-meteo.com/v1/forecast'
COINGECKO_PRICE = (
    'https://api.coingecko.com/api/v3/simple/price'
)
COINGECKO_SEARCH = (
    'https://api.coingecko.com/api/v3/search'
)
HTTP_TIMEOUT = 10.0

WMO_CODES = {
    0: ('☀️', 'Clear'),
    1: ('🌤', 'Mainly clear'),
    2: ('⛅', 'Partly cloudy'),
    3: ('☁️', 'Overcast'),
    45: ('🌫', 'Fog'),
    48: ('🌫', 'Rime fog'),
    51: ('🌦', 'Light drizzle'),
    53: ('🌦', 'Drizzle'),
    55: ('🌧', 'Heavy drizzle'),
    61: ('🌦', 'Light rain'),
    63: ('🌧', 'Rain'),
    65: ('🌧', 'Heavy rain'),
    71: ('🌨', 'Light snow'),
    73: ('🌨', 'Snow'),
    75: ('❄️', 'Heavy snow'),
    77: ('❄️', 'Snow grains'),
    80: ('🌦', 'Rain showers'),
    81: ('🌧', 'Heavy rain showers'),
    82: ('⛈', 'Violent rain'),
    85: ('🌨', 'Snow showers'),
    86: ('❄️', 'Heavy snow showers'),
    95: ('⛈', 'Thunderstorm'),
    96: ('⛈', 'Thunderstorm w/ hail'),
    99: ('⛈', 'Thunderstorm w/ heavy hail'),
}

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


@info_router.message(filters.command('weather', prefixes='.'))
async def weather_cmd(msg: Message):
    city = _extract_arg(msg)
    if not city:
        await msg.edit(
            '<b>Usage:</b> <code>.weather &lt;city&gt;</code>',
            parse_mode=ParseMode.HTML,
        )
        return

    await msg.edit(
        f'<b>Weather:</b> <i>looking up {escape(city)}…</i>',
        parse_mode=ParseMode.HTML,
    )

    try:
        async with httpx.AsyncClient(
            timeout=HTTP_TIMEOUT
        ) as http:
            geo = await http.get(
                GEOCODE_URL,
                params={
                    'name': city,
                    'count': 1,
                    'language': 'en',
                    'format': 'json',
                },
            )
            geo.raise_for_status()
            data = geo.json()
            results = data.get('results') or []
            if not results:
                await msg.edit(
                    f'<b>Weather:</b> city '
                    f'<code>{escape(city)}</code> not found.',
                    parse_mode=ParseMode.HTML,
                )
                return
            place = results[0]

            weather = await http.get(
                WEATHER_URL,
                params={
                    'latitude': place['latitude'],
                    'longitude': place['longitude'],
                    'current': (
                        'temperature_2m,relative_humidity_2m,'
                        'apparent_temperature,weather_code,'
                        'wind_speed_10m'
                    ),
                    'timezone': 'auto',
                },
            )
            weather.raise_for_status()
            cur = weather.json().get('current') or {}
    except Exception as e:
        await msg.edit(
            f'<b>Weather error:</b> '
            f'<code>{escape(str(e))}</code>',
            parse_mode=ParseMode.HTML,
        )
        return

    code = int(cur.get('weather_code', 0))
    icon, desc = WMO_CODES.get(code, ('🌡', f'Code {code}'))
    name = place.get('name', city)
    country = place.get('country', '')
    location = (
        f'{name}, {country}' if country else name
    )

    text = (
        f'<b>{icon} {escape(location)}</b>\n'
        f'<b>{desc}</b>\n'
        f'🌡 <b>{cur.get("temperature_2m", "?")}°C</b> '
        f'(feels {cur.get("apparent_temperature", "?")}°C)\n'
        f'💧 Humidity: {cur.get("relative_humidity_2m", "?")}%\n'
        f'💨 Wind: {cur.get("wind_speed_10m", "?")} km/h'
    )
    await msg.edit(text, parse_mode=ParseMode.HTML)


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
        if usd >= 1:
            price_str = f'${usd:,.2f}'
        else:
            price_str = f'${usd:,.6f}'
        if change is None:
            change_str = ''
        else:
            arrow = '🟢' if change >= 0 else '🔴'
            change_str = f' {arrow} {change:+.2f}% (24h)'
        lines.append(
            f'<b>{escape(sym.upper())}</b> '
            f'<code>{price_str}</code>{change_str}'
        )

    await msg.edit(
        '<b>💰 Crypto</b>\n' + '\n'.join(lines),
        parse_mode=ParseMode.HTML,
    )
