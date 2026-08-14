import pandas as pd
from sqlalchemy import text
from src.logger import log

from src.config import WHO_PM25_THRESHOLD


def classify_aqi(pm25: float) -> str:
    if pm25 is None or pd.isna(pm25):
        return None
    if pm25 <= 12:
        return "Tốt"
    if pm25 <= 35.4:
        return "Trung bình"
    if pm25 <= 55.4:
        return "Kém"
    if pm25 <= 150.4:
        return "Xấu"
    return "Rất xấu"


def aggregate_daily_air_quality(engine, target_date: str) -> int:
    # Tổng hợp từ tầng hourly (Silver) lên tầng daily (Gold).
    # Đọc thẳng từ DB thay vì từ DataFrame — vì 1 local_date có thể gồm
    # dữ liệu từ 2 ngày UTC khác nhau (do lệch +7h).
    sql = text("""
        SELECT
            city_id,
            local_date,
            AVG(pm2_5) AS pm2_5_avg,
            MAX(pm2_5) AS pm2_5_max,
            AVG(pm10)  AS pm10_avg,
            COUNT(*)   AS hours_recorded
        FROM fact_hourly_air_quality
        WHERE local_date = :target_date
        GROUP BY city_id, local_date
    """)

    peak_sql = text("""
        SELECT DISTINCT ON (city_id)
            city_id, local_hour AS pm2_5_peak_hour
        FROM fact_hourly_air_quality
        WHERE local_date = :target_date AND pm2_5 IS NOT NULL
        ORDER BY city_id, pm2_5 DESC
    """)

    with engine.begin() as conn:
        df = pd.read_sql(sql, conn, params={"target_date": target_date})
        df_peak = pd.read_sql(peak_sql, conn, params={"target_date": target_date})

    if df.empty:
        print(f"  Không có dữ liệu hourly cho {target_date}")
        return 0

    df = df.merge(df_peak, on="city_id", how="left")
    df["exceeds_who"] = df["pm2_5_avg"] > WHO_PM25_THRESHOLD
    df["aqi_category"] = df["pm2_5_avg"].apply(classify_aqi)

    columns = [
        "city_id", "local_date", "pm2_5_avg", "pm2_5_max", "pm2_5_peak_hour",
        "pm10_avg", "hours_recorded", "exceeds_who", "aqi_category",
    ]

    upsert_sql = text(f"""
        INSERT INTO fact_daily_air_quality ({", ".join(columns)})
        VALUES ({", ".join(f":{c}" for c in columns)})
        ON CONFLICT (city_id, local_date) DO UPDATE SET
            pm2_5_avg = EXCLUDED.pm2_5_avg,
            pm2_5_max = EXCLUDED.pm2_5_max,
            pm2_5_peak_hour = EXCLUDED.pm2_5_peak_hour,
            pm10_avg = EXCLUDED.pm10_avg,
            hours_recorded = EXCLUDED.hours_recorded,
            exceeds_who = EXCLUDED.exceeds_who,
            aqi_category = EXCLUDED.aqi_category
    """)

    records = df[columns].to_dict(orient="records")
    with engine.begin() as conn:
        conn.execute(upsert_sql, records)

    log.info(f"  Aggregated {len(records)} daily rows for {target_date}")
    return len(records)


def load_daily_weather(df, engine) -> None:
    columns = [
        "city_id", "weather_date", "precipitation_sum",
        "windspeed_10m_max", "temperature_2m_max", "temperature_2m_min",
    ]

    upsert_sql = text(f"""
        INSERT INTO fact_daily_weather ({", ".join(columns)})
        VALUES ({", ".join(f":{c}" for c in columns)})
        ON CONFLICT (city_id, weather_date) DO UPDATE SET
            precipitation_sum = EXCLUDED.precipitation_sum,
            windspeed_10m_max = EXCLUDED.windspeed_10m_max,
            temperature_2m_max = EXCLUDED.temperature_2m_max,
            temperature_2m_min = EXCLUDED.temperature_2m_min
    """)

    records = df[columns].to_dict(orient="records")
    with engine.begin() as conn:
        conn.execute(upsert_sql, records)