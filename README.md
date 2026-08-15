# Vietnam Air Quality ETL Pipeline (Analytics)

An hourly ETL pipeline that collects air quality and weather data for six
Vietnamese cities, loads it into PostgreSQL, and uses it to test which common
explanations for the pollution hold up — and which do not.

<p align="center">
  <b>80,328 hourly rows</b> · <b>6 cities</b> · <b>18 months</b> · <b>99.4% complete</b> · <b>0 validation failures</b>
</p>

---

## Architecture

```mermaid
flowchart TD
    A["Open-Meteo APIs<br/>Air Quality · hourly &nbsp;&nbsp; Weather · daily"]
    B["BRONZE — raw JSON on disk<br/>data/raw/{date}/{city}.json"]
    C["SILVER — fact_hourly_air_quality<br/>80,328 rows · 24 per city-day"]
    D["GOLD — daily air quality + weather<br/>3,360 + 3,353 rows"]
    E["analysis.sql · charts.py · charts_drivers.py"]

    A ==>|"extract.py — retry with backoff"| B
    B ==>|"transform.py — UTC to ICT, validate"| C
    C ==>|"aggregate.py — roll up to daily"| D
    D ==> E

    classDef src  fill:#E6F1FB,stroke:#185FA5,stroke-width:2px,color:#042C53
    classDef brz  fill:#FAECE7,stroke:#993C1D,stroke-width:2px,color:#4A1B0C
    classDef slv  fill:#F1EFE8,stroke:#5F5E5A,stroke-width:2px,color:#2C2C2A
    classDef gld  fill:#FAEEDA,stroke:#854F0B,stroke-width:2px,color:#412402
    classDef out  fill:#E1F5EE,stroke:#0F6E56,stroke-width:2px,color:#04342C

    class A src
    class B brz
    class C slv
    class D gld
    class E out
```

Raw JSON stays on disk so transforms can be re-run without re-fetching. The
three storage tiers follow the bronze/silver/gold pattern used by modern
lakehouses.

| Property | How |
|---|---|
| Idempotent | `INSERT ... ON CONFLICT DO UPDATE` — verified by running the same day three times and counting rows |
| Fault-tolerant | `tenacity` retries transient network errors; per-city `try/except` keeps one failure from costing the other five |
| Observable | Timestamped logs to `logs/etl_{date}.log`, non-zero exit code on failure |
| Tested | 9 unit tests on timezone conversion and validation rules — no network, no database, 0.8s |

---

## The data

Two Open-Meteo APIs, no key required. Cities span all three regions:
**Hanoi, Hai Phong** (North) · **Da Nang, Da Lat** (Central) ·
**Ho Chi Minh City, Can Tho** (South).

| Metric | What it is | What high values point to | WHO 24h limit |
|---|---|---|---|
| **PM2.5** | Fine particles ≤2.5 µm — small enough to cross into the bloodstream | Combustion of any kind; the headline health metric | **15 µg/m³** |
| **PM10** | Coarse particles ≤10 µm — **includes PM2.5 by definition** | Road dust, construction. A PM2.5/PM10 ratio near 1 means combustion, not mechanical dust | 45 µg/m³ |
| **NO₂** | Nitrogen dioxide from high-temperature combustion | **Traffic** — the most reliable vehicle marker | 25 µg/m³ |
| **SO₂** | Sulphur dioxide from sulphur-bearing fuel | **Coal burning / heavy industry** — modern vehicles emit almost none | 40 µg/m³ |
| **CO** | Carbon monoxide from incomplete combustion | Motorbikes, charcoal stoves. Pairs with NO₂ as a traffic signal | 4,000 µg/m³ |
| **O₃** | **Ground-level** ozone — a pollutant, not the protective ozone layer | Not emitted directly; forms when sunlight breaks down NO₂ | 100 µg/m³ |
| **UV** | Solar UV intensity — not a pollutant | The driver behind ozone formation | — |

Weather: `precipitation_sum` (mm), `windspeed_10m_max` (km/h),
`temperature_2m_max/min` (°C).

> **Which standard?** Every exceedance figure below uses WHO's **15 µg/m³**.
> Vietnam's national standard (QCVN 05:2023) allows **50 µg/m³** — the same days
> look very different under each. The stricter threshold is used deliberately and
> stated throughout.

---

# Part 1 — What the air is like

## Hanoi exceeded the WHO guideline on 552 of 557 days

![WHO exceedance by city](charts/01_who_exceedance.png)

Four of six cities are above the guideline on more than 85% of days.

Da Lat is the exception at 17.4%, and it recorded **no sustained pollution
episode at all** in eighteen months — a useful reference point for what low
looks like in this region.

It is not proof that the other five could reach the same level, though. Da Lat
sits on a plateau with little industry and a different climate, so its cleanliness
is confounded with its geography. What it does establish is that the readings are
not a measurement artefact: the same pipeline, the same API and the same
thresholds produce very different numbers for a city with different surroundings.

## Patterns repeat, which makes them patterns rather than events

![Monthly PM2.5 series](charts/02_monthly_series.png)

Plotting all nineteen months in sequence — rather than averaging by calendar
month — shows Hanoi peaking at 68.9 then 67.0 µg/m³ two Aprils running. A single
spike could be an accident; the same spike in consecutive years is a pattern.
Months with fewer than 20 complete days are dropped, so the line never ends on a
half-measured month.

Ho Chi Minh City runs in antiphase: April is its *cleanest* month. Hold on to
that contrast — it comes back.

---

# Part 2 — Three ways the obvious answer is wrong

The intuitive reading of Part 1 is that Vietnam has *an* air pollution problem,
that PM2.5 measures it, and that one set of causes explains it. Each of those
three framings breaks down in a different way — not because the pieces are wrong,
but because each one is really several things wearing a single label.

## It is not one problem — it is at least three

![Correlation against distance](charts/11_distance_decay.png)

Hanoi and Ho Chi Minh City correlate at **−0.008**. A bad day in one says
nothing about the other.

Hanoi and Hai Phong, 100 km apart, correlate at 0.691 — they share an air mass.
But Ho Chi Minh City and Can Tho, only 170 km apart, manage just 0.260, and Da
Lat correlates *negatively* with Ho Chi Minh City despite a 300 km gap — it sits
on a plateau, apart from the lowland air.

Three systems that rise and fall independently. That does not make national
measures pointless — a fuel standard would reach every city regardless of whether
their daily readings move together. What it does rule out is treating the country
as one air shed: an alert issued for Hanoi carries no information about Ho Chi
Minh City, and a source identified in one region cannot be assumed to operate in
another.

## It is not one pollutant — the ranking flips

![PM2.5 ranking against ozone ranking](charts/12_ranking_flip.png)

Da Nang ranks **5th of 6 on PM2.5** and **1st of 6 on ozone**, with 53.9% of
hours above the WHO limit — twice Hanoi's share.

Ozone is not emitted directly — it forms when sunlight breaks down NO₂, and
ozone tracks UV at r = 0.516 across the whole dataset. Less airborne dust means
more UV reaching ground level, which offers a plausible route from "low PM2.5"
to "high ozone".

The direct link between the two is real but small: PM2.5 against ozone gives
r = −0.128 over 80,472 hourly readings (t = −36.7, so comfortably distinguishable
from zero) — yet that accounts for under 2% of the variance. Treat this as a
mechanism the data is consistent with, not one it establishes.

A "cleanest cities in Vietnam" ranking built on PM2.5 would put Da Nang near the
top and miss its actual problem entirely.

## It is not one cause — the two big cities differ

![Pollution fingerprint by city](charts/05_pollution_fingerprint.png)

SO₂ is a coal marker: modern vehicles run on desulphurised fuel and emit almost
none of it. Hanoi's SO₂ averages **12.6 times Da Lat's level**, and crosses the WHO limit in
one hour out of eight.

Ho Chi Minh City instead leads on NO₂ and CO — the traffic pair — exceeding the
NO₂ limit in **65% of hours** despite ranking only third on PM2.5.

Same symptom, different causes, and therefore different remedies. This only
became visible because the pipeline collects six pollutants rather than PM2.5
alone.

---

# Part 3 — What travels with pollution

Emission sources set the baseline. Weather decides what happens to those
emissions once they are in the air — and it turns out to leave a much clearer
fingerprint than the sources themselves.

## A city's own dirty days are stiller and drier

![Cleanest days against dirtiest days](charts/15_clean_vs_dirty.png)

Each city's dirtiest and cleanest deciles — about 56 days each — compared against
one another, then averaged across the six. Cutting the deciles within each city
rather than across the pooled 3,341 days keeps the comparison about days rather
than places.

On a city's own worst days, wind is 35% weaker, rainfall 64% lower, and the
day-night temperature range 50% wider.

The direction is not settled, though. Calm dry weather plausibly lets particles
accumulate — but heavy particle loading also suppresses cloud formation, which
would widen the temperature range on its own. Both readings fit these numbers.

## But the same weather does different things in different cities

![Weather sensitivity per city](charts/16_city_sensitivity.png)

Wind is the one factor pointing the same way everywhere — negative in all four
seasons and all six cities — though its strength ranges from −0.51 in Da Lat to
−0.16 in coastal Da Nang. It is the only factor in this dataset that behaves
consistently.

Ho Chi Minh City reverses sign on three of the four. Rain there arrives *with*
higher PM2.5, not lower, which fits monsoon seasonality better than it fits
rainfall washing particles out.

## Rain helps, but less than either the chart or the coefficient suggests

Rain is the clearest case of a signal two different summaries each get wrong, in
opposite directions.

**The coefficient understates it.** Pearson correlation between rainfall and
PM2.5 is only **−0.094**, which reads as "no relationship". Bucketing by
intensity shows every bucket declining in order, with dry days *gaining* +1.57
µg/m³ against the previous day and heavy-rain days *losing* −1.71. The
coefficient is low because 46% of days fall into the light-rain bucket, where
the effect is near zero — and it is a real signal, not noise (t = −5.4 over
3,341 days).

**The buckets overstate it.** Rainy days are also windier (r = +0.137), so part
of what looks like rain clearing the air is wind doing it. Holding wind constant
cuts the rain coefficient from −0.094 to −0.050 — roughly half. The 20% gap
between dry and heavy-rain days is what a resident would experience; only about
half of it belongs to the rain.

**A weak correlation means the relationship is not linear, not that it does not
exist** — and a clear gap between groups does not mean the labelled factor
caused it. ([chart](charts/03_rain_effect.png))

---

# Part 4 — Testing five obvious explanations

This is where the analysis earns its keep. Each heading below is an explanation
that seemed obvious enough to state without checking. Four fail a specific test;
one — the temperature signal — holds up under two.

### Traffic drives the daily cycle

![24-hour rhythm](charts/07_daily_rhythm.png)

PM2.5 peaks at **6am and 10pm** and bottoms out at midday. Both rush hours fall
where the curve is already declining.

Weekends provide a second, independent check — and they are **equal or slightly
worse** than weekdays in all six cities, with the largest gap just 2.3 µg/m³ in
the wrong direction. If commuter traffic set the daily rhythm, neither result
would look like this.

### Thermal inversion explains the overnight peak

The textbook explanation, and the one an earlier draft of this README asserted.
Two independent checks contradict it:

| Check | Inversion predicts | Data shows |
|---|---|---|
| PM2.5 against day-night temperature range | Rises steadily | 22.1 → 29.8 → 30.0 → **27.7** (rises, then falls) |
| Day-night amplitude by season | Larger in winter | Summer **35.6** vs winter **30.2** |

Inversion is strongest in cold weather, so the seasonal amplitude should be
larger in winter. It is larger in summer.

This sits alongside Part 3 rather than against it. Comparing the extreme
deciles, dirty days really do have a 50% wider temperature range. But across the
full range the relationship stops being monotonic — and inversion requires it to
be monotonic, since a wider range should mean a stronger cap every time. A
difference between extremes is not the same as a mechanism that scales.

Daytime convective mixing fits the midday trough better, but the temperature
correlation below cuts against that too. The mechanism is genuinely unresolved
here.

### The temperature signal is a seasonal artefact

Temperature correlates with PM2.5 at +0.233 overall, which looked like seasonal
confounding — northern winters being both cold and polluted.

Splitting by season should have dissolved it. Instead it **strengthened**:
+0.414 in summer, +0.409 in autumn, with only winter near zero. Within a given
season, warmer days really are dirtier.

A second check points the same way. Warm days tend to be calm ones (temperature
against wind, r = −0.143), so the temperature signal could have been wind wearing
a disguise. Holding wind constant barely moves it — +0.233 falls only to +0.197,
keeping 85% of its strength. Whatever temperature is doing, it is not doing it
through wind.

### April's peak comes from field burning

April is the worst month in five of six cities, repeating in both years, and it
is also the driest — 2.1mm against 8–12mm later in the year. Post-harvest field
burning is the intuitive explanation.

(April is one of seven months with two years of data behind it. January and
September–December rest on a single year, so their figures carry less weight —
the charts mark them.)

The chemistry argues against it. In April, PM2.5 rises 24–52% while CO **falls
10–13%** in Hanoi, Hai Phong and Can Tho. Combustion produces CO. Whatever
drives the April peak, it does not look like local burning.

### Episodes build up gradually

Averaged over 223 episode onsets — every day that crossed 35 µg/m³ straight after
a day below it — PM2.5 *drifts downward* for three days (33.8, 30.4, 28.9) and
then jumps to 43.0, a **49% rise overnight**.

That rules out gradual accumulation and points to a discrete trigger — a wind
shift, an incoming air mass. It also means the PM2.5 series carries no
early-warning signal; forecasting would have to lean on meteorology instead.

**The one that survived** is the temperature signal above. It was the weakest
of the five going in, and it is the only one still standing after two separate
checks.

<sub>Supporting charts for this section:
[weather correlations, raw and wind-adjusted](charts/04_weather_correlation.png) ·
[bad-day share by month](charts/06_month_heatmap.png) ·
[sustained episodes](charts/08_episodes.png)</sub>

---

# Part 5 — Where that leaves the causes

Pulling the four parts together, here is every hypothesis this project tested,
what each one predicts, and the number the data returned.

![Ten hypotheses against the numbers that test them](charts/17_hypothesis_tests.png)

Of the ten, four predictions match the data, two match in part, and four fail
outright.
The failures are the more useful half: several of the surviving hypotheses would
produce identical numbers, and this dataset has no emissions inventory, no
traffic counts and no fire-detection data to tell them apart. A **failed**
prediction rules an explanation out; a matching one only fails to rule it out.

<sub>An earlier version of this chart scored each hypothesis on a 0–1 "weight of
evidence" scale. Those scores were invented — there was no rule behind them, so
they are gone. Every figure above is queried from the warehouse and recomputed
whenever the charts are regenerated.</sub>

What that leaves is narrower and firmer:

- **Daily variation is regional, not national.** Three groups of cities move
  independently of each other, so monitoring and alerting have to be regional
  even where policy is national.
- **There is more than one kind of problem.** Particulate and photochemical
  pollution rank the cities differently and would need different responses.
- **Weather modulates rather than creates.** It decides whether particles
  disperse or accumulate; it does not decide whether they are emitted. Even the
  strongest weather factor, wind, accounts for about 12% of the day-to-day
  variation.
- **Four intuitive explanations fail a specific test each** — and one that was
  expected to fail did not.

Settling which of the surviving explanations actually dominates would need an
emissions inventory, satellite fire detection (NASA FIRMS), wind direction, and
traffic counts. All outside this project's scope, and all named in the code
comments where they would fit.

---

## Setup

```bash
git clone https://github.com/Tuong1308/airquality-etl.git
cd airquality-etl

python -m venv venv && source venv/Scripts/activate    # Linux/macOS: venv/bin/activate
pip install -r requirements.txt

cp .env.example .env                                    # fill in your database password
psql -U postgres -c "CREATE DATABASE airquality;"
psql -U <user> -d airquality -f sql/schema.sql
```

## Running it

```bash
python -m src.main --date 2026-06-01                    # one specific day
python -m src.main --yesterday                          # what a scheduler would call
python -m src.main --start-date 2025-02-01 --end-date 2026-08-12   # backfill
python -m src.main --lookback 7                         # re-run last week, filling gaps
python -m src.charts                                    # regenerate the descriptive charts
python -m src.charts_drivers                            # regenerate the driver-evidence charts
pytest                                                  # 9 tests, no network, 0.8s
```

A single day takes **~16 seconds** across all six cities. The full 18-month
backfill — 558 days, roughly 6,700 API calls — runs in about **1.6 hours**.

---

## Design decisions

| Decision | Why | Alternative considered |
|---|---|---|
| Keep raw JSON before transforming | Re-run transforms without re-fetching; fix past bugs retroactively | Transform in flight — loses the ability to correct history |
| Natural key `(city_id, datetime_utc)` | Foundation for idempotent upserts; the database itself rejects duplicates | `SERIAL` — silently duplicates rows on re-run |
| `datetime_utc` as `TIMESTAMPTZ`, `datetime_local` as `TIMESTAMP` | `TIMESTAMPTZ` normalises to UTC internally, so two such columns would store identical values | Both as `TIMESTAMPTZ` — caught in schema review, before any data was loaded |
| `INSERT ... ON CONFLICT DO UPDATE` | Any day can be re-run safely | Delete-then-insert — simpler, handles source deletions, but loses insert history |
| Aggregate `target_date` **and** `target_date + 1` | A UTC batch feeds two local dates at +7h | Aggregating one date — measured a **34% error** on Can Tho before this was fixed |
| `hours_recorded` on the daily table | Separates a complete day from a partial one; every analytical query filters on it | Assuming completeness — the 34% error stayed invisible without this column |
| Per-city error isolation | One city failing doesn't cost the other five | Global try/except — a single failure loses the whole day |
| Collect six pollutants, not just PM2.5 | Made the Da Nang ozone finding and the Hanoi/HCMC source split possible | PM2.5 only — cheaper, and would have produced a confidently wrong ranking |

**Validation runs in three tiers**, on the principle that one bad column should
not discard a whole row:

| Check | Action | Rationale |
|---|---|---|
| Missing key | **Drop row** | Cannot be stored |
| Negative reading | **Set NULL, keep row** | Physically meaningless, but the other columns still hold |
| PM2.5 > 1000 µg/m³ | **Flag, keep row** | Could be a genuine wildfire |
| PM2.5 > PM10 | **Log ERROR, keep row** | PM2.5 is a subset of PM10 — a violation is certainly a source error |

Across all 80,328 rows: **zero violations**. The rules stay as a guard against
future schema drift.

---

## Known limitations

- **No orchestration yet.** The pipeline exposes `--yesterday` and `--lookback N`
  for a scheduler, but nothing calls them automatically. Windows Task Scheduler
  was skipped deliberately in favour of moving straight to Airflow. The Linux
  cron equivalent:
  ```
  0  6 * * *  cd /path/to/airquality-etl && venv/bin/python -m src.main --yesterday
  30 6 * * 0  cd /path/to/airquality-etl && venv/bin/python -m src.main --lookback 7
  ```
- **Charts regenerate manually.** They read live from the database, so they are
  never more than one run stale — but nothing schedules them.
- **Eighteen months is too short for trend claims.** Only February–August
  overlaps across both years. Patterns repeating in both years are treated as
  patterns; anything appearing once is treated as an event.
- **Correlation is not causation, and this README says so repeatedly.** Part 5
  reports what each hypothesis predicts against what was measured; it does not
  rank them, because this dataset offers no principled way to do so.
- **Only pairwise controls, not a full model.** Partial correlations were used
  to hold wind constant one factor at a time, which is what changed the reading
  of the rain effect. A regression controlling for all three factors at once
  would be stronger; the three are only weakly correlated with each other
  (|r| < 0.15), so the difference is likely small, but it has not been tested.
- **Significance is reported only where the coefficient is small enough to
  doubt.** The two weakest correlations (PM2.5–ozone and PM2.5–rain) were tested
  and both clear the threshold comfortably. The larger coefficients are not in
  question at these sample sizes.
- **Every number in every chart caption is computed at render time.** An earlier
  draft hard-coded some of them, and one chart carried invented scores; both
  have been removed. If the database changes, the captions change with it.
- **The `dust` variable was dropped.** It returned 0.0 across all six cities for
  the entire period. Cross-checking against Dubai (24–72 µg/m³) confirmed the
  model does not cover Southeast Asia, rather than the request being malformed.
- **No failure alerting**, **no Docker packaging**, **local PostgreSQL only**.

---

## What's next

Project 2 turns this into an orchestrated pipeline. Most of the groundwork is
in place:

| Today | Becomes |
|---|---|
| `run_one_day()` | A task in an Airflow DAG |
| `--date` | `{{ ds }}` |
| Validation inside `transform.py` | `dbt test` |
| `aggregate.py` | A dbt mart model |
| Manual chart regeneration | A `generate_charts` task downstream of `aggregate` |
| Local PostgreSQL | Docker Compose |

On the analysis side, the open questions have concrete next steps: satellite
fire detection to settle the April question, wind direction to trace incoming
air masses, and an emissions inventory to turn the source fingerprints into
actual attributions.

---

Every figure quoted above comes from a query in
[`sql/analysis.sql`](sql/analysis.sql); the chart captions recompute theirs at
render time, so nothing in this README can drift out of step with the database.

---

<sub>Python 3.13 · PostgreSQL 15 · pandas · SQLAlchemy · psycopg2 · tenacity · pytest · matplotlib · Data: <a href="https://open-meteo.com">Open-Meteo</a></sub>