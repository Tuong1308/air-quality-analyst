-- ============================================
-- Vietnam Air Quality ETL Pipeline — Schema
-- ============================================

SET client_encoding = 'UTF8';

-- Bảng dimension: 6 thành phố
CREATE TABLE IF NOT EXISTS dim_city (
    city_id    VARCHAR(20) PRIMARY KEY,
    name       VARCHAR(100) NOT NULL,
    latitude   NUMERIC(9,6) NOT NULL,
    longitude  NUMERIC(9,6) NOT NULL,
    region     VARCHAR(20) NOT NULL CHECK (region IN ('Bắc', 'Trung', 'Nam'))
);

-- Bảng fact theo giờ (Silver layer)
CREATE TABLE IF NOT EXISTS fact_hourly_air_quality (
    city_id         VARCHAR(20) NOT NULL REFERENCES dim_city(city_id),
    datetime_utc    TIMESTAMPTZ NOT NULL,
    datetime_local  TIMESTAMP NOT NULL,
    local_date      DATE NOT NULL,
    local_hour      SMALLINT NOT NULL CHECK (local_hour BETWEEN 0 AND 23),

    pm2_5               NUMERIC(6,2),
    pm10                NUMERIC(6,2),
    nitrogen_dioxide    NUMERIC(6,2),
    ozone               NUMERIC(6,2),
    sulphur_dioxide     NUMERIC(6,2),
    carbon_monoxide     NUMERIC(7,2),
    uv_index            NUMERIC(5,2),

    validation_flags    TEXT[],
    ingested_at         TIMESTAMPTZ NOT NULL DEFAULT now(),

    PRIMARY KEY (city_id, datetime_utc)
);

CREATE INDEX IF NOT EXISTS idx_hourly_local_date
    ON fact_hourly_air_quality (city_id, local_date);

CREATE INDEX IF NOT EXISTS idx_hourly_local_hour
    ON fact_hourly_air_quality (local_hour);

-- Bảng fact theo ngày — chất lượng không khí (Gold layer)
CREATE TABLE IF NOT EXISTS fact_daily_air_quality (
    city_id           VARCHAR(20) NOT NULL REFERENCES dim_city(city_id),
    local_date        DATE NOT NULL,

    pm2_5_avg         NUMERIC(6,2),
    pm2_5_max         NUMERIC(6,2),
    pm2_5_peak_hour   SMALLINT CHECK (pm2_5_peak_hour BETWEEN 0 AND 23),
    pm10_avg          NUMERIC(6,2),

    hours_recorded    SMALLINT NOT NULL CHECK (hours_recorded BETWEEN 0 AND 24),
    exceeds_who       BOOLEAN,
    aqi_category      VARCHAR(20),
    ingested_at       TIMESTAMPTZ NOT NULL DEFAULT now(),

    PRIMARY KEY (city_id, local_date)
);

-- Bảng fact theo ngày — thời tiết (Gold layer)
CREATE TABLE IF NOT EXISTS fact_daily_weather (
    city_id                VARCHAR(20) NOT NULL REFERENCES dim_city(city_id),
    weather_date           DATE NOT NULL,

    precipitation_sum      NUMERIC(6,2),
    windspeed_10m_max      NUMERIC(6,2),
    temperature_2m_max     NUMERIC(5,2),
    temperature_2m_min     NUMERIC(5,2),
    ingested_at            TIMESTAMPTZ NOT NULL DEFAULT now(),

    PRIMARY KEY (city_id, weather_date)
);

-- Seed dữ liệu 6 thành phố
INSERT INTO dim_city (city_id, name, latitude, longitude, region) VALUES
    ('hanoi',    'Hà Nội',           21.0285, 105.8542, 'Bắc'),
    ('haiphong', 'Hải Phòng',        20.8449, 106.6881, 'Bắc'),
    ('danang',   'Đà Nẵng',          16.0544, 108.2022, 'Trung'),
    ('hcmc',     'TP. Hồ Chí Minh',  10.8231, 106.6297, 'Nam'),
    ('cantho',   'Cần Thơ',          10.0452, 105.7469, 'Nam'),
    ('dalat',    'Đà Lạt',           11.9404, 108.4583, 'Trung')
ON CONFLICT (city_id) DO UPDATE SET
    name      = EXCLUDED.name,
    latitude  = EXCLUDED.latitude,
    longitude = EXCLUDED.longitude,
    region    = EXCLUDED.region;