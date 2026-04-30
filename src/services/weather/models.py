from dataclasses import dataclass


@dataclass
class WeatherReport:
    location: str
    icon: str
    description: str
    temperature: str
    feels_like: str
    humidity: str
    wind: str
