import os
from dotenv import load_dotenv
from sqlalchemy import create_engine

load_dotenv()

DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")

DB_URL = f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"


def get_engine():
    return create_engine(DB_URL)


def load_hourly_naive(df, engine) -> None:
    df.to_sql(
        "fact_hourly_air_quality",
        con=engine,
        if_exists="append",
        index=False,
    )
    print(f"Loaded {len(df)} rows.")


if __name__ == "__main__":
    from src.transform import transform_air_quality

    engine = get_engine()
    df = transform_air_quality("hanoi", "2026-06-01")
    load_hourly_naive(df, engine)