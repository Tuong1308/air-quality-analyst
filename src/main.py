import argparse

from src.config import CITIES
from src.extract import extract_one_city_one_day
from src.transform import transform_air_quality, transform_weather
from src.load import get_engine, load_hourly_naive


def run_one_day(target_date: str) -> None:
    engine = get_engine()

    for city_id in CITIES:
        print(f"[{city_id}] extracting...")
        extract_one_city_one_day(city_id, target_date)

        print(f"[{city_id}] transforming...")
        df_air = transform_air_quality(city_id, target_date)
        df_weather = transform_weather(city_id, target_date)

        print(f"[{city_id}] loading...")
        load_hourly_naive(df_air, engine)

    print(f"Done: {target_date}")


def main():
    parser = argparse.ArgumentParser(description="Air Quality ETL pipeline")
    parser.add_argument("--date", required=True, help="Ngày cần chạy, dạng YYYY-MM-DD")
    args = parser.parse_args()

    run_one_day(args.date)


if __name__ == "__main__":
    main()