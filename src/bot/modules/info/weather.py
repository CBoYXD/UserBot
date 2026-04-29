from html import escape

import httpx
from pyrogram import filters
from pyrogram.enums import ParseMode
from pyrogram.types import Message

from src.bot.modules.info.router import HTTP_TIMEOUT, info_router


GEOCODE_URL = 'https://geocoding-api.open-meteo.com/v1/search'
WEATHER_URL = 'https://api.open-meteo.com/v1/forecast'

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
            results = (geo.json().get('results') or [])
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
    location = f'{name}, {country}' if country else name

    text = (
        f'<b>{icon} {escape(location)}</b>\n'
        f'<b>{desc}</b>\n'
        f'🌡 <b>{cur.get("temperature_2m", "?")}°C</b> '
        f'(feels {cur.get("apparent_temperature", "?")}°C)\n'
        f'💧 Humidity: {cur.get("relative_humidity_2m", "?")}%\n'
        f'💨 Wind: {cur.get("wind_speed_10m", "?")} km/h'
    )
    await msg.edit(text, parse_mode=ParseMode.HTML)
