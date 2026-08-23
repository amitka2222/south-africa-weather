"""Fetch a South African weather snapshot from Open-Meteo and write data/weather.json.

The website reads this file for an instant first paint and as a fallback when the
live API is unreachable; the browser then refreshes straight from Open-Meteo.
Because only a small JSON file is committed (never the rendered HTML), the
automated commits stay small and reviewable.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import time
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).resolve().parent
CITIES_FILE = ROOT / "data" / "cities.json"
OUTPUT_FILE = ROOT / "data" / "weather.json"

API_URL = "https://api.open-meteo.com/v1/forecast"
TIMEZONE = "Africa/Johannesburg"
FORECAST_DAYS = 7
FORECAST_HOURS = 24

CURRENT_FIELDS = (
    "temperature_2m",
    "relative_humidity_2m",
    "apparent_temperature",
    "is_day",
    "precipitation",
    "weather_code",
    "cloud_cover",
    "pressure_msl",
    "wind_speed_10m",
    "wind_direction_10m",
    "wind_gusts_10m",
)
HOURLY_FIELDS = ("temperature_2m", "precipitation_probability", "weather_code")
DAILY_FIELDS = (
    "weather_code",
    "temperature_2m_max",
    "temperature_2m_min",
    "sunrise",
    "sunset",
    "uv_index_max",
    "precipitation_sum",
    "precipitation_probability_max",
    "wind_speed_10m_max",
)

MAX_ATTEMPTS = 3
RETRY_BACKOFF_SECONDS = 5


def load_cities() -> list[dict[str, Any]]:
    with CITIES_FILE.open(encoding="utf-8") as handle:
        cities = json.load(handle)["cities"]
    if not cities:
        raise ValueError(f"{CITIES_FILE} contains no cities")
    return cities


def request_forecast(cities: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Query every station in a single multi-coordinate request, with retries."""
    params = {
        "latitude": ",".join(str(c["lat"]) for c in cities),
        "longitude": ",".join(str(c["lon"]) for c in cities),
        "current": ",".join(CURRENT_FIELDS),
        "hourly": ",".join(HOURLY_FIELDS),
        "daily": ",".join(DAILY_FIELDS),
        "timezone": TIMEZONE,
        "forecast_days": FORECAST_DAYS,
        "forecast_hours": FORECAST_HOURS,
    }

    last_error: Exception | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response = requests.get(API_URL, params=params, timeout=30)
            response.raise_for_status()
            payload = response.json()
            break
        except (requests.RequestException, ValueError) as error:
            last_error = error
            if attempt == MAX_ATTEMPTS:
                raise RuntimeError(
                    f"Open-Meteo request failed after {MAX_ATTEMPTS} attempts: {error}"
                ) from error
            wait = RETRY_BACKOFF_SECONDS * attempt
            print(f"  attempt {attempt} failed ({error}); retrying in {wait}s", file=sys.stderr)
            time.sleep(wait)
    else:  # pragma: no cover - defensive
        raise RuntimeError(f"Open-Meteo request failed: {last_error}")

    # A single coordinate returns an object; multiple coordinates return a list.
    if isinstance(payload, dict):
        payload = [payload]
    if len(payload) != len(cities):
        raise ValueError(
            f"Open-Meteo returned {len(payload)} locations for {len(cities)} cities"
        )
    return payload


def build_station(city: dict[str, Any], block: dict[str, Any]) -> dict[str, Any]:
    current = block.get("current", {})
    hourly = block.get("hourly", {})
    daily = block.get("daily", {})

    days = [
        {
            "date": daily["time"][i],
            "code": daily["weather_code"][i],
            "tmax": daily["temperature_2m_max"][i],
            "tmin": daily["temperature_2m_min"][i],
            "sunrise": daily["sunrise"][i],
            "sunset": daily["sunset"][i],
            "uvMax": daily["uv_index_max"][i],
            "precipSum": daily["precipitation_sum"][i],
            "precipProb": daily["precipitation_probability_max"][i],
            "windMax": daily["wind_speed_10m_max"][i],
        }
        for i in range(len(daily.get("time", [])))
    ]

    hours = [
        {
            "time": hourly["time"][i],
            "temp": hourly["temperature_2m"][i],
            "precipProb": hourly["precipitation_probability"][i],
            "code": hourly["weather_code"][i],
        }
        for i in range(len(hourly.get("time", [])))
    ]

    return {
        "id": city["id"],
        "name": city["name"],
        "province": city["province"],
        "tag": city["tag"],
        "lat": city["lat"],
        "lon": city["lon"],
        "elevation": block.get("elevation"),
        "current": {
            "time": current.get("time"),
            "temp": current.get("temperature_2m"),
            "feels": current.get("apparent_temperature"),
            "humidity": current.get("relative_humidity_2m"),
            "isDay": bool(current.get("is_day", 1)),
            "precip": current.get("precipitation"),
            "code": current.get("weather_code"),
            "cloud": current.get("cloud_cover"),
            "pressure": current.get("pressure_msl"),
            "wind": current.get("wind_speed_10m"),
            "gust": current.get("wind_gusts_10m"),
            "windDir": current.get("wind_direction_10m"),
        },
        "today": days[0] if days else None,
        "daily": days,
        "hourly": hours,
    }


def build_snapshot(cities: list[dict[str, Any]], payload: list[dict[str, Any]]) -> dict[str, Any]:
    stations = [build_station(city, block) for city, block in zip(cities, payload)]
    return {
        "generated": dt.datetime.now(dt.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
        "source": "snapshot",
        "attribution": "Open-Meteo (https://open-meteo.com/)",
        "timezone": TIMEZONE,
        "stations": stations,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="fetch and print a summary without writing data/weather.json",
    )
    args = parser.parse_args()

    cities = load_cities()
    print(f"Fetching Open-Meteo data for {len(cities)} South African stations...")

    try:
        snapshot = build_snapshot(cities, request_forecast(cities))
    except Exception as error:  # noqa: BLE001 - surface any failure to the workflow
        print(f"Error building weather snapshot: {error}", file=sys.stderr)
        return 1

    for station in snapshot["stations"]:
        now = station["current"]
        today = station["today"] or {}
        print(
            f"  {station['name']:<14} {station['province']:<15} "
            f"{now['temp']:>5}°C  feels {now['feels']:>5}°C  "
            f"wind {now['wind']:>5} km/h  "
            f"high {today.get('tmax')}°C / low {today.get('tmin')}°C"
        )

    if args.dry_run:
        print("Dry run: data/weather.json left unchanged.")
        return 0

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_FILE.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(snapshot, handle, indent=1, ensure_ascii=False, sort_keys=False)
        handle.write("\n")

    size_kb = OUTPUT_FILE.stat().st_size / 1024
    print(f"Wrote {OUTPUT_FILE.relative_to(ROOT)} ({size_kb:.1f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
