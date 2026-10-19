import json
import urllib.error
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import SimpleTestCase
from rest_framework.test import APITestCase

from apps.farms.models import Farm

from . import client
from .alerts import build_alerts
from .client import WeatherUnavailable

URL = "/api/v1/weather/forecast/"

RAW = {
    "timezone": "Asia/Kolkata",
    "current": {"time": "2026-10-19T12:00", "temperature_2m": 31.2, "relative_humidity_2m": 55,
                "precipitation": 0.0, "weather_code": 2, "wind_speed_10m": 9.4},
    "daily": {
        "time": ["2026-10-19", "2026-10-20"],
        "temperature_2m_max": [34.1, 41.0],
        "temperature_2m_min": [22.0, 24.0],
        "precipitation_sum": [0.0, 62.5],
        "precipitation_probability_max": [10, 90],
        "weather_code": [1, 95],
        "wind_speed_10m_max": [12.0, 45.0],
    },
}


class ClientTests(SimpleTestCase):
    def test_normalizes_a_response(self):
        out = client.normalize(RAW)
        self.assertEqual(out["current"]["condition"], "cloudy")
        self.assertEqual(out["daily"][1]["condition"], "thunderstorm")
        self.assertEqual(len(out["daily"]), 2)

    def test_null_values_become_none(self):
        raw = json.loads(json.dumps(RAW))
        raw["daily"]["temperature_2m_max"][0] = None
        self.assertIsNone(client.normalize(raw)["daily"][0]["temp_max_c"])

    def test_unexpected_shapes_are_rejected(self):
        with self.assertRaises(WeatherUnavailable):
            client.normalize({})
        broken = json.loads(json.dumps(RAW))
        broken["daily"]["precipitation_sum"] = [1.0]
        with self.assertRaises(WeatherUnavailable):
            client.normalize(broken)

    def test_network_errors_are_mapped(self):
        for error in (urllib.error.URLError("down"), TimeoutError()):
            with patch("apps.weather.client.urllib.request.urlopen", side_effect=error):
                with self.assertRaises(WeatherUnavailable):
                    client.fetch_forecast(26.85, 80.95)

    def test_bad_json_is_mapped(self):
        resp = MagicMock()
        resp.read.return_value = b"<html>not json</html>"
        resp.__enter__.return_value = resp
        with patch("apps.weather.client.urllib.request.urlopen", return_value=resp):
            with self.assertRaises(WeatherUnavailable):
                client.fetch_forecast(26.85, 80.95)

    def test_fetch_parses_a_good_response(self):
        resp = MagicMock()
        resp.read.return_value = json.dumps(RAW).encode()
        resp.__enter__.return_value = resp
        with patch("apps.weather.client.urllib.request.urlopen", return_value=resp):
            self.assertEqual(client.fetch_forecast(26.85, 80.95)["current"]["temperature_c"], 31.2)


class AlertTests(SimpleTestCase):
    def test_only_the_extreme_day_is_flagged(self):
        alerts = build_alerts(client.normalize(RAW)["daily"])
        self.assertEqual({a["type"] for a in alerts}, {"heavy_rain", "heat", "strong_wind"})
        self.assertEqual({a["date"] for a in alerts}, {"2026-10-20"})

    def test_missing_values_raise_no_alert(self):
        self.assertEqual(build_alerts([{"date": "2026-10-19", "rain_mm": None, "temp_max_c": None,
                                        "temp_min_c": None, "wind_max_kmh": None}]), [])


class ApiTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.alice = User.objects.create_user("alice", password="StrongPass#2026")
        self.bob = User.objects.create_user("bob", password="StrongPass#2026")
        self.client.force_authenticate(user=self.alice)
        self.normalized = client.normalize(RAW)

    def get(self, params):
        with patch("apps.weather.views.fetch_forecast", return_value=self.normalized) as mocked:
            return self.client.get(URL, params), mocked

    def test_requires_authentication(self):
        self.client.force_authenticate(user=None)
        self.assertEqual(self.get({"lat": 26.85, "lon": 80.95})[0].status_code, 401)

    def test_bad_queries_are_rejected(self):
        for params in ({}, {"lat": 26.85}, {"lat": 95, "lon": 80}, {"lat": "nan", "lon": 80},
                       {"farm_id": 1, "lat": 26.85, "lon": 80.95}):
            self.assertEqual(self.get(params)[0].status_code, 400, params)

    def test_coordinates_are_rounded_before_leaving_our_server(self):
        res, mocked = self.get({"lat": 26.8567, "lon": 80.9512})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(mocked.call_args.args, (26.86, 80.95))
        self.assertEqual(res.data["location"]["latitude"], 26.86)
        self.assertEqual(res.data["source"]["name"], "Open-Meteo.com")
        self.assertTrue(res.data["notes"]["alerts_are_general_guidance"])
        self.assertEqual(len(res.data["alerts"]), 3)

    def test_farm_with_coordinates(self):
        farm = Farm.objects.create(owner=self.alice, name="A", state="UP", district="X",
                                   latitude="26.846700", longitude="80.946200")
        res, _ = self.get({"farm_id": farm.id})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["location"]["farm_id"], farm.id)

    def test_farm_without_coordinates_is_rejected(self):
        farm = Farm.objects.create(owner=self.alice, name="A", state="UP", district="X")
        self.assertEqual(self.get({"farm_id": farm.id})[0].status_code, 400)

    def test_other_users_farm_is_rejected(self):
        farm = Farm.objects.create(owner=self.bob, name="B", state="UP", district="X",
                                   latitude="26.8", longitude="80.9")
        self.assertEqual(self.get({"farm_id": farm.id})[0].status_code, 400)

    def test_second_request_is_served_from_the_cache(self):
        with patch("apps.weather.views.fetch_forecast", return_value=self.normalized) as mocked:
            first = self.client.get(URL, {"lat": 26.85, "lon": 80.95})
            second = self.client.get(URL, {"lat": 26.85, "lon": 80.95})
        self.assertEqual(mocked.call_count, 1)
        self.assertFalse(first.data["from_cache"])
        self.assertTrue(second.data["from_cache"])

    def test_upstream_failure_returns_502(self):
        with patch("apps.weather.views.fetch_forecast", side_effect=WeatherUnavailable("down")):
            res = self.client.get(URL, {"lat": 26.85, "lon": 80.95})
        self.assertEqual(res.status_code, 502)
        self.assertEqual(res.data["error"]["code"], "weather_unavailable")