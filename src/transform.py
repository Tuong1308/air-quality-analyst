import json
from datetime import date as date_type
from zoneinfo import ZoneInfo
from src.logger import log

import pandas as pd

from src.config import RAW_DATA_DIR, TIMEZONE, WHO_PM25_THRESHOLD

UTC = ZoneInfo("UTC")
VN_TZ = ZoneInfo(TIMEZONE)


def load_raw_json(city_id: str, target_date: str, source: str) -> dict:
    file_path = RAW_DATA_DIR / target_date / f"{city_id}_{source}.json"
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def transform_air_quality(city_id: str, target_date: str) -> pd.DataFrame:
    raw = load_raw_json(city_id, target_date, "air_quality")
    hourly = raw["hourly"]

    df = pd.DataFrame(hourly)

    # Bước 1 — GẮN NHÃN: chuỗi "time" từ API vốn dĩ đã là UTC (đã xác nhận ở Buổi 1:
    # timezone trả về là "GMT", offset 0). Đây KHÔNG phải chuyển đổi, chỉ đánh dấu.
    df["datetime_utc"] = pd.to_datetime(df["time"]).dt.tz_localize(UTC)

    # Bước 2 — CHUYỂN ĐỔI: dịch thời điểm UTC đó sang giờ VN thật (+7 tiếng).
    # Khác thao tác với bước 1: giá trị số THẬT SỰ thay đổi ở đây.
    df["datetime_local_aware"] = df["datetime_utc"].dt.tz_convert(VN_TZ)

    # Lưu datetime_local dạng "naive" (bỏ tz-info) vì cột DB là TIMESTAMP,
    # không phải TIMESTAMPTZ — xem lý do ở sql/schema.sql (Buổi 3).
    df["datetime_local"] = df["datetime_local_aware"].dt.tz_localize(None)

    df["local_date"] = df["datetime_local"].dt.date
    df["local_hour"] = df["datetime_local"].dt.hour

    df["city_id"] = city_id

    keep_cols = [
        "city_id", "datetime_utc", "datetime_local", "local_date", "local_hour",
        "pm2_5", "pm10", "nitrogen_dioxide", "ozone",
        "sulphur_dioxide", "carbon_monoxide", "uv_index",
    ]
    keep_cols = [
        "city_id", "datetime_utc", "datetime_local", "local_date", "local_hour",
        "pm2_5", "pm10", "nitrogen_dioxide", "ozone",
        "sulphur_dioxide", "carbon_monoxide", "uv_index",
    ]
    return validate_air_quality(df[keep_cols])

def validate_air_quality(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["validation_flags"] = [[] for _ in range(len(df))]

    # Tầng 1 — Loại bỏ: thiếu khóa thì không lưu được
    missing_key = df["city_id"].isna() | df["datetime_utc"].isna()
    if missing_key.any():
        log.warning(f"  VALIDATION: loại {missing_key.sum()} dòng thiếu khóa")
        df = df[~missing_key].copy()

    # Tầng 2 — Đặt NULL: giá trị âm vô nghĩa vật lý, nhưng giữ các cột khác
    for col in ["pm2_5", "pm10", "nitrogen_dioxide", "ozone",
                "sulphur_dioxide", "carbon_monoxide"]:
        negative = df[col] < 0
        if negative.any():
            log.warning(f"  VALIDATION: {negative.sum()} giá trị âm ở {col} -> NULL")
            df.loc[negative, col] = None
            df.loc[negative, "validation_flags"].apply(lambda f: f.append(f"NEGATIVE_{col.upper()}"))

    # Tầng 3 — Cảnh báo, GIỮ LẠI: có thể là sự kiện thật (cháy rừng)
    extreme = df["pm2_5"] > 1000
    if extreme.any():
        log.warning(f"  VALIDATION WARNING: {extreme.sum()} dòng PM2.5 > 1000 (giữ lại)")
        df.loc[extreme, "validation_flags"].apply(lambda f: f.append("PM25_EXCEEDS_1000"))

    # Tầng 3 — Vi phạm định nghĩa vật lý: PM2.5 là tập con của PM10
    violation = df["pm2_5"] > df["pm10"]
    if violation.any():
        log.error(f"  VALIDATION ERROR: {violation.sum()} dòng PM2.5 > PM10 (giữ lại)")
        df.loc[violation, "validation_flags"].apply(lambda f: f.append("PM25_GT_PM10"))

    return df

def transform_weather(city_id: str, target_date: str) -> pd.DataFrame:
    raw = load_raw_json(city_id, target_date, "weather")
    daily = raw["daily"]

    df = pd.DataFrame(daily)
    df["weather_date"] = pd.to_datetime(df["time"]).dt.date
    df["city_id"] = city_id

    keep_cols = [
        "city_id", "weather_date",
        "precipitation_sum", "windspeed_10m_max",
        "temperature_2m_max", "temperature_2m_min",
    ]
    return df[keep_cols]


if __name__ == "__main__":
    test_date = "2026-06-01"
    df = transform_air_quality("hanoi", test_date)
    print(df[["datetime_utc", "datetime_local", "local_date", "local_hour", "pm2_5"]].head(10))
    print()
    print("Kiểm tra thủ công: dòng đầu tiên UTC 00:00 phải ứng với local 07:00 cùng ngày")