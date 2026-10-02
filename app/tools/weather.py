import httpx

from app.config import Settings
from app.tools.base import EchoTool, ToolResult

WMO_CONDITIONS = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Rime fog", 51: "Light drizzle", 53: "Drizzle",
    55: "Heavy drizzle", 56: "Light freezing drizzle", 57: "Heavy freezing drizzle",
    61: "Light rain", 63: "Rain", 65: "Heavy rain", 66: "Light freezing rain",
    67: "Heavy freezing rain", 71: "Light snow", 73: "Snow", 75: "Heavy snow",
    77: "Snow grains", 80: "Light rain showers", 81: "Rain showers",
    82: "Heavy rain showers", 85: "Light snow showers", 86: "Heavy snow showers",
    95: "Thunderstorm", 96: "Thunderstorm with light hail", 99: "Thunderstorm with heavy hail",
}


class WeatherTool(EchoTool):
    name = "weather"
    description = "Get free Open-Meteo current weather, forecasts, and rain probability."
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["current", "today_forecast", "forecast", "seven_day_forecast", "rain_probability"],
            },
            "location": {"type": "string"},
            "days": {"type": "integer", "minimum": 1, "maximum": 7},
        },
        "required": ["action", "location"],
    }

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def run(self, arguments: dict) -> ToolResult:
        action = arguments.get("action", "current")
        query = arguments.get("location")
        if not query:
            return ToolResult(ok=False, error="location is required")
        try:
            location = await self._geocode(query)
            days = 1 if action == "current" else self._forecast_days(action, arguments.get("days"))
            data = await self._forecast(location, days)
            if action == "current":
                return ToolResult(data=self._current_payload(location, data))
            payload = self._forecast_payload(location, data, days)
            return ToolResult(data=self._rain_payload(payload) if action == "rain_probability" else payload)
        except LookupError as exc:
            return ToolResult(ok=False, error=str(exc))
        except httpx.HTTPStatusError as exc:
            return ToolResult(ok=False, error=f"Open-Meteo request failed: HTTP {exc.response.status_code}")
        except httpx.HTTPError as exc:
            return ToolResult(ok=False, error=f"Open-Meteo connection failed: {exc}")
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            return ToolResult(ok=False, error=f"Unexpected Open-Meteo response: {exc}")

    async def _geocode(self, query: str) -> dict:
        data = await self._request(
            self.settings.open_meteo_geocoding_url,
            {"name": query, "count": 1, "language": "en", "format": "json"},
        )
        results = data.get("results") or []
        if not results:
            raise LookupError(f"No weather location found for {query!r}.")
        return results[0]

    async def _forecast(self, location: dict, days: int) -> dict:
        return await self._request(
            self.settings.open_meteo_forecast_url,
            {
                "latitude": location["latitude"], "longitude": location["longitude"],
                "timezone": "auto", "forecast_days": days,
                "current": "temperature_2m,apparent_temperature,relative_humidity_2m,precipitation,weather_code,wind_speed_10m,wind_direction_10m",
                "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max,wind_speed_10m_max,uv_index_max",
                "hourly": "temperature_2m,relative_humidity_2m,precipitation_probability,weather_code,wind_speed_10m",
            },
        )

    @staticmethod
    async def _request(url: str, params: dict) -> dict:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            return response.json()

    @staticmethod
    def _forecast_days(action: str, requested_days: int | None) -> int:
        if action in {"today_forecast", "rain_probability"}:
            return 1
        if action == "seven_day_forecast":
            return 7
        return max(1, min(int(requested_days or 3), 7))

    @classmethod
    def _current_payload(cls, location: dict, data: dict) -> dict:
        current = data["current"]
        return {
            "provider": "open-meteo.com", "type": "current",
            "location": cls._location_payload(location, data),
            "condition": cls._condition(current.get("weather_code")),
            "temperature_c": current.get("temperature_2m"),
            "feels_like_c": current.get("apparent_temperature"),
            "humidity_percent": current.get("relative_humidity_2m"),
            "wind_kph": current.get("wind_speed_10m"),
            "wind_direction": cls._cardinal(current.get("wind_direction_10m")),
            "uv_index": (data.get("daily", {}).get("uv_index_max") or [None])[0],
            "precipitation_mm": current.get("precipitation"), "updated_at": current.get("time"),
        }

    @classmethod
    def _forecast_payload(cls, location: dict, data: dict, days: int) -> dict:
        daily, hourly = data["daily"], data["hourly"]
        output = []
        for index, date in enumerate(daily["time"][:days]):
            hour_indexes = [i for i, value in enumerate(hourly["time"]) if value.startswith(f"{date}T")]
            temperatures = [hourly["temperature_2m"][i] for i in hour_indexes]
            humidity = [hourly["relative_humidity_2m"][i] for i in hour_indexes]
            output.append({
                "date": date, "condition": cls._condition(daily["weather_code"][index]),
                "temperature_c": {
                    "average": round(sum(temperatures) / len(temperatures), 1) if temperatures else None,
                    "maximum": daily["temperature_2m_max"][index], "minimum": daily["temperature_2m_min"][index],
                },
                "humidity_percent": round(sum(humidity) / len(humidity)) if humidity else None,
                "wind_kph": daily["wind_speed_10m_max"][index], "uv_index": daily["uv_index_max"][index],
                "rain_probability_percent": daily["precipitation_probability_max"][index],
                "precipitation_mm": daily["precipitation_sum"][index],
                "hourly": [{
                    "time": hourly["time"][i], "condition": cls._condition(hourly["weather_code"][i]),
                    "temperature_c": hourly["temperature_2m"][i],
                    "humidity_percent": hourly["relative_humidity_2m"][i],
                    "wind_kph": hourly["wind_speed_10m"][i],
                    "rain_probability_percent": hourly["precipitation_probability"][i],
                } for i in hour_indexes],
            })
        return {"provider": "open-meteo.com", "type": "forecast", "location": cls._location_payload(location, data), "days": output}

    @staticmethod
    def _rain_payload(payload: dict) -> dict:
        return {
            "provider": payload["provider"], "type": "rain_probability", "location": payload["location"],
            "days": [{
                "date": day["date"], "condition": day["condition"],
                "rain_probability_percent": day["rain_probability_percent"],
                "precipitation_mm": day["precipitation_mm"],
                "hourly": [{"time": hour["time"], "rain_probability_percent": hour["rain_probability_percent"], "condition": hour["condition"]} for hour in day["hourly"]],
            } for day in payload["days"]],
        }

    @staticmethod
    def _location_payload(location: dict, data: dict) -> dict:
        return {
            "name": location.get("name"), "region": location.get("admin1"), "country": location.get("country"),
            "timezone": data.get("timezone") or location.get("timezone"),
            "latitude": location.get("latitude"), "longitude": location.get("longitude"),
        }

    @staticmethod
    def _condition(code: int | None) -> str:
        return WMO_CONDITIONS.get(code, f"Weather code {code}" if code is not None else "Unknown")

    @staticmethod
    def _cardinal(degrees: float | None) -> str | None:
        if degrees is None:
            return None
        return ("N", "NE", "E", "SE", "S", "SW", "W", "NW")[round(degrees / 45) % 8]
