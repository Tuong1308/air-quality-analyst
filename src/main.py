import argparse
import sys
from datetime import date, timedelta

from src.config import CITIES
from src.extract import extract_one_city_one_day
from src.transform import transform_air_quality, transform_weather
from src.load import get_engine, load_hourly_upsert
from src.aggregate import aggregate_daily_air_quality, load_daily_weather
from src.logger import log



def run_one_day(target_date: str, engine=None) -> int:
    own_engine = engine is None
    if own_engine:
        engine = get_engine()

    failed_cities = []

    for city_id in CITIES:
        try:
            log.info(f"[{city_id}] extracting...")
            extract_one_city_one_day(city_id, target_date)

            log.info(f"[{city_id}] transforming...")
            df_air = transform_air_quality(city_id, target_date)
            df_weather = transform_weather(city_id, target_date)
            load_daily_weather(df_weather, engine)

            log.info(f"[{city_id}] loading...")
            load_hourly_upsert(df_air, engine)

        except Exception as e:
            # Cô lập lỗi: 1 thành phố hỏng không làm sập 5 thành phố còn lại
            log.error(f"[{city_id}] {type(e).__name__}: {e}")
            failed_cities.append(city_id)

    if failed_cities:
        log.error(f"Done with errors: {target_date} — failed: {', '.join(failed_cities)}")
        return 1
    
    # Batch UTC ngày X đóng góp dữ liệu cho local_date X (17 giờ)
    # và local_date X+1 (7 giờ) do lệch +7h — phải aggregate lại cả hai.
    log.info("Aggregating daily layer...")
    next_date = (date.fromisoformat(target_date) + timedelta(days=1)).isoformat()
    aggregate_daily_air_quality(engine, target_date)
    aggregate_daily_air_quality(engine, next_date)

    log.info(f"Done: {target_date}")
    return 0


def date_range(start: str, end: str):
    start_d = date.fromisoformat(start)
    end_d = date.fromisoformat(end)
    current = start_d
    while current <= end_d:
        yield current.isoformat()
        current += timedelta(days=1)


def run_date_range(start: str, end: str) -> int:
    engine = get_engine()
    exit_code = 0
    for d in date_range(start, end):
        log.info(f"=== Running {d} ===")
        if run_one_day(d, engine=engine) != 0:
            exit_code = 1
    return exit_code


def main():
    parser = argparse.ArgumentParser(description="Air Quality ETL pipeline")
    parser.add_argument("--date", help="Chạy 1 ngày, dạng YYYY-MM-DD")
    parser.add_argument("--start-date", help="Ngày bắt đầu (dùng kèm --end-date)")
    parser.add_argument("--end-date", help="Ngày kết thúc (dùng kèm --start-date)")
    args = parser.parse_args()

    if args.date:
        exit_code = run_one_day(args.date)
    elif args.start_date and args.end_date:
        exit_code = run_date_range(args.start_date, args.end_date)
    else:
        parser.error("Cần truyền --date HOẶC cả --start-date và --end-date")

    sys.exit(exit_code)
if __name__ == "__main__":
    main()
    