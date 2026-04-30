import httpx

from src.services.weather.codes import WMO_CODES
from src.services.weather.models import WeatherReport


GEOCODE_URL = 'https://geocoding-api.open-meteo.com/v1/search'
WEATHER_URL = 'https://api.open-meteo.com/v1/forecast'


class WeatherService:
    def __init__(self, timeout: float = 10.0):
        self._timeout = timeout

    async def fetch(self, city: str) -> WeatherReport | None:
        async with httpx.AsyncClient(
            timeout=self._timeout
        ) as http:
            place = await self._geocode(http, city)
            if place is None:
                return None
            current = await self._current(http, place)
        return self._build_report(place, current, city)

    async def _geocode(
        self, http: httpx.AsyncClient, city: str
    ) -> dict | None:
        for language in ('uk', 'ru', 'en'):
            resp = await http.get(
                GEOCODE_URL,
                params={
                    'name': city,
                    'count': 1,
                    'language': language,
                    'format': 'json',
                },
            )
            resp.raise_for_status()
            results = resp.json().get('results') or []
            if results:
                return results[0]
        return None

    async def _current(
        self, http: httpx.AsyncClient, place: dict
    ) -> dict:
        resp = await http.get(
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
        resp.raise_for_status()
        return resp.json().get('current') or {}

    @staticmethod
    def _build_report(
        place: dict, current: dict, city: str
    ) -> WeatherReport:
        code = int(current.get('weather_code', 0))
        icon, desc = WMO_CODES.get(
            code, ('🌡', f'Code {code}')
        )
        name = place.get('name', city)
        country = place.get('country', '')
        location = f'{name}, {country}' if country else name
        return WeatherReport(
            location=location,
            icon=icon,
            description=desc,
            temperature=str(
                current.get('temperature_2m', '?')
            ),
            feels_like=str(
                current.get('apparent_temperature', '?')
            ),
            humidity=str(
                current.get('relative_humidity_2m', '?')
            ),
            wind=str(current.get('wind_speed_10m', '?')),
        )
