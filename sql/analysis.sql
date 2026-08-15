-- ============================================================
-- Vietnam Air Quality — Analysis Queries
-- Data: 80,328 hourly rows | 6 cities | 18 months (2025-02 to 2026-08)
--
-- Ordered to match the five parts of README.md:
--   PART 1  What the air is like
--   PART 2  Three ways the obvious answer is wrong
--   PART 3  What travels with pollution
--   PART 4  Testing five obvious explanations
--   PART 5  Where that leaves the causes
--
-- NOTE: queries joining dim_city return Vietnamese city names.
--       Run those via pgAdmin; psql console on Windows has
--       WIN1252 encoding issues with Vietnamese characters.
-- ============================================================


-- ============================================================
-- PART 1 — WHAT THE AIR IS LIKE
-- Feeds charts 01 (WHO exceedance) and 02 (19-month series)
-- ============================================================

-- 1.1 Days exceeding WHO guideline, by city
SELECT
    c.name                                                              AS city,
    COUNT(*)                                                            AS total_days,
    COUNT(*) FILTER (WHERE a.exceeds_who)                               AS days_exceeding,
    ROUND(100.0 * COUNT(*) FILTER (WHERE a.exceeds_who) / COUNT(*), 1)  AS pct_exceeding,
    ROUND(AVG(a.pm2_5_avg), 1)                                          AS pm25_avg
FROM fact_daily_air_quality a
JOIN dim_city c ON a.city_id = c.city_id
WHERE a.hours_recorded = 24     -- REQUIRED: partial days skew results up to 34%
GROUP BY c.name
ORDER BY pct_exceeding DESC;


-- ============================================================
-- PART 2 — THREE WAYS THE OBVIOUS ANSWER IS WRONG
-- Not one problem (chart 11), not one pollutant (chart 12),
-- not one cause (chart 05)
-- ============================================================

-- 2.1 Daily rhythm over 24 hours + NO2/O3 photochemical cycle
SELECT
    local_hour,
    ROUND(AVG(pm2_5), 1)                                       AS pm25_all_cities,
    ROUND(AVG(CASE WHEN city_id = 'hanoi' THEN pm2_5 END), 1)  AS hanoi,
    ROUND(AVG(CASE WHEN city_id = 'hcmc'  THEN pm2_5 END), 1)  AS hcmc,
    ROUND(AVG(CASE WHEN city_id = 'dalat' THEN pm2_5 END), 1)  AS dalat,
    ROUND(AVG(nitrogen_dioxide), 1)                            AS no2,
    ROUND(AVG(ozone), 1)                                       AS o3
FROM fact_hourly_air_quality
GROUP BY local_hour
ORDER BY local_hour;


-- 2.2 Monthly variation by region
-- Chart: MULTI-LINE CHART over months
-- Uses city_id instead of region to avoid Vietnamese encoding issues
SELECT
    TO_CHAR(local_date, 'YYYY-MM')                                                AS month,
    ROUND(AVG(CASE WHEN city_id IN ('hanoi','haiphong') THEN pm2_5_avg END), 1)   AS north,
    ROUND(AVG(CASE WHEN city_id IN ('danang','dalat')   THEN pm2_5_avg END), 1)   AS central,
    ROUND(AVG(CASE WHEN city_id IN ('hcmc','cantho')    THEN pm2_5_avg END), 1)   AS south
FROM fact_daily_air_quality
WHERE hours_recorded = 24
GROUP BY month
ORDER BY month;


-- 2.3 Seasonal summary
SELECT
    CASE
        WHEN EXTRACT(MONTH FROM local_date) IN (12,1,2) THEN '1. Winter (Dec-Feb)'
        WHEN EXTRACT(MONTH FROM local_date) IN (3,4,5)  THEN '2. Spring (Mar-May)'
        WHEN EXTRACT(MONTH FROM local_date) IN (6,7,8)  THEN '3. Summer (Jun-Aug)'
        ELSE                                                 '4. Autumn (Sep-Nov)'
    END                                                                           AS season,
    ROUND(AVG(CASE WHEN city_id IN ('hanoi','haiphong') THEN pm2_5_avg END), 1)   AS north,
    ROUND(AVG(CASE WHEN city_id IN ('danang','dalat')   THEN pm2_5_avg END), 1)   AS central,
    ROUND(AVG(CASE WHEN city_id IN ('hcmc','cantho')    THEN pm2_5_avg END), 1)   AS south
FROM fact_daily_air_quality
WHERE hours_recorded = 24
GROUP BY season
ORDER BY season;


-- ============================================================
-- PART 3 — WHAT TRAVELS WITH POLLUTION
-- Weather association: charts 15 (clean vs dirty days) and
-- 16 (per-city sensitivity)
-- ============================================================

-- ------------------------------------------------------------
-- TWIST 1: Peak pollution does NOT match rush hour
-- -> Reuse query 2.1; shade the 7-8am and 5-6pm bands on the
--    chart. Readers see it themselves: rush hour falls where
--    PM2.5 is DECLINING, not peaking.
-- ------------------------------------------------------------

-- ------------------------------------------------------------
-- TWIST 2: Weekends are NOT cleaner than weekdays
-- NO CHART HERE — the gap is too small (max 2.3 ug/m3).
-- A bar chart with Y-axis at 0 makes both bars look identical;
-- truncating the Y-axis to exaggerate the gap MISLEADS.
-- Honest presentation: show the numbers in a table.
-- ------------------------------------------------------------
SELECT
    city_id,
    ROUND(AVG(CASE WHEN EXTRACT(DOW FROM local_date) BETWEEN 1 AND 5
                   THEN pm2_5_avg END), 1)                              AS weekday_avg,
    ROUND(AVG(CASE WHEN EXTRACT(DOW FROM local_date) IN (0,6)
                   THEN pm2_5_avg END), 1)                              AS weekend_avg,
    ROUND(AVG(CASE WHEN EXTRACT(DOW FROM local_date) IN (0,6)
                   THEN pm2_5_avg END)
        - AVG(CASE WHEN EXTRACT(DOW FROM local_date) BETWEEN 1 AND 5
                   THEN pm2_5_avg END), 1)                              AS difference
FROM fact_daily_air_quality
WHERE hours_recorded = 24
GROUP BY city_id
ORDER BY city_id;


-- Breakdown by day of week (0=Sunday, 6=Saturday)
SELECT
    EXTRACT(DOW FROM local_date)  AS day_of_week,
    COUNT(*)                      AS total_days,
    ROUND(AVG(pm2_5_avg), 1)      AS pm25_avg
FROM fact_daily_air_quality
WHERE hours_recorded = 24
GROUP BY day_of_week
ORDER BY day_of_week;


-- ------------------------------------------------------------
-- TWIST 3: Rain barely reduces PM2.5
-- The original project spec predicted "heavy rain clearly
-- reduces fine dust". The data says otherwise: r = -0.094.
-- Chart: BAR CHART, 4 rain buckets, Y-axis starting at 0
-- ------------------------------------------------------------
WITH daily AS (
    SELECT
        a.city_id,
        a.local_date,
        a.pm2_5_avg,
        w.precipitation_sum,
        LAG(a.pm2_5_avg) OVER (PARTITION BY a.city_id ORDER BY a.local_date) AS pm25_prev_day
    FROM fact_daily_air_quality a
    JOIN fact_daily_weather w
      ON a.city_id = w.city_id AND a.local_date = w.weather_date
    WHERE a.hours_recorded = 24
)
SELECT
    CASE
        WHEN precipitation_sum = 0  THEN '1. No rain'
        WHEN precipitation_sum < 5  THEN '2. Light (<5mm)'
        WHEN precipitation_sum < 20 THEN '3. Moderate (5-20mm)'
        ELSE                             '4. Heavy (>20mm)'
    END                                                                       AS rain_level,
    COUNT(*)                                                                  AS total_days,
    ROUND(AVG(pm2_5_avg), 2)                                                  AS pm25_avg,
    ROUND(AVG(pm2_5_avg - pm25_prev_day), 2)                                  AS change_vs_prev_day,
    ROUND(AVG((pm2_5_avg - pm25_prev_day) / NULLIF(pm25_prev_day, 0) * 100), 1) AS pct_change
FROM daily
WHERE pm25_prev_day IS NOT NULL
GROUP BY rain_level
ORDER BY rain_level;


-- Testing the LAG hypothesis: does rain today mean cleaner air tomorrow?
WITH daily AS (
    SELECT
        a.city_id, a.local_date, a.pm2_5_avg, w.precipitation_sum,
        LEAD(a.pm2_5_avg) OVER (PARTITION BY a.city_id ORDER BY a.local_date) AS pm25_next_day
    FROM fact_daily_air_quality a
    JOIN fact_daily_weather w
      ON a.city_id = w.city_id AND a.local_date = w.weather_date
    WHERE a.hours_recorded = 24
)
SELECT
    CASE WHEN precipitation_sum = 0  THEN '1. No rain'
         WHEN precipitation_sum < 20 THEN '2. Moderate'
         ELSE                             '3. Heavy (>20mm)' END AS rain_level,
    COUNT(*)                                  AS total_days,
    ROUND(AVG(pm2_5_avg), 2)                  AS pm25_today,
    ROUND(AVG(pm25_next_day), 2)              AS pm25_tomorrow,
    ROUND(AVG(pm25_next_day - pm2_5_avg), 2)  AS difference
FROM daily
WHERE pm25_next_day IS NOT NULL
GROUP BY rain_level
ORDER BY rain_level;

-- 3.4 Weather on a city's dirtiest days against its own cleanest days
-- Deciles are cut WITHIN each city, so the comparison is about days rather
-- than places: pooling all 3,341 days would put most of Da Lat in the clean
-- group and most of Hanoi in the dirty one.
WITH r AS (
    SELECT a.city_id, a.pm2_5_avg,
           w.windspeed_10m_max, w.precipitation_sum, w.temperature_2m_max,
           (w.temperature_2m_max - w.temperature_2m_min) AS trange,
           NTILE(10) OVER (PARTITION BY a.city_id ORDER BY a.pm2_5_avg) AS decile
    FROM fact_daily_air_quality a
    JOIN fact_daily_weather w
      ON a.city_id = w.city_id AND a.local_date = w.weather_date
    WHERE a.hours_recorded = 24
), per_city AS (
    SELECT city_id,
           CASE WHEN decile = 1 THEN 'cleanest_decile' ELSE 'dirtiest_decile' END AS grp,
           AVG(windspeed_10m_max)  AS wind,
           AVG(precipitation_sum)  AS rain,
           AVG(trange)             AS temp_range,
           AVG(temperature_2m_max) AS tmax
    FROM r WHERE decile IN (1, 10)
    GROUP BY city_id, decile
)
SELECT grp,
       ROUND(AVG(wind)::numeric, 1)       AS wind_kmh,
       ROUND(AVG(rain)::numeric, 1)       AS rain_mm,
       ROUND(AVG(temp_range)::numeric, 1) AS temp_range_c,
       ROUND(AVG(tmax)::numeric, 1)       AS tmax_c
FROM per_city
GROUP BY grp
ORDER BY grp;




-- ============================================================
-- PART 4 — TESTING FIVE OBVIOUS EXPLANATIONS
-- Four fail, one survives. Chart 07 carries the daily-cycle test.
-- ============================================================

-- 4.1 Which weather factor actually matters?
-- Chart: DIVERGING BAR (values span negative and positive around 0)
SELECT
    ROUND(CORR(a.pm2_5_avg, w.windspeed_10m_max)::numeric, 3)  AS wind_speed,
    ROUND(CORR(a.pm2_5_avg, w.precipitation_sum)::numeric, 3)  AS precipitation,
    ROUND(CORR(a.pm2_5_avg, w.temperature_2m_max)::numeric, 3) AS max_temperature,
    ROUND(CORR(a.pm2_5_avg,
        (w.temperature_2m_max - w.temperature_2m_min))::numeric, 3) AS temp_range
FROM fact_daily_air_quality a
JOIN fact_daily_weather w
  ON a.city_id = w.city_id AND a.local_date = w.weather_date
WHERE a.hours_recorded = 24;


-- 4.2 Per-city correlations — is the pattern consistent?
SELECT
    a.city_id,
    ROUND(CORR(a.pm2_5_avg, w.windspeed_10m_max)::numeric, 3)  AS wind_speed,
    ROUND(CORR(a.pm2_5_avg, w.precipitation_sum)::numeric, 3)  AS precipitation,
    ROUND(CORR(a.pm2_5_avg, w.temperature_2m_max)::numeric, 3) AS temperature
FROM fact_daily_air_quality a
JOIN fact_daily_weather w
  ON a.city_id = w.city_id AND a.local_date = w.weather_date
WHERE a.hours_recorded = 24
GROUP BY a.city_id
ORDER BY a.city_id;


-- 4.3 Each city has a distinct pollution fingerprint
-- Source markers:  high SO2       = coal burning / heavy industry
--                  high NO2 + CO  = vehicle traffic
--                  PM2.5 ~ PM10   = combustion, not mechanical dust
-- Chart: GROUPED BAR (6 cities x 4 pollutants)
SELECT
    city_id,
    ROUND(AVG(pm2_5), 1)            AS pm25,
    ROUND(AVG(pm10), 1)             AS pm10,
    ROUND(AVG(nitrogen_dioxide), 1) AS no2,
    ROUND(AVG(sulphur_dioxide), 1)  AS so2,
    ROUND(AVG(carbon_monoxide), 1)  AS co,
    ROUND(AVG(ozone), 1)            AS o3
FROM fact_hourly_air_quality
GROUP BY city_id
ORDER BY AVG(pm2_5) DESC;


-- 4.4 Normalized ratios — fair comparison across cities with
-- different absolute pollution levels
SELECT
    city_id,
    ROUND((AVG(sulphur_dioxide)  / AVG(pm2_5))::numeric, 3) AS so2_to_pm25,
    ROUND((AVG(nitrogen_dioxide) / AVG(pm2_5))::numeric, 3) AS no2_to_pm25,
    ROUND((AVG(carbon_monoxide)  / AVG(pm2_5))::numeric, 1) AS co_to_pm25,
    ROUND((AVG(pm2_5) / AVG(pm10))::numeric, 3)             AS pm25_to_pm10
FROM fact_hourly_air_quality
GROUP BY city_id
ORDER BY so2_to_pm25 DESC;


-- 4.5 Inter-pollutant correlations — confirming shared sources
SELECT
    ROUND(CORR(pm2_5, pm10)::numeric, 3)                       AS pm25_pm10,
    ROUND(CORR(pm2_5, nitrogen_dioxide)::numeric, 3)           AS pm25_no2,
    ROUND(CORR(pm2_5, carbon_monoxide)::numeric, 3)            AS pm25_co,
    ROUND(CORR(pm2_5, ozone)::numeric, 3)                      AS pm25_o3,
    ROUND(CORR(nitrogen_dioxide, carbon_monoxide)::numeric, 3) AS no2_co,
    ROUND(CORR(ozone, uv_index)::numeric, 3)                   AS o3_uv
FROM fact_hourly_air_quality;

-- 4.6 Partial correlations - does each weather factor survive controlling for wind?
-- r(A,B | C) = [r(A,B) - r(A,C)*r(B,C)] / sqrt[(1-r(A,C)^2)(1-r(B,C)^2)]
-- Warm days tend to be calm, and rainy days tend to be windy, so a raw
-- correlation cannot tell whether temperature and rain matter in their own right.
WITH c AS (
    SELECT
        CORR(a.pm2_5_avg, w.temperature_2m_max)         AS r_pt,
        CORR(a.pm2_5_avg, w.windspeed_10m_max)          AS r_pw,
        CORR(w.temperature_2m_max, w.windspeed_10m_max) AS r_tw,
        CORR(a.pm2_5_avg, w.precipitation_sum)          AS r_pr,
        CORR(w.precipitation_sum, w.windspeed_10m_max)  AS r_rw
    FROM fact_daily_air_quality a
    JOIN fact_daily_weather w
      ON a.city_id = w.city_id AND a.local_date = w.weather_date
    WHERE a.hours_recorded = 24
)
SELECT
    ROUND(r_pt::numeric, 3) AS temp_raw,
    ROUND(((r_pt - r_pw * r_tw)
        / SQRT((1 - POWER(r_pw, 2)) * (1 - POWER(r_tw, 2))))::numeric, 3) AS temp_given_wind,
    ROUND(r_pr::numeric, 3) AS rain_raw,
    ROUND(((r_pr - r_pw * r_rw)
        / SQRT((1 - POWER(r_pw, 2)) * (1 - POWER(r_rw, 2))))::numeric, 3) AS rain_given_wind,
    ROUND(r_tw::numeric, 3) AS temp_vs_wind,
    ROUND(r_rw::numeric, 3) AS rain_vs_wind
FROM c;


-- 4.7 Significance check for the two weakest coefficients
-- t = r * sqrt((n-2) / (1-r^2)); |t| > 2 clears the 5 percent threshold
SELECT 'pm25_vs_ozone' AS pair, COUNT(*) AS n,
    ROUND(CORR(pm2_5, ozone)::numeric, 3) AS r,
    ROUND((CORR(pm2_5, ozone)
        * SQRT((COUNT(*) - 2) / (1 - POWER(CORR(pm2_5, ozone), 2))))::numeric, 1) AS t_stat
FROM fact_hourly_air_quality
UNION ALL
SELECT 'pm25_vs_rain', COUNT(*),
    ROUND(CORR(a.pm2_5_avg, w.precipitation_sum)::numeric, 3),
    ROUND((CORR(a.pm2_5_avg, w.precipitation_sum)
        * SQRT((COUNT(*) - 2)
            / (1 - POWER(CORR(a.pm2_5_avg, w.precipitation_sum), 2))))::numeric, 1)
FROM fact_daily_air_quality a
JOIN fact_daily_weather w
  ON a.city_id = w.city_id AND a.local_date = w.weather_date
WHERE a.hours_recorded = 24;




-- ============================================================
-- PART 5 — WHERE THAT LEAVES THE CAUSES
-- Chart 17 sets each hypothesis against the number that tests it
-- ============================================================

-- 5.1 Sustained pollution episodes (3+ consecutive days)
-- Technique: GAPS-AND-ISLANDS using ROW_NUMBER()
-- Principle: for consecutive dates, (local_date - ROW_NUMBER())
--            stays constant; a gap produces a different value,
--            which then serves as the grouping key for "islands"
-- Chart: GANTT-STYLE HORIZONTAL BAR
WITH flagged AS (
    SELECT
        city_id,
        local_date,
        pm2_5_avg,
        local_date - (ROW_NUMBER() OVER (PARTITION BY city_id
                                         ORDER BY local_date))::int AS grp
    FROM fact_daily_air_quality
    WHERE hours_recorded = 24
      AND pm2_5_avg > 35        -- "Unhealthy for sensitive groups" AQI threshold
)
SELECT
    city_id,
    MIN(local_date)          AS start_date,
    MAX(local_date)          AS end_date,
    COUNT(*)                 AS consecutive_days,
    ROUND(AVG(pm2_5_avg), 1) AS pm25_avg,
    ROUND(MAX(pm2_5_avg), 1) AS pm25_peak
FROM flagged
GROUP BY city_id, grp
HAVING COUNT(*) >= 3
ORDER BY consecutive_days DESC
LIMIT 20;


-- 5.2 Episode statistics by city
WITH flagged AS (
    SELECT city_id, local_date,
        local_date - (ROW_NUMBER() OVER (PARTITION BY city_id
                                         ORDER BY local_date))::int AS grp
    FROM fact_daily_air_quality
    WHERE hours_recorded = 24 AND pm2_5_avg > 35
),
episodes AS (
    SELECT city_id, COUNT(*) AS episode_length
    FROM flagged GROUP BY city_id, grp HAVING COUNT(*) >= 3
)
SELECT
    city_id,
    COUNT(*)                        AS episode_count,
    SUM(episode_length)             AS total_days_in_episodes,
    ROUND(AVG(episode_length), 1)   AS avg_episode_length,
    MAX(episode_length)             AS longest_episode
FROM episodes
GROUP BY city_id
ORDER BY total_days_in_episodes DESC;


-- 5.3 Which months to avoid, by city
-- Chart: HEATMAP (X = 12 months, Y = 6 cities, color = pct bad days)
SELECT
    city_id,
    EXTRACT(MONTH FROM local_date)                                      AS month,
    ROUND(AVG(pm2_5_avg), 1)                                            AS pm25_avg,
    ROUND(100.0 * COUNT(*) FILTER (WHERE pm2_5_avg > 35) / COUNT(*), 1) AS pct_bad_days
FROM fact_daily_air_quality
WHERE hours_recorded = 24
GROUP BY city_id, month
ORDER BY city_id, month;


-- 5.4 Year-over-year comparison
-- CAVEAT: 18 months is TOO SHORT to establish a long-term trend.
-- This compares only 7 overlapping months (Feb-Aug) across two
-- years. Treat as a preliminary observation, NOT a trend analysis.
-- Chart: SLOPE CHART (if used) — must state the limitation
SELECT
    city_id,
    EXTRACT(MONTH FROM local_date) AS month,
    ROUND(AVG(CASE WHEN EXTRACT(YEAR FROM local_date) = 2025
                   THEN pm2_5_avg END), 1) AS year_2025,
    ROUND(AVG(CASE WHEN EXTRACT(YEAR FROM local_date) = 2026
                   THEN pm2_5_avg END), 1) AS year_2026,
    ROUND(AVG(CASE WHEN EXTRACT(YEAR FROM local_date) = 2026 THEN pm2_5_avg END)
        - AVG(CASE WHEN EXTRACT(YEAR FROM local_date) = 2025 THEN pm2_5_avg END), 1)
                                           AS difference
FROM fact_daily_air_quality
WHERE hours_recorded = 24
  AND EXTRACT(MONTH FROM local_date) BETWEEN 2 AND 8
GROUP BY city_id, month
ORDER BY city_id, month;


-- ============================================================
-- APPENDIX — Data quality checks
-- ============================================================

-- Completeness
SELECT
    MIN(local_date)                              AS first_date,
    MAX(local_date)                              AS last_date,
    COUNT(DISTINCT local_date)                   AS distinct_days,
    COUNT(*) FILTER (WHERE hours_recorded = 24)  AS complete_days,
    COUNT(*) FILTER (WHERE hours_recorded < 24)  AS partial_days,
    ROUND(100.0 * COUNT(*) FILTER (WHERE hours_recorded = 24) / COUNT(*), 2) AS pct_complete
FROM fact_daily_air_quality;


-- Descriptive statistics for PM2.5 by city
SELECT
    city_id,
    COUNT(*)                    AS total_days,
    ROUND(MIN(pm2_5_avg), 1)    AS min_value,
    ROUND(AVG(pm2_5_avg), 1)    AS mean_value,
    ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY pm2_5_avg)::numeric, 1) AS median_value,
    ROUND(MAX(pm2_5_avg), 1)    AS max_value,
    ROUND(STDDEV(pm2_5_avg), 1) AS std_dev
FROM fact_daily_air_quality
WHERE hours_recorded = 24
GROUP BY city_id
ORDER BY AVG(pm2_5_avg) DESC;


-- Validation rule violations
SELECT validation_flags, COUNT(*)
FROM fact_hourly_air_quality
WHERE validation_flags IS NOT NULL AND validation_flags != '{}'
GROUP BY validation_flags;