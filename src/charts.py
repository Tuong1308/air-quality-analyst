"""
Generate charts for README, following the story arc in docs/storytelling.md.

Run:  python -m src.charts
Output: charts/*.png
"""

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd

from src.config import BASE_DIR
from src.load import get_engine

CHARTS_DIR = BASE_DIR / "charts"

WHO_THRESHOLD = 15

COLOR_DANGER = "#c0392b"
COLOR_WARNING = "#e67e22"
COLOR_SAFE = "#27ae60"
COLOR_NEUTRAL = "#95a5a6"
COLOR_ACCENT = "#2980b9"
COLOR_TEXT = "#2c3e50"

CITY_LABELS = {
    "hanoi": "Hanoi",
    "haiphong": "Hai Phong",
    "danang": "Da Nang",
    "hcmc": "Ho Chi Minh City",
    "cantho": "Can Tho",
    "dalat": "Da Lat",
}

CITY_COLORS = {
    "hanoi": "#c0392b",
    "haiphong": "#e67e22",
    "danang": "#16a085",
    "hcmc": "#8e44ad",
    "cantho": "#2980b9",
    "dalat": "#27ae60",
}

FOOTER = "Source: Open-Meteo  |  6 Vietnamese cities  |  Feb 2025 - Aug 2026"


def setup_style():
    plt.rcParams.update({
        "figure.dpi": 110,
        "savefig.dpi": 150,
        "figure.constrained_layout.use": True,      # key fix for overlap
        "figure.constrained_layout.h_pad": 0.08,
        "figure.constrained_layout.w_pad": 0.08,
        "font.size": 10.5,
        "font.family": "DejaVu Sans",
        "axes.titlesize": 12,
        "axes.titleweight": "bold",
        "axes.titlecolor": COLOR_TEXT,
        "axes.labelsize": 10,
        "axes.labelcolor": COLOR_TEXT,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.edgecolor": "#bdc3c7",
        "axes.grid": True,
        "grid.alpha": 0.22,
        "grid.linestyle": "-",
        "grid.linewidth": 0.6,
        "xtick.color": COLOR_TEXT,
        "ytick.color": COLOR_TEXT,
        "legend.frameon": False,
    })


def title_block(fig, headline, subtitle=None, has_legend=False):
    """Centred, uppercase headline with a sentence-case subtitle below.

    constrained_layout cannot see manually placed fig.text, so the layout
    rect has to be shrunk first - otherwise the subtitle lands on top of
    the axes. Charts with a legend above the axes need extra room.

    The headline is uppercased for a poster-like look; the subtitle stays
    in sentence case because all-caps slows reading on longer strings.
    """
    top = 0.89 if subtitle else 0.93
    if has_legend:
        top -= 0.06
    fig.get_layout_engine().set(rect=(0, 0, 1, top))

    fig.text(0.5, 0.985, headline.upper(), ha="center", va="top",
             fontsize=15.5, fontweight="bold", color=COLOR_TEXT,
             linespacing=1.4)
    if subtitle:
        fig.text(0.5, 0.928, subtitle, ha="center", va="top",
                 fontsize=10.5, color="#7f8c8d", style="italic")


def add_footer(fig, note=None):
    text = FOOTER if note is None else f"{FOOTER}\n{note}"
    fig.text(0.012, -0.015, text, fontsize=7.5, color=COLOR_NEUTRAL,
             ha="left", va="top", linespacing=1.5)


def save(fig, name):
    CHARTS_DIR.mkdir(parents=True, exist_ok=True)
    path = CHARTS_DIR / f"{name}.png"
    fig.savefig(path, bbox_inches="tight", facecolor="white",
                pad_inches=0.35)
    plt.close(fig)
    print(f"  saved {path.name}")


# ============================================================
# CHART 1 [HOOK] - WHO exceedance by city
# ============================================================

def chart_01_who_exceedance(engine):
    sql = """
        SELECT city_id,
               COUNT(*) AS total_days,
               COUNT(*) FILTER (WHERE exceeds_who) AS days_exceeding,
               ROUND(100.0 * COUNT(*) FILTER (WHERE exceeds_who) / COUNT(*), 1)
                   AS pct_exceeding
        FROM fact_daily_air_quality
        WHERE hours_recorded = 24
        GROUP BY city_id
        ORDER BY pct_exceeding
    """
    df = pd.read_sql(sql, engine)
    df["city"] = df["city_id"].map(CITY_LABELS)

    colors = [
        COLOR_DANGER if p >= 85 else COLOR_WARNING if p >= 50 else COLOR_SAFE
        for p in df["pct_exceeding"]
    ]

    fig, ax = plt.subplots(figsize=(11, 5.5))
    bars = ax.barh(df["city"], df["pct_exceeding"], color=colors, height=0.6)

    # Labels sit inside the axes; xlim leaves room so nothing clips
    for bar, row in zip(bars, df.itertuples()):
        ax.text(row.pct_exceeding + 1.8, bar.get_y() + bar.get_height() / 2,
                f"{row.pct_exceeding}%",
                va="center", fontsize=11, fontweight="bold", color=COLOR_TEXT)
        ax.text(row.pct_exceeding + 11, bar.get_y() + bar.get_height() / 2,
                f"{row.days_exceeding} of {row.total_days} days",
                va="center", fontsize=9, color="#7f8c8d")

    ax.set_xlim(0, 138)
    ax.set_xlabel("Share of days above WHO guideline (%)", labelpad=8)
    ax.set_axisbelow(True)
    ax.grid(axis="y", visible=False)
    ax.tick_params(axis="y", length=0, labelsize=11)

    title_block(fig,
                "552 of 557 days above the WHO limit in Hanoi",
                "Four cities exceed it on more than 85% of days. Da Lat is the only one under 20%.")
    add_footer(fig, "WHO 24h guideline = 15 ug/m3.\n"
                    "Vietnam's national standard (QCVN 05:2023) allows 50 ug/m3.")
    save(fig, "01_who_exceedance")


# ============================================================
# CHART 2 [EXPLORE] - 19-month series
# ============================================================

def chart_02_monthly_series(engine):
    sql = """
        SELECT TO_CHAR(local_date, 'YYYY-MM') AS month,
               city_id,
               ROUND(AVG(pm2_5_avg), 1) AS pm25,
               COUNT(*) AS days
        FROM fact_daily_air_quality
        WHERE hours_recorded = 24
        GROUP BY month, city_id
        ORDER BY month
    """
    df = pd.read_sql(sql, engine)

    # Drop partial months so the line does not end on a misleading point
    complete = df[df["days"] >= 20]
    pivot = complete.pivot(index="month", columns="city_id", values="pm25")

    fig, ax = plt.subplots(figsize=(13, 6.5))
    x = range(len(pivot.index))

    # Shade April columns first so lines draw on top
    for month in ["2025-04", "2026-04"]:
        if month in pivot.index:
            i = list(pivot.index).index(month)
            ax.axvspan(i - 0.45, i + 0.45, color=COLOR_DANGER, alpha=0.07, zorder=0)

    for city_id in ["hanoi", "cantho", "hcmc", "haiphong", "danang", "dalat"]:
        if city_id not in pivot.columns:
            continue
        ax.plot(x, pivot[city_id], color=CITY_COLORS[city_id],
                linewidth=2.2, marker="o", markersize=4, zorder=3,
                label=CITY_LABELS[city_id])

    ax.axhline(WHO_THRESHOLD, color=COLOR_NEUTRAL, linestyle="--",
               linewidth=1.1, zorder=1)
    ax.text(len(x) - 0.4, WHO_THRESHOLD + 1.2, "WHO guideline (15)",
            fontsize=8.5, color=COLOR_NEUTRAL, ha="right")

    # Single annotation instead of two overlapping ones
    if "2025-04" in pivot.index:
        i = list(pivot.index).index("2025-04")
        ax.annotate("April spike - repeats in 2026",
                    xy=(i, pivot.loc["2025-04", "hanoi"]),
                    xytext=(i + 1.3, pivot.loc["2025-04", "hanoi"] + 8),
                    fontsize=9, color=COLOR_DANGER, fontweight="bold",
                    arrowprops=dict(arrowstyle="->", color=COLOR_DANGER,
                                    lw=1.2, connectionstyle="arc3,rad=-0.2"))

    ax.set_xticks(list(x))
    ax.set_xticklabels(pivot.index, rotation=45, ha="right", fontsize=9)
    ax.set_ylabel("Monthly average PM2.5 (ug/m3)", labelpad=8)
    ax.set_ylim(0, 80)
    ax.set_xlim(-0.6, len(x) - 0.4)
    ax.legend(ncol=3, fontsize=9.5, loc="upper center",
              bbox_to_anchor=(0.5, 1.09), columnspacing=1.6)

    title_block(fig,
                "April spikes repeat in both years",
                "Hanoi hits 69 then 67 ug/m3 two Aprils running - while HCMC dips to its yearly low",
                has_legend=True)
    add_footer(fig, "Months with fewer than 20 complete days excluded (Aug 2026 had 13).")
    save(fig, "02_monthly_series")


# ============================================================
# CHART 3 [TWIST] - Rain effect
# ============================================================

def chart_03_rain_effect(engine):
    sql = """
        WITH daily AS (
            SELECT a.city_id, a.local_date, a.pm2_5_avg, w.precipitation_sum,
                   LAG(a.pm2_5_avg) OVER (PARTITION BY a.city_id
                                          ORDER BY a.local_date) AS pm25_prev
            FROM fact_daily_air_quality a
            JOIN fact_daily_weather w
              ON a.city_id = w.city_id AND a.local_date = w.weather_date
            WHERE a.hours_recorded = 24
        )
        SELECT
            CASE WHEN precipitation_sum = 0  THEN 0
                 WHEN precipitation_sum < 5  THEN 1
                 WHEN precipitation_sum < 20 THEN 2
                 ELSE                             3 END AS bucket,
            COUNT(*) AS total_days,
            ROUND(AVG(pm2_5_avg), 2) AS pm25_avg,
            ROUND(AVG(pm2_5_avg - pm25_prev), 2) AS change_vs_prev
        FROM daily
        WHERE pm25_prev IS NOT NULL
        GROUP BY bucket
        ORDER BY bucket
    """
    df = pd.read_sql(sql, engine)
    df["label"] = ["No rain", "Light\n<5mm", "Moderate\n5-20mm", "Heavy\n>20mm"]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5.8))

    # --- Left panel: absolute level
    bars1 = ax1.bar(df["label"], df["pm25_avg"], color=COLOR_ACCENT, width=0.58)
    for bar, row in zip(bars1, df.itertuples()):
        ax1.text(bar.get_x() + bar.get_width() / 2, row.pm25_avg + 0.8,
                 f"{row.pm25_avg}", ha="center", fontsize=11,
                 fontweight="bold", color=COLOR_TEXT)
        ax1.text(bar.get_x() + bar.get_width() / 2, 1.5,
                 f"n={row.total_days}", ha="center", fontsize=8.5, color="white")

    ax1.set_ylim(0, 38)
    ax1.set_ylabel("Average PM2.5 (ug/m3)", labelpad=8)
    ax1.set_title("Level drops 20% from dry to heavy rain",
                  loc="left", fontsize=11, pad=10)

    # --- Right panel: day-over-day change (fairer: each city vs itself)
    colors2 = [COLOR_DANGER if v > 0 else COLOR_SAFE for v in df["change_vs_prev"]]
    bars2 = ax2.bar(df["label"], df["change_vs_prev"], color=colors2, width=0.58)
    for bar, row in zip(bars2, df.itertuples()):
        va = "bottom" if row.change_vs_prev > 0 else "top"
        pad = 0.08 if row.change_vs_prev > 0 else -0.08
        ax2.text(bar.get_x() + bar.get_width() / 2, row.change_vs_prev + pad,
                 f"{row.change_vs_prev:+.2f}", ha="center", va=va,
                 fontsize=11, fontweight="bold", color=COLOR_TEXT)

    ax2.axhline(0, color="#34495e", linewidth=1)
    ax2.set_ylim(-2.4, 2.4)
    ax2.set_ylabel("Change vs previous day (ug/m3)", labelpad=8)
    ax2.set_title("Dry days push it up; heavy rain pulls it down",
                  loc="left", fontsize=11, pad=10)

    title_block(fig,
                "Correlation said r = -0.09.  Bucketing said otherwise.",
                "Dry days gain +1.57 ug/m3; heavy-rain days lose -1.71. Every bucket declines in order.")
    add_footer(fig, "46% of days fall in the light-rain bucket,\n"
                    "which dilutes the linear coefficient.")
    save(fig, "03_rain_effect")


# ============================================================
# CHART 4 [EXPLAIN] - Weather correlation
# ============================================================

def chart_04_weather_correlation(engine):
    sql = """
        SELECT
            ROUND(CORR(a.pm2_5_avg, w.windspeed_10m_max)::numeric, 3)  AS "Wind speed",
            ROUND(CORR(a.pm2_5_avg, w.temperature_2m_max)::numeric, 3) AS "Max temperature",
            ROUND(CORR(a.pm2_5_avg, w.precipitation_sum)::numeric, 3)  AS "Precipitation"
        FROM fact_daily_air_quality a
        JOIN fact_daily_weather w
          ON a.city_id = w.city_id AND a.local_date = w.weather_date
        WHERE a.hours_recorded = 24
    """
    wide = pd.read_sql(sql, engine)
    df = wide.melt(var_name="factor", value_name="correlation")
    df["correlation"] = df["correlation"].astype(float)
    df = df.iloc[df["correlation"].abs().argsort()]

    colors = [COLOR_SAFE if v < 0 else COLOR_DANGER for v in df["correlation"]]

    fig, ax = plt.subplots(figsize=(10, 4.6))
    bars = ax.barh(df["factor"], df["correlation"], color=colors, height=0.5)

    for bar, row in zip(bars, df.itertuples()):
        ha = "left" if row.correlation > 0 else "right"
        pad = 0.014 if row.correlation > 0 else -0.014
        ax.text(row.correlation + pad, bar.get_y() + bar.get_height() / 2,
                f"{row.correlation:+.3f}", va="center", ha=ha,
                fontsize=11, fontweight="bold", color=COLOR_TEXT)

    ax.axvline(0, color="#34495e", linewidth=1)
    ax.set_xlim(-0.48, 0.38)
    ax.set_xlabel("Correlation with daily PM2.5", labelpad=8)
    ax.grid(axis="y", visible=False)
    ax.tick_params(axis="y", length=0, labelsize=10.5)

    title_block(fig,
                "Wind clears the air 3.7x better than rain",
                "Dispersion beats washout: r = -0.344 for wind against -0.094 for rainfall")
    add_footer(fig, "Temperature (+0.233) holds up when split by season - see the seasonal chart.\n"
                    "Wind is negative in all four seasons; rain only bites in autumn.")
    save(fig, "04_weather_correlation")


# ============================================================
# CHART 5 [EXPLAIN] - Pollution fingerprint
# ============================================================

def chart_05_pollution_fingerprint(engine):
    sql = """
        SELECT city_id,
               ROUND(AVG(pm2_5), 1)            AS "PM2.5",
               ROUND(AVG(nitrogen_dioxide), 1) AS "NO2",
               ROUND(AVG(sulphur_dioxide), 1)  AS "SO2",
               ROUND(AVG(carbon_monoxide), 1)  AS "CO"
        FROM fact_hourly_air_quality
        GROUP BY city_id
    """
    df = pd.read_sql(sql, engine).set_index("city_id")
    order = ["hanoi", "hcmc", "cantho", "haiphong", "danang", "dalat"]
    df = df.loc[order]

    # Scale each pollutant to its own maximum (city with highest value = 100).
    # Two alternatives were tested and rejected:
    #   - dividing by PM2.5: small denominators (Da Lat, 10.4) inflate ratios
    #   - min-max scaling:   forces the lowest city to 0 on every pollutant,
    #                        so Da Lat's bars vanish entirely from the chart
    scaled = df.apply(lambda c: 100 * c / c.max())

    pollutants = list(df.columns)
    width = 0.19
    x = range(len(df))
    palette = {"PM2.5": "#34495e", "NO2": "#8e44ad",
               "SO2": "#c0392b", "CO": "#e67e22"}

    fig, ax = plt.subplots(figsize=(13, 6))

    for i, pol in enumerate(pollutants):
        positions = [xi + (i - 1.5) * width for xi in x]
        ax.bar(positions, scaled[pol], width=width, label=pol, color=palette[pol])

    ax.set_xticks(list(x))
    ax.set_xticklabels([CITY_LABELS[c] for c in df.index], fontsize=10.5)
    ax.set_ylabel("Relative level (0-100, scaled per pollutant)", labelpad=8)
    ax.set_ylim(0, 126)
    ax.legend(ncol=4, fontsize=10, loc="upper center",
              bbox_to_anchor=(0.5, 1.09), columnspacing=2)

    # Annotations placed in clear space above the bars
    ax.annotate("SO2 = coal burning\n12.6x Da Lat's level",
                xy=(0 + 0.5 * width, scaled.loc["hanoi", "SO2"]),
                xytext=(0.55, 112),
                fontsize=9, color=COLOR_DANGER, fontweight="bold",
                ha="center",
                arrowprops=dict(arrowstyle="->", color=COLOR_DANGER, lw=1.2,
                                connectionstyle="arc3,rad=0.25"))
    ax.annotate("NO2 + CO = traffic",
                xy=(1 - 0.5 * width, scaled.loc["hcmc", "NO2"]),
                xytext=(2.1, 112),
                fontsize=9, color="#8e44ad", fontweight="bold",
                ha="center",
                arrowprops=dict(arrowstyle="->", color="#8e44ad", lw=1.2,
                                connectionstyle="arc3,rad=-0.25"))

    title_block(fig,
                "Hanoi burns coal.  Ho Chi Minh City burns fuel.",
                "Hanoi's SO2 runs 12.6x Da Lat's. HCMC tops NO2 and CO despite lower PM2.5.",
                has_legend=True)
    add_footer(fig, "Each pollutant scaled independently - absolute values differ by\n"
                    "orders of magnitude (CO ~800 against SO2 ~26 ug/m3).")
    save(fig, "05_pollution_fingerprint")


# ============================================================
# CHART 6 [ACTION] - Month heatmap
# ============================================================

def chart_06_month_heatmap(engine):
    sql = """
        SELECT city_id,
               EXTRACT(MONTH FROM local_date)::int AS month,
               ROUND(100.0 * COUNT(*) FILTER (WHERE pm2_5_avg > 35) / COUNT(*), 1)
                   AS pct_bad,
               COUNT(DISTINCT EXTRACT(YEAR FROM local_date)) AS n_years
        FROM fact_daily_air_quality
        WHERE hours_recorded = 24
        GROUP BY city_id, month
        ORDER BY city_id, month
    """
    df = pd.read_sql(sql, engine)

    order = ["hanoi", "cantho", "hcmc", "haiphong", "danang", "dalat"]
    pivot = df.pivot(index="city_id", columns="month", values="pct_bad").loc[order]
    years = df.pivot(index="city_id", columns="month", values="n_years").loc[order]

    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    labels = [f"{m}*" if years.iloc[0].get(i + 1, 2) == 1 else m
              for i, m in enumerate(months)]

    fig, ax = plt.subplots(figsize=(13, 5))
    im = ax.imshow(pivot.values, cmap="YlOrRd", aspect="auto", vmin=0, vmax=100)

    ax.set_xticks(range(12))
    ax.set_xticklabels(labels, fontsize=10)
    ax.set_yticks(range(len(order)))
    ax.set_yticklabels([CITY_LABELS[c] for c in order], fontsize=10.5)
    ax.grid(visible=False)
    ax.tick_params(length=0)

    for r in range(pivot.shape[0]):
        for c in range(pivot.shape[1]):
            val = pivot.values[r, c]
            if pd.isna(val):
                continue
            ax.text(c, r, f"{val:.0f}", ha="center", va="center",
                    fontsize=9.5, fontweight="bold" if val > 70 else "normal",
                    color="white" if val > 55 else "#2c3e50")

    # Outline the April column - the story's focal point
    ax.add_patch(plt.Rectangle((2.5, -0.5), 1, len(order),
                               fill=False, edgecolor="#2c3e50",
                               linewidth=2, zorder=5))

    cbar = fig.colorbar(im, ax=ax, pad=0.012, fraction=0.03)
    cbar.set_label("Share of days above 35 ug/m3 (%)", fontsize=9.5, labelpad=8)
    cbar.ax.tick_params(labelsize=9)

    title_block(fig,
                "Avoid April everywhere - except Ho Chi Minh City",
                "Hanoi: 98% bad days in April. HCMC: 2% in April, but 87% in June.")
    add_footer(fig, "* Months backed by one year of data only (~30 days).\n"
                    "Feb-Aug have two years (~60 days).")
    save(fig, "06_month_heatmap")


# ============================================================
# CHART 7 [EXTRA] - 24-hour rhythm
# ============================================================

def chart_07_daily_rhythm(engine):
    sql = """
        SELECT local_hour,
               ROUND(AVG(pm2_5), 1)            AS pm25,
               ROUND(AVG(nitrogen_dioxide), 1) AS no2,
               ROUND(AVG(ozone), 1)            AS o3
        FROM fact_hourly_air_quality
        GROUP BY local_hour
        ORDER BY local_hour
    """
    df = pd.read_sql(sql, engine)

    fig, ax = plt.subplots(figsize=(12, 6))

    for start, end in [(7, 8), (17, 18)]:
        ax.axvspan(start, end, color=COLOR_NEUTRAL, alpha=0.16, zorder=0)
    ax.text(7.5, 41.5, "rush hour", ha="center", fontsize=8.5,
            color="#7f8c8d", style="italic")
    ax.text(17.5, 41.5, "rush hour", ha="center", fontsize=8.5,
            color="#7f8c8d", style="italic")

    l1, = ax.plot(df["local_hour"], df["pm25"], color=COLOR_DANGER,
                  linewidth=2.6, marker="o", markersize=4.5,
                  zorder=3, label="PM2.5")
    l2, = ax.plot(df["local_hour"], df["no2"], color="#8e44ad",
                  linewidth=1.9, marker="s", markersize=3.5,
                  zorder=3, label="NO2")
    ax.set_ylabel("PM2.5 / NO2 (ug/m3)", labelpad=8)
    ax.set_ylim(0, 45)

    # O3 spans 40-130 - a secondary axis keeps the PM2.5 curve readable
    ax2 = ax.twinx()
    l3, = ax2.plot(df["local_hour"], df["o3"], color=COLOR_ACCENT,
                   linewidth=1.9, linestyle="--", marker="^", markersize=3.5,
                   zorder=3, label="O3 (right axis)")
    ax2.set_ylabel("O3 (ug/m3)", color=COLOR_ACCENT, labelpad=8)
    ax2.tick_params(axis="y", labelcolor=COLOR_ACCENT)
    ax2.set_ylim(0, 150)
    ax2.grid(visible=False)
    ax2.spines["right"].set_visible(True)
    ax2.spines["top"].set_visible(False)

    ax.set_xlabel("Hour of day (local time, UTC+7)", labelpad=8)
    ax.set_xticks(range(0, 24, 2))
    ax.set_xlim(-0.5, 23.5)
    ax.legend(handles=[l1, l2, l3], ncol=3, fontsize=10,
              loc="upper center", bbox_to_anchor=(0.5, 1.09))

    title_block(fig,
                "Peaks at 6am and 10pm - not during rush hour",
                "Both rush hours (shaded) land where PM2.5 is already falling",
                has_legend=True)
    add_footer(fig, "NO2 and O3 run in antiphase - the classic photochemical cycle.\n"
                    "The mechanism behind the overnight peak is not settled here: daytime convective\n"
                    "mixing fits the midday trough, but thermal inversion does not - it would predict\n"
                    "a larger winter amplitude, and summer is larger.")
    save(fig, "07_daily_rhythm")


# ============================================================
# CHART 8 [EXTRA] - Sustained episodes
# ============================================================

def chart_08_episodes(engine):
    sql = """
        WITH flagged AS (
            SELECT city_id, local_date, pm2_5_avg,
                   local_date - (ROW_NUMBER() OVER (PARTITION BY city_id
                                 ORDER BY local_date))::int AS grp
            FROM fact_daily_air_quality
            WHERE hours_recorded = 24 AND pm2_5_avg > 35
        )
        SELECT city_id,
               MIN(local_date) AS start_date,
               COUNT(*)        AS consecutive_days
        FROM flagged
        GROUP BY city_id, grp
        HAVING COUNT(*) >= 3
        ORDER BY consecutive_days DESC
        LIMIT 10
    """
    df = pd.read_sql(sql, engine).sort_values("consecutive_days")
    df["label"] = (df["city_id"].map(CITY_LABELS) + "   "
                   + pd.to_datetime(df["start_date"]).dt.strftime("%b %Y"))

    fig, ax = plt.subplots(figsize=(11, 6))
    colors = [CITY_COLORS[c] for c in df["city_id"]]
    bars = ax.barh(df["label"], df["consecutive_days"], color=colors, height=0.6)

    for bar, row in zip(bars, df.itertuples()):
        ax.text(row.consecutive_days + 0.8, bar.get_y() + bar.get_height() / 2,
                f"{row.consecutive_days} days", va="center",
                fontsize=10, fontweight="bold", color=COLOR_TEXT)

    ax.set_xlim(0, max(df["consecutive_days"]) * 1.2)
    ax.set_xlabel("Consecutive days above 35 ug/m3", labelpad=8)
    ax.grid(axis="y", visible=False)
    ax.tick_params(axis="y", length=0, labelsize=10)

    title_block(fig,
                "Hanoi: 400 of 557 days inside a pollution episode",
                "45 separate episodes, 9 days each on average. Da Lat recorded none.")
    add_footer(fig, "Episode = 3 or more consecutive days above 35 ug/m3.\n"
                    "Da Lat recorded none in 18 months.")
    save(fig, "08_episodes")


# ============================================================

def main():
    setup_style()
    engine = get_engine()

    print("Generating charts...")
    chart_01_who_exceedance(engine)
    chart_02_monthly_series(engine)
    chart_03_rain_effect(engine)
    chart_04_weather_correlation(engine)
    chart_05_pollution_fingerprint(engine)
    chart_06_month_heatmap(engine)
    chart_07_daily_rhythm(engine)
    chart_08_episodes(engine)
    print(f"Done. Charts written to {CHARTS_DIR}")


if __name__ == "__main__":
    main()