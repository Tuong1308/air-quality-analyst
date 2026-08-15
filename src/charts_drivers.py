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


# Straight-line distances between city pairs, km. Hand-entered because the
# warehouse stores coordinates but no distance calculation.
PAIR_DISTANCE = {
    ("hanoi", "haiphong"): 100,
    ("danang", "dalat"): 600,
    ("hcmc", "cantho"): 170,
    ("hanoi", "danang"): 760,
    ("danang", "hcmc"): 850,
    ("hanoi", "cantho"): 1700,
    ("hanoi", "hcmc"): 1700,
    ("dalat", "hcmc"): 300,
}



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


# ============================================================
# CHART 11 - Correlation against distance
# Bears on: is pollution a national phenomenon or a regional one?
# ============================================================

def chart_11_distance_decay(engine):
    corr = _pairwise_correlations(engine)

    rows = []
    for (a, b), km in PAIR_DISTANCE.items():
        rows.append({
            "pair": f"{CITY_LABELS[a]} - {CITY_LABELS[b]}",
            "km": km,
            "r": round(float(corr.loc[a, b]), 3),
            "same_region": (a, b) in [("hanoi", "haiphong"), ("hcmc", "cantho")],
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

    title_block(fig,
                "Pollution correlation dies with distance",
                "Hanoi and Ho Chi Minh City move independently: r = -0.008 across 1,700 km")
    add_footer(fig, "Two pairs break the trend. Ho Chi Minh City and Can Tho are 170 km apart\n"
                    "yet correlate at just 0.260, against 0.691 for Hanoi-Hai Phong at 100 km.\n"
                    "Da Lat runs negative to Ho Chi Minh City across 300 km - it sits 1,500 m up.")
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

    title_block(fig,
                "Dirty days are still, dry and cloudless",
                "Averaged over ~330 days in each group, pooled across all six cities")
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
    add_footer(fig, "Wind is the one factor that points the same way everywhere, though its strength\n"
                    "ranges from -0.51 in Da Lat to -0.16 in coastal Da Nang. Ho Chi Minh City is the\n"
                    "outlier: there, rain arrives WITH higher PM2.5, not lower - a pattern that fits a\n"
                    "monsoon-season effect rather than rainfall washing particles out.")
    save(fig, "16_city_sensitivity")


# ============================================================
# CHART 17 - Candidate drivers, graded by evidence
# The summary chart: what the data supports, and how firmly
# ============================================================

def chart_17_driver_evidence(engine):
    # Strength scores are assigned by hand from the query log, not computed -
    # they encode a judgement about how much weight each line of evidence
    # carries, which is not something the warehouse can answer.
    drivers = [
        ("Wind dispersion", 0.90, "supported",
         "negative in all 4 seasons and all 6 cities; dirty days 35% calmer"),
        ("Emission source mix", 0.75, "supported",
         "SO2 12.6x higher in Hanoi; NO2 exceeded 65% of hours in HCMC"),
        ("Regional air mass", 0.70, "supported",
         "Hanoi-Hai Phong r=0.69 at 100 km; Hanoi-HCMC r=0.00 at 1,700 km"),
        ("Photochemistry", 0.65, "supported",
         "O3 tracks UV at r=0.52; NO2 and O3 in antiphase"),
        ("Warm-day secondary formation", 0.50, "partial",
         "holds within season (+0.41 summer) but absent in winter"),
        ("Dry-season accumulation", 0.45, "partial",
         "April is driest and dirtiest - but HCMC is dry and clean then"),
        ("Rain washout", 0.35, "partial",
         "20% drop across rain buckets, yet only autumn shows it clearly"),
        ("Seasonal biomass burning", 0.20, "against",
         "CO falls 10-13% in April while PM2.5 rises 24-52%"),
        ("Thermal inversion", 0.15, "against",
         "predicts a larger winter amplitude; summer is larger"),
        ("Traffic driving the daily cycle", 0.10, "against",
         "peaks miss rush hour; weekends equal or worse"),
        ("Gradual build-up before episodes", 0.08, "against",
         "PM2.5 falls for 3 days, then jumps 48% overnight"),
    ]

    df = pd.DataFrame(drivers, columns=["driver", "score", "verdict", "evidence"])
    df = df.sort_values("score")

    palette = {"supported": COLOR_SAFE, "partial": "#e67e22", "against": COLOR_MUTED}
    colors = [palette[v] for v in df["verdict"]]

    fig, ax = plt.subplots(figsize=(13.5, 8))
    bars = ax.barh(range(len(df)), df["score"], color=colors, height=0.66)

    for i, row in enumerate(df.itertuples()):
        ax.text(row.score + 0.015, i + 0.16, row.driver,
                va="center", fontsize=10.5, fontweight="bold", color=COLOR_TEXT)
        ax.text(row.score + 0.015, i - 0.2, row.evidence,
                va="center", fontsize=8.5, color="#7f8c8d")

    ax.set_yticks([])
    ax.set_xlim(0, 1.02)
    ax.set_xticks([0, 0.25, 0.5, 0.75, 1.0])
    ax.set_xticklabels(["contradicted", "weak", "mixed", "solid", "strong"], fontsize=9.5)
    ax.set_xlabel("Weight of evidence in this dataset", labelpad=8)
    ax.grid(axis="y", visible=False)
    ax.tick_params(axis="y", length=0)

    handles = [plt.Rectangle((0, 0), 1, 1, color=palette[k]) for k in
               ["supported", "partial", "against"]]
    ax.legend(handles, ["Supported by the data", "Partly supported",
                        "Contradicted by the data"],
              ncol=3, fontsize=10, loc="lower right", bbox_to_anchor=(1.0, -0.16))

    title_block(fig,
                "Candidate drivers, graded by evidence",
                "None of these is established as a cause - this ranks how well each fits the data")
    add_footer(fig, "Scores are a judgement call, not a computed statistic: they weigh how consistent\n"
                    "each pattern is across cities, seasons and pollutants. Settling any of them would\n"
                    "need data this project does not have - an emissions inventory, traffic counts,\n"
                    "or satellite fire detection.")
    save(fig, "17_driver_evidence")


def main():
    setup_style()
    engine = get_engine()
    print("Generating driver charts...")
    chart_11_distance_decay(engine)
    chart_12_ranking_flip(engine)
    chart_15_clean_vs_dirty(engine)
    chart_16_city_sensitivity(engine)
    chart_17_driver_evidence(engine)
    print(f"Done. Charts written to {CHARTS_DIR}")


if __name__ == "__main__":
    main()