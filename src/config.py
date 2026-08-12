import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DATA_DIR = BASE_DIR / "data" / "raw"
LOGS_DIR = BASE_DIR / "logs"

AIR_QUALITY_API_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
WEATHER_API_URL = "https://archive-api.open-meteo.com/v1/archive"

# Đã loại "dust" — model bụi khoáng không phủ khu vực Đông Nam Á
# (kiểm chứng bằng Dubai, xem tien-do-du-an.md phần "Vấn đề / quyết định phát sinh")
AIR_QUALITY_HOURLY_VARS = [
    "pm2_5",
    "pm10",
    "nitrogen_dioxide",
    "ozone",
    "sulphur_dioxide",
    "carbon_monoxide",
    "uv_index",
]

WEATHER_DAILY_VARS = [
    "precipitation_sum",
    "windspeed_10m_max",
    "temperature_2m_max",
    "temperature_2m_min",
]

CITIES = {
    "hanoi":    {"name": "Hà Nội",           "lat": 21.0285, "lon": 105.8542, "region": "Bắc"},
    "haiphong": {"name": "Hải Phòng",         "lat": 20.8449, "lon": 106.6881, "region": "Bắc"},
    "danang":   {"name": "Đà Nẵng",           "lat": 16.0544, "lon": 108.2022, "region": "Trung"},
    "hcmc":     {"name": "TP. Hồ Chí Minh",   "lat": 10.8231, "lon": 106.6297, "region": "Nam"},
    "cantho":   {"name": "Cần Thơ",           "lat": 10.0452, "lon": 105.7469, "region": "Nam"},
    "dalat":    {"name": "Đà Lạt",            "lat": 11.9404, "lon": 108.4583, "region": "Trung"},
}

TIMEZONE = "Asia/Ho_Chi_Minh"
WHO_PM25_THRESHOLD = 15  # µg/m³
