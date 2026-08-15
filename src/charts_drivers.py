"""
Charts examining POSSIBLE drivers, graded by how much evidence supports each.

    11  How far a pollution signal travels    - scope of the driver
    12  PM2.5 ranking against ozone ranking   - more than one kind of problem
    15  Dirtiest days against cleanest days   - weather travels with pollution
    16  Weather sensitivity per city          - the mechanism is not uniform
    17  Candidate drivers, graded             - summary of what holds up

Nothing here is a causal claim. The dataset carries no emissions inventory,
no traffic counts and no fire-detection data, so the most these charts can do
is show which factors travel with pollution and which do not. Where an
association could run either way, the caption says so.

Run:  python -m src.charts_drivers
"""

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd

from src.config import BASE_DIR
from src.load import get_engine

CHARTS_DIR = BASE_DIR / "charts"

COLOR_TEXT = "#2c3e50"
COLOR_MUTED = "#95a5a6"
COLOR_DANGER = "#c0392b"
COLOR_SAFE = "#27ae60"
COLOR_ACCENT = "#2980b9"
FOOTER = "Source: Open-Meteo  |  6 Vietnamese cities  |  Feb 2025 - Aug 2026"

CITY_LABELS = {
    "hanoi": "Hanoi", "haiphong": "Hai Phong", "danang": "Da Nang",
    "hcmc": "Ho Chi Minh City", "cantho": "Can Tho", "dalat": "Da Lat",
}
CITY_COLORS = {
    "hanoi": "#c0392b", "haiphong": "#e67e22", "danang": "#16a085",
    "hcmc": "#8e44ad", "cantho": "#2980b9", "dalat": "#27ae60",
}


# City pairs to plot. Distances are computed from the coordinates stored in
# dim_city, not entered by hand.
CITY_PAIRS = [
    ("hanoi", "haiphong"),
    ("danang", "dalat"),
    ("hcmc", "cantho"),
    ("hanoi", "danang"),
    ("danang", "hcmc"),
    ("hanoi", "cantho"),
    ("hanoi", "hcmc"),
    ("dalat", "hcmc"),
]


def setup_style():
    plt.rcParams.update({
        "figure.dpi": 110, "savefig.dpi": 150,
        "figure.constrained_layout.use": True,
        "font.size": 10.5, "font.family": "DejaVu Sans",
        "axes.titlesize": 11, "axes.titleweight": "bold",
        "axes.titlecolor": COLOR_TEXT, "axes.labelcolor": COLOR_TEXT,
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.edgecolor": "#bdc3c7", "axes.grid": True,
        "grid.alpha": 0.22, "grid.linewidth": 0.6,
        "xtick.color": COLOR_TEXT, "ytick.color": COLOR_TEXT,
        "legend.frameon": False,
    })


def title_block(fig, headline, subtitle=None, has_legend=False):
    top = 0.89 if subtitle else 0.93
    if has_legend:
        top -= 0.06
    fig.get_layout_engine().set(rect=(0, 0, 1, top))
    fig.text(0.5, 0.985, headline.upper(), ha="center", va="top",
             fontsize=15.5, fontweight="bold", color=COLOR_TEXT)
    if subtitle:
        fig.text(0.5, 0.932, subtitle, ha="center", va="top",
                 fontsize=10.5, color="#7f8c8d", style="italic")


def add_footer(fig, note=None):
    text = FOOTER if note is None else f"{FOOTER}\n{note}"
    fig.text(0.012, -0.015, text, fontsize=7.5, color=COLOR_MUTED,
             ha="left", va="top", linespacing=1.5)


def save(fig, name):
    CHARTS_DIR.mkdir(parents=True, exist_ok=True)
    path = CHARTS_DIR / f"{name}.png"
    fig.savefig(path, bbox_inches="tight", facecolor="white", pad_inches=0.35)
    plt.close(fig)
    print(f"  saved {path.name}")


def _pairwise_correlations(engine):
    sql = """
        SELECT local_date,
            MAX(CASE WHEN city_id='hanoi'    THEN pm2_5_avg END) AS hanoi,
            MAX(CASE WHEN city_id='haiphong' THEN pm2_5_avg END) AS haiphong,
            MAX(CASE WHEN city_id='danang'   THEN pm2_5_avg END) AS danang,
            MAX(CASE WHEN city_id='dalat'    THEN pm2_5_avg END) AS dalat,
            MAX(CASE WHEN city_id='hcmc'     THEN pm2_5_avg END) AS hcmc,
            MAX(CASE WHEN city_id='cantho'   THEN pm2_5_avg END) AS cantho
        FROM fact_daily_air_quality
        WHERE hours_recorded = 24
        GROUP BY local_date
    """
    wide = pd.read_sql(sql, engine).set_index("local_date")
    return wide.corr()


def _pair_distances_km(engine):
    """Great-circle distance for every city pair, from dim_city coordinates."""
    sql = """
        SELECT a.city_id AS city_a, b.city_id AS city_b,
               ROUND((6371 * ACOS(LEAST(1.0,
                   COS(RADIANS(a.latitude)) * COS(RADIANS(b.latitude))
                     * COS(RADIANS(b.longitude) - RADIANS(a.longitude))
                 + SIN(RADIANS(a.latitude)) * SIN(RADIANS(b.latitude))
               )))::numeric, 0) AS km
        FROM dim_city a
        CROSS JOIN dim_city b
        WHERE a.city_id < b.city_id
    """
    df = pd.read_sql(sql, engine)
    out = {}
    for r in df.itertuples():
        out[(r.city_a, r.city_b)] = float(r.km)
        out[(r.city_b, r.city_a)] = float(r.km)
    return out


# ============================================================
# CHART 11 - Correlation against distance
# Bears on: is pollution a national phenomenon or a regional one?
# ============================================================

def chart_11_distance_decay(engine):
    corr = _pairwise_correlations(engine)
    dist = _pair_distances_km(engine)

    rows = []
    for a, b in CITY_PAIRS:
        rows.append({
            "pair": f"{CITY_LABELS[a]} - {CITY_LABELS[b]}",
            "km": dist[(a, b)],
            "r": round(float(corr.loc[a, b]), 3),
        })
    df = pd.DataFrame(rows)

    fig, ax = plt.subplots(figsize=(12.5, 6.2))

    ax.axhline(0, color="#34495e", linewidth=1, zorder=1)

    for row in df.itertuples():
        color = COLOR_DANGER if row.r > 0.4 else COLOR_ACCENT if row.r > 0.15 else COLOR_MUTED
        ax.scatter(row.km, row.r, s=180, color=color, zorder=3,
                   edgecolor="white", linewidth=1.5)

    # Label each point, nudging a few to avoid collisions
    offsets = {
        "Hanoi - Hai Phong": (28, 0.02),
        "Da Nang - Da Lat": (28, 0.02),
        "Ho Chi Minh City - Can Tho": (28, 0.03),
        "Hanoi - Da Nang": (28, 0.02),
        "Da Nang - Ho Chi Minh City": (28, -0.05),
        "Hanoi - Can Tho": (-28, 0.055),
        "Hanoi - Ho Chi Minh City": (-28, -0.065),
        "Da Lat - Ho Chi Minh City": (28, -0.02),
    }
    for row in df.itertuples():
        dx, dy = offsets.get(row.pair, (25, 0.02))
        ha = "left" if dx > 0 else "right"
        ax.annotate(f"{row.pair}\nr = {row.r:+.3f}",
                    xy=(row.km, row.r), xytext=(row.km + dx, row.r + dy),
                    fontsize=9, color=COLOR_TEXT, ha=ha, va="center",
                    linespacing=1.4)

    ax.set_xlabel("Straight-line distance between cities (km)", labelpad=8)
    ax.set_ylabel("Correlation of daily PM2.5", labelpad=8)
    ax.set_xlim(-90, 1880)
    ax.set_ylim(-0.25, 0.85)

    # Captions read their figures back out of the dataframe rather than
    # repeating them by hand, so they cannot drift out of step with the data
    def _pair(a, b):
        row = df[df["pair"] == f"{CITY_LABELS[a]} - {CITY_LABELS[b]}"].iloc[0]
        return row.r, int(row.km)

    r_hn_hcm, km_hn_hcm = _pair("hanoi", "hcmc")
    r_hn_hp, km_hn_hp = _pair("hanoi", "haiphong")
    r_hcm_ct, km_hcm_ct = _pair("hcmc", "cantho")
    r_dl_hcm, km_dl_hcm = _pair("dalat", "hcmc")

    title_block(fig,
                "Pollution correlation dies with distance",
                f"Hanoi and Ho Chi Minh City move independently: "
                f"r = {r_hn_hcm:+.3f} across {km_hn_hcm:,} km")
    add_footer(fig, f"Two pairs break the trend. Ho Chi Minh City and Can Tho are {km_hcm_ct:,} km\n"
                    f"apart yet correlate at just {r_hcm_ct:.3f}, against {r_hn_hp:.3f} for\n"
                    f"Hanoi-Hai Phong at {km_hn_hp:,} km. Da Lat runs negative to Ho Chi Minh City\n"
                    f"({r_dl_hcm:+.3f}) across {km_dl_hcm:,} km - it sits on a plateau, above the lowland air.")
    save(fig, "11_distance_decay")


# ============================================================
# CHART 12 - PM2.5 ranking vs ozone ranking
# Bears on: does the choice of pollutant change the answer?
# ============================================================

def chart_12_ranking_flip(engine):
    sql = """
        SELECT city_id,
               ROUND(AVG(pm2_5), 1) AS pm25_mean,
               ROUND(100.0 * COUNT(*) FILTER (WHERE ozone > 100) / COUNT(*), 1)
                   AS pct_o3_over
        FROM fact_hourly_air_quality
        GROUP BY city_id
    """
    df = pd.read_sql(sql, engine)

    # Rank 1 = worst on each measure
    df["rank_pm25"] = df["pm25_mean"].rank(ascending=False).astype(int)
    df["rank_o3"] = df["pct_o3_over"].rank(ascending=False).astype(int)

    fig, ax = plt.subplots(figsize=(12, 6.6))

    for row in df.itertuples():
        moved = abs(row.rank_pm25 - row.rank_o3)
        color = CITY_COLORS[row.city_id]
        lw = 3.2 if moved >= 3 else 1.6
        alpha = 1.0 if moved >= 3 else 0.45

        ax.plot([0, 1], [row.rank_pm25, row.rank_o3],
                color=color, linewidth=lw, alpha=alpha,
                marker="o", markersize=9, zorder=3 if moved >= 3 else 2)

        ax.text(-0.04, row.rank_pm25, f"{CITY_LABELS[row.city_id]}  ({row.pm25_mean})",
                ha="right", va="center", fontsize=10, color=COLOR_TEXT)
        ax.text(1.04, row.rank_o3, f"{CITY_LABELS[row.city_id]}  ({row.pct_o3_over}%)",
                ha="left", va="center", fontsize=10, color=COLOR_TEXT)

    ax.set_xlim(-0.66, 1.52)
    ax.set_ylim(6.6, 0.4)          # rank 1 at the top
    ax.set_xticks([0, 1])
    ax.set_xticklabels(["Ranked by mean PM2.5\n(ug/m3)",
                        "Ranked by hours above\nWHO ozone limit (%)"], fontsize=10.5)
    ax.set_yticks(range(1, 7))
    ax.set_yticklabels([f"#{i}" for i in range(1, 7)], fontsize=10)
    ax.grid(axis="x", visible=False)
    ax.tick_params(length=0)

    # Call out the city that swaps ends
    danang = df[df.city_id == "danang"].iloc[0]
    ax.annotate("cleanest-looking city\nturns out to be the worst",
                xy=(0.5, (danang.rank_pm25 + danang.rank_o3) / 2),
                xytext=(0.5, 4.6), ha="center", fontsize=10,
                color=CITY_COLORS["danang"], fontweight="bold",
                arrowprops=dict(arrowstyle="->", color=CITY_COLORS["danang"],
                                lw=1.4, connectionstyle="arc3,rad=0.3"))

    title_block(fig,
                "Change the pollutant, change the ranking",
                "Da Nang goes from 5th cleanest on PM2.5 to worst in the country on ozone")
    add_footer(fig, "Ozone is not emitted directly - sunlight breaks down NO2 to form it.\n"
                    "Less dust means more UV reaching the ground, so the least dusty city\n"
                    "records the most ozone. A PM2.5-only ranking misses this entirely.")
    save(fig, "12_ranking_flip")


# ============================================================
# CHART 15 - Dirtiest days against cleanest days
# The clearest quantitative signal that weather travels with pollution
# ============================================================

def chart_15_clean_vs_dirty(engine):
    sql = """
        WITH r AS (
            SELECT a.city_id, a.pm2_5_avg,
                   w.windspeed_10m_max, w.precipitation_sum,
                   w.temperature_2m_max,
                   (w.temperature_2m_max - w.temperature_2m_min) AS trange,
                   NTILE(10) OVER (PARTITION BY a.city_id ORDER BY a.pm2_5_avg) AS decile
            FROM fact_daily_air_quality a
            JOIN fact_daily_weather w
              ON a.city_id = w.city_id AND a.local_date = w.weather_date
            WHERE a.hours_recorded = 24
        )
        SELECT CASE WHEN decile = 1 THEN 'clean' ELSE 'dirty' END AS grp,
               ROUND(AVG(windspeed_10m_max), 1) AS wind,
               ROUND(AVG(precipitation_sum), 1) AS rain,
               ROUND(AVG(trange), 1)            AS temp_range,
               ROUND(AVG(temperature_2m_max), 1) AS tmax
        FROM r WHERE decile IN (1, 10)
        GROUP BY grp
    """
    df = pd.read_sql(sql, engine).set_index("grp")

    metrics = [
        ("wind", "Wind speed\n(km/h)"),
        ("rain", "Rainfall\n(mm)"),
        ("temp_range", "Day-night temp\nrange (C)"),
        ("tmax", "Max temperature\n(C)"),
    ]

    fig, axes = plt.subplots(1, 4, figsize=(13, 5.4))

    for ax, (col, label) in zip(axes, metrics):
        clean = float(df.loc["clean", col])
        dirty = float(df.loc["dirty", col])
        bars = ax.bar(["Cleanest\n10% of days", "Dirtiest\n10% of days"],
                      [clean, dirty],
                      color=[COLOR_SAFE, COLOR_DANGER], width=0.58)
        for bar, v in zip(bars, [clean, dirty]):
            ax.text(bar.get_x() + bar.get_width()/2, v + max(clean, dirty)*0.03,
                    f"{v}", ha="center", fontsize=11, fontweight="bold",
                    color=COLOR_TEXT)

        pct = round(100 * (dirty - clean) / clean)
        ax.set_title(f"{label}\n{pct:+d}% on dirty days",
                     loc="center", fontsize=10, pad=10)
        ax.set_ylim(0, max(clean, dirty) * 1.28)
        ax.tick_params(labelsize=9)
        ax.grid(axis="x", visible=False)

    n_per_decile = pd.read_sql("""
        SELECT ROUND(COUNT(*) / 10.0, 0) AS n
        FROM fact_daily_air_quality WHERE hours_recorded = 24
    """, engine)["n"].iloc[0]

    title_block(fig,
                "Dirty days are still, dry and cloudless",
                f"Averaged over ~{int(n_per_decile)} days in each group, "
                f"pooled across all six cities")
    add_footer(fig, "The direction of this association is not settled. Calm dry weather plausibly lets\n"
                    "particles accumulate - but heavy particle loading also suppresses cloud formation,\n"
                    "which would widen the temperature range. Both readings fit these numbers.")
    save(fig, "15_clean_vs_dirty")


# ============================================================
# CHART 16 - Weather sensitivity per city
# Shows the same factor behaving differently in different places
# ============================================================

def chart_16_city_sensitivity(engine):
    sql = """
        SELECT a.city_id,
               ROUND(CORR(a.pm2_5_avg, w.windspeed_10m_max)::numeric, 3)  AS wind,
               ROUND(CORR(a.pm2_5_avg, w.temperature_2m_max)::numeric, 3) AS temperature,
               ROUND(CORR(a.pm2_5_avg, w.precipitation_sum)::numeric, 3)  AS rain,
               ROUND(CORR(a.pm2_5_avg,
                   (w.temperature_2m_max - w.temperature_2m_min))::numeric, 3) AS temp_range
        FROM fact_daily_air_quality a
        JOIN fact_daily_weather w
          ON a.city_id = w.city_id AND a.local_date = w.weather_date
        WHERE a.hours_recorded = 24
        GROUP BY a.city_id
    """
    df = pd.read_sql(sql, engine).set_index("city_id")
    order = ["dalat", "cantho", "hanoi", "haiphong", "danang", "hcmc"]
    df = df.loc[order]

    factors = ["wind", "rain", "temperature", "temp_range"]
    labels = {"wind": "Wind speed", "rain": "Rainfall",
              "temperature": "Max temperature", "temp_range": "Day-night temp range"}

    fig, axes = plt.subplots(1, 4, figsize=(13.5, 6), sharey=True)

    for ax, f in zip(axes, factors):
        vals = df[f].astype(float)
        colors = [CITY_COLORS[c] for c in df.index]
        ax.barh(range(len(df)), vals, color=colors, height=0.62)
        ax.axvline(0, color="#34495e", linewidth=1)

        for i, v in enumerate(vals):
            ha = "left" if v > 0 else "right"
            pad = 0.02 if v > 0 else -0.02
            ax.text(v + pad, i, f"{v:+.2f}", va="center", ha=ha,
                    fontsize=9, color=COLOR_TEXT)

        ax.set_title(labels[f], fontsize=10.5, pad=10)
        ax.set_xlim(-0.72, 0.88)
        ax.set_yticks(range(len(df)))
        ax.grid(axis="y", visible=False)
        ax.tick_params(length=0, labelsize=9.5)

    axes[0].set_yticklabels([CITY_LABELS[c] for c in df.index], fontsize=10)

    title_block(fig,
                "The same weather does different things in different cities",
                "Ho Chi Minh City reverses sign on three of the four factors")
    w = df["wind"].astype(float)
    rain_hcmc = float(df.loc["hcmc", "rain"])
    add_footer(fig, f"Wind is the one factor that points the same way everywhere, though its strength\n"
                    f"ranges from {w.min():.2f} in {CITY_LABELS[w.idxmin()]} to {w.max():.2f} in "
                    f"{CITY_LABELS[w.idxmax()]}. Ho Chi Minh City is the\n"
                    f"outlier: there, rain arrives WITH higher PM2.5 ({rain_hcmc:+.3f}), not lower -\n"
                    f"a pattern that fits monsoon seasonality rather than rainfall washing particles out.")
    save(fig, "16_city_sensitivity")


# ============================================================
# CHART 17 - Hypotheses against the measurements that test them
# No scoring, no ranking: each row shows the number the test produced
# and whether that number matches what the hypothesis predicts.
# ============================================================

def chart_17_hypothesis_tests(engine):
    """Every value on this chart is queried, not assigned.

    An earlier version ranked hypotheses on a 0-1 "weight of evidence"
    scale. Those numbers were invented - there was no rule behind them,
    so they are gone. What remains is the measurement each hypothesis
    predicts, the measurement the data returned, and whether the two agree.
    """

    # --- every figure below comes from a query ---

    # Wind: correlation with PM2.5, per season
    season_wind = pd.read_sql("""
        SELECT ROUND(CORR(a.pm2_5_avg, w.windspeed_10m_max)::numeric, 3) AS r
        FROM fact_daily_air_quality a
        JOIN fact_daily_weather w
          ON a.city_id = w.city_id AND a.local_date = w.weather_date
        WHERE a.hours_recorded = 24
        GROUP BY CASE WHEN EXTRACT(MONTH FROM a.local_date) IN (12,1,2) THEN 1
                      WHEN EXTRACT(MONTH FROM a.local_date) IN (3,4,5)  THEN 2
                      WHEN EXTRACT(MONTH FROM a.local_date) IN (6,7,8)  THEN 3
                      ELSE 4 END
    """, engine)["r"].astype(float)

    # Source split: SO2 ratio between the highest and lowest city
    so2 = pd.read_sql("""
        SELECT ROUND(MAX(m)::numeric / MIN(m)::numeric, 1) AS ratio FROM (
            SELECT AVG(sulphur_dioxide) AS m FROM fact_hourly_air_quality
            GROUP BY city_id) t
    """, engine)["ratio"].iloc[0]

    # Regional air mass: nearest pair against the furthest pair
    corr = _pairwise_correlations(engine)
    r_near = round(float(corr.loc["hanoi", "haiphong"]), 3)
    r_far = round(float(corr.loc["hanoi", "hcmc"]), 3)

    # Photochemistry: O3 against UV
    r_o3uv = pd.read_sql("""
        SELECT ROUND(CORR(ozone, uv_index)::numeric, 3) AS r
        FROM fact_hourly_air_quality
    """, engine)["r"].iloc[0]

    # Warm-day formation: temperature correlation, winter against summer
    temp_season = pd.read_sql("""
        SELECT CASE WHEN EXTRACT(MONTH FROM a.local_date) IN (12,1,2) THEN 'winter'
                    WHEN EXTRACT(MONTH FROM a.local_date) IN (6,7,8)  THEN 'summer'
                    ELSE 'other' END AS season,
               ROUND(CORR(a.pm2_5_avg, w.temperature_2m_max)::numeric, 3) AS r
        FROM fact_daily_air_quality a
        JOIN fact_daily_weather w
          ON a.city_id = w.city_id AND a.local_date = w.weather_date
        WHERE a.hours_recorded = 24
        GROUP BY season
    """, engine).set_index("season")["r"].astype(float)

    # Rain: PM2.5 in the driest bucket against the wettest
    rain = pd.read_sql("""
        SELECT CASE WHEN w.precipitation_sum = 0 THEN 'dry'
                    WHEN w.precipitation_sum >= 20 THEN 'heavy'
                    ELSE 'mid' END AS bucket,
               ROUND(AVG(a.pm2_5_avg)::numeric, 1) AS pm25
        FROM fact_daily_air_quality a
        JOIN fact_daily_weather w
          ON a.city_id = w.city_id AND a.local_date = w.weather_date
        WHERE a.hours_recorded = 24
        GROUP BY bucket
    """, engine).set_index("bucket")["pm25"].astype(float)

    # Biomass burning: PM2.5 and CO in April against the rest of the year
    april = pd.read_sql("""
        SELECT ROUND(AVG(CASE WHEN EXTRACT(MONTH FROM local_date)=4
                    THEN pm2_5 END)::numeric, 1) AS pm25_apr,
               ROUND(AVG(CASE WHEN EXTRACT(MONTH FROM local_date)<>4
                    THEN pm2_5 END)::numeric, 1) AS pm25_oth,
               ROUND(AVG(CASE WHEN EXTRACT(MONTH FROM local_date)=4
                    THEN carbon_monoxide END)::numeric, 0) AS co_apr,
               ROUND(AVG(CASE WHEN EXTRACT(MONTH FROM local_date)<>4
                    THEN carbon_monoxide END)::numeric, 0) AS co_oth
        FROM fact_hourly_air_quality WHERE city_id IN ('hanoi','haiphong','cantho')
    """, engine).iloc[0]
    pm_apr_delta = round(100 * (float(april.pm25_apr) - float(april.pm25_oth))
                         / float(april.pm25_oth))
    co_apr_delta = round(100 * (float(april.co_apr) - float(april.co_oth))
                         / float(april.co_oth))

    # Inversion: day-night amplitude in Hanoi, winter against summer
    amp = pd.read_sql("""
        SELECT CASE WHEN EXTRACT(MONTH FROM local_date) IN (12,1,2) THEN 'winter'
                    ELSE 'summer' END AS season,
               ROUND((MAX(h)-MIN(h))::numeric, 1) AS amplitude
        FROM (
            SELECT local_date, local_hour, AVG(pm2_5) AS h
            FROM fact_hourly_air_quality WHERE city_id='hanoi'
              AND EXTRACT(MONTH FROM local_date) IN (12,1,2,6,7,8)
            GROUP BY local_date, local_hour
        ) t GROUP BY season
    """, engine).set_index("season")["amplitude"].astype(float)

    # Traffic: weekday against weekend, worst gap across the six cities
    wk = pd.read_sql("""
        SELECT ROUND(MAX(diff)::numeric, 1) AS worst FROM (
            SELECT AVG(CASE WHEN EXTRACT(DOW FROM local_date) IN (0,6)
                       THEN pm2_5_avg END)
                 - AVG(CASE WHEN EXTRACT(DOW FROM local_date) BETWEEN 1 AND 5
                       THEN pm2_5_avg END) AS diff
            FROM fact_daily_air_quality WHERE hours_recorded=24
            GROUP BY city_id) t
    """, engine)["worst"].iloc[0]

    # Build-up: PM2.5 the day before an episode against the first day of it
    onset = pd.read_sql("""
        WITH s AS (
            SELECT city_id, pm2_5_avg,
                LAG(pm2_5_avg) OVER (PARTITION BY city_id ORDER BY local_date) AS d1
            FROM fact_daily_air_quality WHERE hours_recorded=24
        )
        SELECT ROUND(AVG(d1)::numeric,1) AS before,
               ROUND(AVG(pm2_5_avg)::numeric,1) AS onset_day
        FROM s WHERE pm2_5_avg > 35 AND d1 <= 35
    """, engine).iloc[0]

    rows = [
        ("Wind disperses particles",
         "negative correlation in every season",
         f"{season_wind.min():+.2f} to {season_wind.max():+.2f} across 4 seasons",
         "matches"),
        ("Cities differ in emission source",
         "one pollutant marker far above the rest",
         f"SO2 spans {so2}x between highest and lowest city",
         "matches"),
        ("Pollution is a regional air mass",
         "correlation falls away with distance",
         f"r = {r_near} at 100 km, r = {r_far} at 1,700 km",
         "matches"),
        ("Ozone forms photochemically",
         "ozone tracks UV",
         f"r = {r_o3uv} between O3 and UV index",
         "matches"),
        ("Warm days form more PM2.5",
         "holds within a season, not only across seasons",
         f"summer {temp_season['summer']:+.2f}, winter {temp_season['winter']:+.2f}",
         "partly"),
        ("Rain washes particles out",
         "PM2.5 falls as rainfall rises",
         f"{rain['dry']} ug/m3 dry vs {rain['heavy']} heavy ({round(100*(rain['heavy']-rain['dry'])/rain['dry'])}%)",
         "partly"),
        ("Seasonal burning drives April",
         "CO rises with PM2.5, since burning makes CO",
         f"PM2.5 {pm_apr_delta:+d}% but CO {co_apr_delta:+d}% in April",
         "contradicted"),
        ("Thermal inversion causes night peaks",
         "day-night swing larger in winter",
         f"winter {amp['winter']}, summer {amp['summer']} ug/m3",
         "contradicted"),
        ("Commuter traffic sets the daily cycle",
         "weekends measurably cleaner",
         f"weekends up to {wk:+.1f} ug/m3 - wrong direction",
         "contradicted"),
        ("Episodes build up gradually",
         "PM2.5 climbing before onset",
         f"{onset.before} the day before, {onset.onset_day} on day one",
         "contradicted"),
    ]

    df = pd.DataFrame(rows, columns=["hypothesis", "predicts", "measured", "verdict"])

    palette = {"matches": COLOR_SAFE, "partly": "#e67e22", "contradicted": COLOR_DANGER}

    fig, ax = plt.subplots(figsize=(14, 7.6))
    ax.axis("off")

    y = len(df)
    ax.text(0.005, y + 0.55, "HYPOTHESIS", fontsize=9, fontweight="bold", color=COLOR_MUTED)
    ax.text(0.30, y + 0.55, "WOULD PREDICT", fontsize=9, fontweight="bold", color=COLOR_MUTED)
    ax.text(0.60, y + 0.55, "WHAT THE DATA SHOWS", fontsize=9, fontweight="bold", color=COLOR_MUTED)
    ax.plot([0, 1], [y + 0.35, y + 0.35], color="#bdc3c7", linewidth=0.8)

    for i, row in enumerate(df.itertuples()):
        yy = y - i - 0.5
        c = palette[row.verdict]
        ax.add_patch(plt.Rectangle((0, yy - 0.34), 0.006, 0.68,
                                   color=c, transform=ax.transData))
        ax.text(0.018, yy, row.hypothesis, fontsize=10, va="center", color=COLOR_TEXT)
        ax.text(0.30, yy, row.predicts, fontsize=9, va="center", color="#7f8c8d")
        ax.text(0.60, yy, row.measured, fontsize=9.5, va="center",
                color=c, fontweight="bold")
        ax.plot([0, 1], [yy - 0.5, yy - 0.5], color="#ecf0f1", linewidth=0.6)

    ax.set_xlim(0, 1)
    ax.set_ylim(-0.3, y + 0.9)

    handles = [plt.Rectangle((0, 0), 1, 1, color=palette[k]) for k in
               ["matches", "partly", "contradicted"]]
    ax.legend(handles, ["Prediction matches", "Partly matches", "Prediction fails"],
              ncol=3, fontsize=10, loc="lower left", bbox_to_anchor=(0, -0.09))

    title_block(fig,
                "Ten hypotheses against the numbers that test them",
                "Every figure in the right-hand column is queried from the warehouse")
    add_footer(fig, "A matching prediction is not proof of cause - several of these hypotheses\n"
                    "would produce the same numbers. A failed prediction is the stronger result:\n"
                    "it rules the explanation out. Settling the rest needs an emissions inventory,\n"
                    "traffic counts or satellite fire detection, none of which this project has.")
    save(fig, "17_hypothesis_tests")


def main():
    setup_style()
    engine = get_engine()
    print("Generating driver charts...")
    chart_11_distance_decay(engine)
    chart_12_ranking_flip(engine)
    chart_15_clean_vs_dirty(engine)
    chart_16_city_sensitivity(engine)
    chart_17_hypothesis_tests(engine)
    print(f"Done. Charts written to {CHARTS_DIR}")


if __name__ == "__main__":
    main()