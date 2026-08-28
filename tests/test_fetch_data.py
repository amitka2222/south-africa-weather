import json
from pathlib import Path
import sys
from unittest.mock import MagicMock, patch
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fetch_data import (
    build_snapshot,
    build_station,
    load_cities,
    main,
    request_forecast,
)


@pytest.fixture
def mock_city():
    return {
        "id": "jnb",
        "name": "Johannesburg",
        "province": "Gauteng",
        "tag": "Highveld / Economic hub",
        "lat": -26.2041,
        "lon": 28.0473,
    }


@pytest.fixture
def mock_meteo_block():
    return {
        "elevation": 1753.0,
        "current": {
            "time": "2026-08-28T12:00",
            "temperature_2m": 22.5,
            "apparent_temperature": 21.0,
            "relative_humidity_2m": 45,
            "is_day": 1,
            "precipitation": 0.0,
            "weather_code": 1,
            "cloud_cover": 10,
            "pressure_msl": 1018.5,
            "wind_speed_10m": 12.0,
            "wind_gusts_10m": 18.0,
            "wind_direction_10m": 90,
        },
        "daily": {
            "time": ["2026-08-28", "2026-08-29"],
            "weather_code": [1, 2],
            "temperature_2m_max": [24.0, 25.0],
            "temperature_2m_min": [10.0, 11.0],
            "sunrise": ["2026-08-28T06:30", "2026-08-29T06:29"],
            "sunset": ["2026-08-28T17:50", "2026-08-29T17:51"],
            "uv_index_max": [6.5, 7.0],
            "precipitation_sum": [0.0, 0.5],
            "precipitation_probability_max": [10, 20],
            "wind_speed_10m_max": [15.0, 16.0],
        },
        "hourly": {
            "time": ["2026-08-28T12:00", "2026-08-28T13:00"],
            "temperature_2m": [22.5, 23.0],
            "precipitation_probability": [5, 10],
            "weather_code": [1, 1],
        },
    }


def test_load_cities():
    cities = load_cities()
    assert isinstance(cities, list)
    assert len(cities) >= 12
    assert any(c["id"] == "jnb" for c in cities)


def test_build_station(mock_city, mock_meteo_block):
    station = build_station(mock_city, mock_meteo_block)
    assert station["id"] == "jnb"
    assert station["name"] == "Johannesburg"
    assert station["province"] == "Gauteng"
    assert station["elevation"] == 1753.0
    assert station["current"]["temp"] == 22.5
    assert station["current"]["isDay"] is True
    assert station["today"]["tmax"] == 24.0
    assert len(station["daily"]) == 2
    assert len(station["hourly"]) == 2


def test_build_snapshot(mock_city, mock_meteo_block):
    snapshot = build_snapshot([mock_city], [mock_meteo_block])
    assert snapshot["source"] == "snapshot"
    assert snapshot["timezone"] == "Africa/Johannesburg"
    assert "generated" in snapshot
    assert len(snapshot["stations"]) == 1
    assert snapshot["stations"][0]["id"] == "jnb"


@patch("requests.get")
def test_request_forecast_success(mock_get, mock_city, mock_meteo_block):
    mock_response = MagicMock()
    mock_response.json.return_value = [mock_meteo_block]
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    payload = request_forecast([mock_city])
    assert isinstance(payload, list)
    assert len(payload) == 1
    assert payload[0]["elevation"] == 1753.0


import requests

@patch("time.sleep", return_value=None)
@patch("requests.get")
def test_request_forecast_failure(mock_get, mock_sleep, mock_city):
    mock_get.side_effect = requests.RequestException("Network error")
    with pytest.raises(RuntimeError) as exc_info:
        request_forecast([mock_city])
    assert "Open-Meteo request failed" in str(exc_info.value)


@patch("fetch_data.request_forecast")
def test_main_dry_run(mock_req, mock_city, mock_meteo_block):
    mock_req.return_value = [mock_meteo_block] * 12
    with patch("sys.argv", ["fetch_data.py", "--dry-run"]):
        ret = main()
        assert ret == 0
