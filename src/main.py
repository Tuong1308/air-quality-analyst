import argparse
from datetime import date, timedelta

from src.config import CITIES
from src.extract import extract_one_city_one_day
from src.transform import transform_air_quality, transform_weather
from src.load import get_engine, load_hourly_upsert


def run_one_day(target_date: str, engine=None) -> None:
    own_engine = engine is None
    if own_engine:
        engine = get_engine()

    for city_id in CITIES:
        print(f"[{city_id}] extracting...")
        extract_one_city_one_day(city_id, target_date)

        print(f"[{city_id}] transforming...")
        df_air = transform_air_quality(city_id, target_date)
        df_weather = transform_weather(city_id, target_date)  # noqa: F841 — load ở Buổi 11

        print(f"[{city_id}] loading...")
        load_hourly_upsert(df_air, engine)

    print(f"Done: {target_date}")


def date_range(start: str, end: str):
    start_d = date.fromisoformat(start)
    end_d = date.fromisoformat(end)
    current = start_d
    while current <= end_d:
        yield current.isoformat()
        current += timedelta(days=1)


def run_date_range(start: str, end: str) -> None:
    engine = get_engine()
    for d in date_range(start, end):
        print(f"=== Running {d} ===")
        run_one_day(d, engine=engine)


def main():
    parser = argparse.ArgumentParser(description="Air Quality ETL pipeline")
    parser.add_argument("--date", help="Chạy 1 ngày, dạng YYYY-MM-DD")
    parser.add_argument("--start-date", help="Ngày bắt đầu (dùng kèm --end-date)")
    parser.add_argument("--end-date", help="Ngày kết thúc (dùng kèm --start-date)")
    args = parser.parse_args()

    if args.date:
        run_one_day(args.date)
    elif args.start_date and args.end_date:
        run_date_range(args.start_date, args.end_date)
    else:
        parser.error("Cần truyền --date HOẶC cả --start-date và --end-date")


if __name__ == "__main__":
    main()