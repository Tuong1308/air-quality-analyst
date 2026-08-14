import json
import requests
from requests.exceptions import ConnectionError, Timeout, HTTPError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from src.logger import log

from datetime import date as date_type

from src.config import (
    AIR_QUALITY_API_URL,
    WEATHER_API_URL,
    AIR_QUALITY_HOURLY_VARS,
    WEATHER_DAILY_VARS,
    CITIES,
    RAW_DATA_DIR,
    TIMEZONE,
)

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((ConnectionError, Timeout)),
    reraise=True,
)

def fetch_air_quality(city_id: str, target_date: str) -> dict:
    city = CITIES[city_id]
    params = {
        "latitude": city["lat"],
        "longitude": city["lon"],
        "hourly": ",".join(AIR_QUALITY_HOURLY_VARS),
        "start_date": target_date,
        "end_date": target_date,
    }
    response = requests.get(AIR_QUALITY_API_URL, params=params, timeout=30)
    response.raise_for_status()
    return response.json()


def fetch_weather(city_id: str, target_date: str) -> dict:
    city = CITIES[city_id]
    params = {
        "latitude": city["lat"],
        "longitude": city["lon"],
        "daily": ",".join(WEATHER_DAILY_VARS),
        "start_date": target_date,
        "end_date": target_date,
        "timezone": TIMEZONE,
    }
    response = requests.get(WEATHER_API_URL, params=params, timeout=30)
    response.raise_for_status()
    return response.json()


def save_raw(data: dict, city_id: str, target_date: str, source: str) -> None:
    day_dir = RAW_DATA_DIR / target_date
    day_dir.mkdir(parents=True, exist_ok=True)
    file_path = day_dir / f"{city_id}_{source}.json"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    log.info(f"Saved: {file_path}")


def extract_one_city_one_day(city_id: str, target_date: str) -> None:
    air_quality_data = fetch_air_quality(city_id, target_date)
    save_raw(air_quality_data, city_id, target_date, "air_quality")

    weather_data = fetch_weather(city_id, target_date)
    save_raw(weather_data, city_id, target_date, "weather")


def extract_all_cities_one_day(target_date: str) -> None:
    for city_id in CITIES:
        print(f"Extracting {city_id} for {target_date}...")
        extract_one_city_one_day(city_id, target_date)


if __name__ == "__main__":
    test_date = "2026-06-01"
    extract_all_cities_one_day(test_date)