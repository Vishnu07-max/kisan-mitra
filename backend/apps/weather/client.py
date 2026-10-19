"""Open-Meteo client: one call, strict timeout, normalized output. No data is ever invented."""
import json
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
CURRENT = ["temperature_2m", "relative_humidity_2m", "precipitation", "weather_code", "wind_speed_10m"]
DAILY = [
    "temperature_2m_max", "temperature_2m_min", "precipitation_sum",
    "precipitation_probability_max", "weather_code", "wind_speed_10m_max",
]


class WeatherUnavailable(Exception):
    """The weather service could not be reached or returned something unexpected."""


def _num(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def condition_from_code(code):
    """Group WMO weather codes into a few keys the front end can translate."""
    code = _num(code)
    if code is None:
        return "unknown"
    code = int(code)
    if code == 0:
        return "clear"
    if code in (1, 2, 3):
        return "cloudy"
    if code in (45, 48):
        return "fog"
    if 51 <= code <= 57:
        return "drizzle"
    if 61 <= code <= 67:
        return "rain"
    if 71 <= code <= 77 or code in (85, 86):
        return "snow"
    if 80 <= code <= 82:
        return "showers"
    if 95 <= code <= 99:
        return "thunderstorm"
    return "unknown"


def normalize(data):
    """Turn the service's response into a stable shape, or raise WeatherUnavailable."""
    try:
        cur, daily = data["current"], data["daily"]
        dates = daily["time"]
        series = {key: daily[key] for key in DAILY}
        if any(len(values) != len(dates) for values in series.values()):
            raise ValueError("daily arrays differ in length")
        days = [
            {
                "date": date,
                "temp_max_c": _num(series["temperature_2m_max"][i]),
                "temp_min_c": _num(series["temperature_2m_min"][i]),
                "rain_mm": _num(series["precipitation_sum"][i]),
                "rain_probability_pct": _num(series["precipitation_probability_max"][i]),
                "wind_max_kmh": _num(series["wind_speed_10m_max"][i]),
                "condition": condition_from_code(series["weather_code"][i]),
            }
            for i, date in enumerate(dates)
        ]
        return {
            "timezone": data.get("timezone"),
            "current": {
                "time": cur.get("time"),
                "temperature_c": _num(cur.get("temperature_2m")),
                "humidity_pct": _num(cur.get("relative_humidity_2m")),
                "rain_mm": _num(cur.get("precipitation")),
                "wind_kmh": _num(cur.get("wind_speed_10m")),
                "condition": condition_from_code(cur.get("weather_code")),
            },
            "daily": days,
        }
    except (KeyError, TypeError, ValueError, AttributeError, IndexError) as exc:
        raise WeatherUnavailable("Unexpected response from the weather service.") from exc


def fetch_forecast(lat, lon, days=7):
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": ",".join(CURRENT),
        "daily": ",".join(DAILY),
        "timezone": "auto",
        "forecast_days": days,
    }
    request = urllib.request.Request(
        FORECAST_URL + "?" + urllib.parse.urlencode(params),
        headers={"User-Agent": "KisanMitra/0.1 (student project)"},
    )
    try:
        with urllib.request.urlopen(request, timeout=settings.WEATHER_TIMEOUT_SECONDS) as response:
            raw = response.read(2_000_000)
        data = json.loads(raw)
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        raise WeatherUnavailable(str(exc)) from exc
    return normalize(data)