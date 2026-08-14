import json
from pathlib import Path

import pandas as pd
import pytest

from src.transform import validate_air_quality

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> dict:
    with open(FIXTURES / name, encoding="utf-8") as f:
        return json.load(f)


def build_df_from_fixture() -> pd.DataFrame:
    from zoneinfo import ZoneInfo

    raw = load_fixture("hanoi_air_quality.json")
    df = pd.DataFrame(raw["hourly"])
    df["datetime_utc"] = pd.to_datetime(df["time"]).dt.tz_localize(ZoneInfo("UTC"))
    df["datetime_local"] = (
        df["datetime_utc"].dt.tz_convert(ZoneInfo("Asia/Ho_Chi_Minh")).dt.tz_localize(None)
    )
    df["local_date"] = df["datetime_local"].dt.date
    df["local_hour"] = df["datetime_local"].dt.hour
    df["city_id"] = "hanoi"
    return df


class TestTimezone:
    def test_utc_midnight_becomes_local_7am(self):
        df = build_df_from_fixture()
        first = df.iloc[0]
        assert str(first["datetime_utc"]) == "2026-06-01 00:00:00+00:00"
        assert str(first["datetime_local"]) == "2026-06-01 07:00:00"
        assert first["local_hour"] == 7

    def test_utc_17h_rolls_over_to_next_local_day(self):
        # Điểm dễ bug nhất: UTC 17:00 + 7h = 00:00 ngày hôm sau
        df = build_df_from_fixture()
        row = df[df["datetime_utc"].dt.hour == 17].iloc[0]
        assert str(row["datetime_local"]) == "2026-06-02 00:00:00"
        assert row["local_hour"] == 0
        assert str(row["local_date"]) == "2026-06-02"

    def test_all_rows_shifted_exactly_7_hours(self):
        df = build_df_from_fixture()
        diff = df["datetime_local"] - df["datetime_utc"].dt.tz_localize(None)
        assert (diff == pd.Timedelta(hours=7)).all()

    def test_local_date_spans_two_days(self):
        # 24 giờ UTC luôn trải qua đúng 2 local_date do lệch +7h
        df = build_df_from_fixture()
        assert df["local_date"].nunique() == 2


class TestValidation:
    def _base_df(self) -> pd.DataFrame:
        return pd.DataFrame({
            "city_id": ["hanoi"] * 3,
            "datetime_utc": pd.to_datetime(
                ["2026-06-01 00:00", "2026-06-01 01:00", "2026-06-01 02:00"]
            ).tz_localize("UTC"),
            "pm2_5": [20.0, 30.0, 40.0],
            "pm10": [25.0, 35.0, 45.0],
            "nitrogen_dioxide": [10.0, 10.0, 10.0],
            "ozone": [50.0, 50.0, 50.0],
            "sulphur_dioxide": [5.0, 5.0, 5.0],
            "carbon_monoxide": [300.0, 300.0, 300.0],
        })

    def test_clean_data_has_no_flags(self):
        result = validate_air_quality(self._base_df())
        assert all(len(f) == 0 for f in result["validation_flags"])
        assert len(result) == 3

    def test_negative_value_becomes_null_row_kept(self):
        df = self._base_df()
        df.loc[1, "pm2_5"] = -5.0
        result = validate_air_quality(df)
        assert len(result) == 3, "Không được xóa dòng, chỉ đặt NULL"
        assert pd.isna(result.loc[1, "pm2_5"])
        assert result.loc[0, "pm2_5"] == 20.0, "Dòng khác không bị ảnh hưởng"

    def test_extreme_pm25_flagged_but_kept(self):
        df = self._base_df()
        df.loc[2, "pm2_5"] = 1500.0
        df.loc[2, "pm10"] = 1600.0
        result = validate_air_quality(df)
        assert len(result) == 3, "Giữ lại — có thể là cháy rừng thật"
        assert "PM25_EXCEEDS_1000" in result.loc[2, "validation_flags"]

    def test_pm25_greater_than_pm10_flagged_but_kept(self):
        df = self._base_df()
        df.loc[0, "pm2_5"] = 50.0
        df.loc[0, "pm10"] = 30.0
        result = validate_air_quality(df)
        assert len(result) == 3, "Giữ dòng, chỉ ghi ERROR"
        assert "PM25_GT_PM10" in result.loc[0, "validation_flags"]

    def test_missing_key_row_dropped(self):
        df = self._base_df()
        df.loc[1, "city_id"] = None
        result = validate_air_quality(df)
        assert len(result) == 2, "Thiếu khóa thì phải loại bỏ dòng"