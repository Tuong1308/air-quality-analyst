import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy import text

load_dotenv()

DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")

DB_URL = f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"


def get_engine():
    return create_engine(DB_URL)

def load_hourly_upsert(df, engine) -> None:
    columns = [
        "city_id", "datetime_utc", "datetime_local", "local_date", "local_hour",
        "pm2_5", "pm10", "nitrogen_dioxide", "ozone",
        "sulphur_dioxide", "carbon_monoxide", "uv_index",
    ]

    insert_sql = text(f"""
        INSERT INTO fact_hourly_air_quality ({", ".join(columns)})
        VALUES ({", ".join(f":{c}" for c in columns)})
        ON CONFLICT (city_id, datetime_utc) DO UPDATE SET
            datetime_local = EXCLUDED.datetime_local,
            local_date = EXCLUDED.local_date,
            local_hour = EXCLUDED.local_hour,
            pm2_5 = EXCLUDED.pm2_5,
            pm10 = EXCLUDED.pm10,
            nitrogen_dioxide = EXCLUDED.nitrogen_dioxide,
            ozone = EXCLUDED.ozone,
            sulphur_dioxide = EXCLUDED.sulphur_dioxide,
            carbon_monoxide = EXCLUDED.carbon_monoxide,
            uv_index = EXCLUDED.uv_index
    """)

    records = df[columns].to_dict(orient="records")

    with engine.begin() as conn:
        conn.execute(insert_sql, records)

    print(f"Upserted {len(records)} rows.")


if __name__ == "__main__":
    from src.transform import transform_air_quality

    engine = get_engine()
    df = transform_air_quality("hanoi", "2026-06-01")
    load_hourly_naive(df, engine)