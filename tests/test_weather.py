import unittest
from unittest.mock import AsyncMock, patch

from app.config import Settings
from app.tools.weather import WeatherTool


LOCATION = {
    "name": "Abeokuta",
    "admin1": "Ogun State",
    "country": "Nigeria",
    "latitude": 7.15,
    "longitude": 3.35,
    "timezone": "Africa/Lagos",
}

FORECAST = {
    "timezone": "Africa/Lagos",
    "current": {
        "time": "2026-08-24T12:00",
        "temperature_2m": 29.0,
        "apparent_temperature": 33.0,
        "relative_humidity_2m": 74,
        "precipitation": 0.0,
        "weather_code": 2,
        "wind_speed_10m": 9.5,
        "wind_direction_10m": 225,
    },
    "daily": {
        "time": ["2026-08-24"],
        "weather_code": [61],
        "temperature_2m_max": [30.0],
        "temperature_2m_min": [23.0],
        "precipitation_sum": [4.2],
        "precipitation_probability_max": [70],
        "wind_speed_10m_max": [14.0],
        "uv_index_max": [7.0],
    },
    "hourly": {
        "time": ["2026-08-24T00:00", "2026-08-24T01:00"],
        "temperature_2m": [24.0, 24.5],
        "relative_humidity_2m": [90, 88],
        "precipitation_probability": [40, 50],
        "weather_code": [61, 63],
        "wind_speed_10m": [5.0, 6.0],
    },
}


class OpenMeteoWeatherTests(unittest.IsolatedAsyncioTestCase):
    async def test_current_weather_requires_no_api_key(self) -> None:
        tool = WeatherTool(Settings(_env_file=None))
        with (
            patch.object(tool, "_geocode", new=AsyncMock(return_value=LOCATION)),
            patch.object(tool, "_forecast", new=AsyncMock(return_value=FORECAST)),
        ):
            result = await tool.run({"action": "current", "location": "Abeokuta"})
        self.assertTrue(result.ok)
        self.assertEqual(result.data["provider"], "open-meteo.com")
        self.assertEqual(result.data["condition"], "Partly cloudy")
        self.assertEqual(result.data["wind_direction"], "SW")

    async def test_rain_probability_preserves_agent_contract(self) -> None:
        tool = WeatherTool(Settings(_env_file=None))
        with (
            patch.object(tool, "_geocode", new=AsyncMock(return_value=LOCATION)),
            patch.object(tool, "_forecast", new=AsyncMock(return_value=FORECAST)),
        ):
            result = await tool.run({"action": "rain_probability", "location": "Abeokuta"})
        self.assertTrue(result.ok)
        self.assertEqual(result.data["type"], "rain_probability")
        self.assertEqual(result.data["days"][0]["rain_probability_percent"], 70)

    async def test_unknown_location_is_friendly_error(self) -> None:
        tool = WeatherTool(Settings(_env_file=None))
        with patch.object(tool, "_geocode", new=AsyncMock(side_effect=LookupError("No location"))):
            result = await tool.run({"action": "current", "location": "Nowhere"})
        self.assertFalse(result.ok)
        self.assertEqual(result.error, "No location")


if __name__ == "__main__":
    unittest.main()
