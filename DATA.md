# Liftoff - Data Sources, Schemas & Storage

Look-up reference for the data Liftoff uses: where it comes from, what the fields mean, what units they are in, how to handle gaps, and where files live on disk. Datasets themselves are **never committed**. Only the scripts that fetch and process them are tracked in git.

**Contents**

1. [Source register](#1-source-register)
2. [Missing-data policy](#2-missing-data-policy)
3. [Launch Library 2 API](#3-launch-library-2-api)
4. [Open-Meteo Historical Weather API](#4-open-meteo-historical-weather-api)
5. [Unit conversions](#5-unit-conversions)
6. [Storage layout (`data/`)](#6-storage-layout-data)
7. [EDA report: SpaceX launch feature table](#7-eda-report-spacex-launch-feature-table)

> Status: only Launch Library 2 and Open-Meteo are documented so far. The earlier SpaceX community API was dropped (archived and unreachable). NASA Space Shuttle data and CelesTrak / Space-Track TLEs (listed in [`DELIVERABLES.md`](DELIVERABLES.md)) will be added in later issues.

---

## 1. Source register

| Source | Origin / URL | Access method | License | Sensitivity | Notes |
|---|---|---|---|---|---|
| Launch Library 2 (LL2) API | `https://ll.thespacedevs.com/2.3.0` ([docs](https://thespacedevs.com/llapi), by The Space Devs) | Public HTTPS GET, JSON, no auth (free tier) | Not stated on the API page: **TBD** | Public, no PII | Free tier is **15 unauthenticated requests per hour**. Covers all providers and historical launches, not just SpaceX. Replaces the SpaceX community API. |
| Open-Meteo Historical Weather API | `https://archive-api.open-meteo.com/v1/archive` | Public HTTPS GET, JSON, no key (free tier) | CC BY 4.0, **non-commercial use only** on the free tier | Public, no PII | Attribution required. Backed by ERA5 / ERA5-Land reanalysis. |

---

## 2. Missing-data policy

> ## ⚠️ TEMPORARY - NEEDS DISCUSSION WITH PM ⚠️
> **Interim rule, by kind of field:**
> - **Missing labels** (categorical or text fields, including the outcome): either **generalize** to a coarser category or store `null`. Decide per field and write down which.
> - **Missing numbers**: keep as `null` (JSON `null` / pandas `NaN` / `None`) **and flag them**, so downstream code can tell "missing" apart from a real value. Never fill with 0.
>
> Do not drop rows or impute in the pipeline. The flagging mechanism (for example a companion `<column>_missing` boolean), the generalization scheme, and per-field choices are **not decided**: **TBD, must be discussed with a PM** before feature engineering starts. Do not build logic that depends on the current choice.

---

## 3. Launch Library 2 API

LL2 is a community-run launch database from The Space Devs. It covers launches from every provider and goes back to 1957, so it can also supply the historical comparison. Fields below were read from a live response (`/2.3.0/launches/?limit=1&mode=detailed`, checked 2026-10-22). Anything not seen in that response is marked **TBD**.

### 3.1 Endpoints

| Endpoint | Returns | Status |
|---|---|---|
| `GET /2.3.0/launches/` | Paginated list of all launches (past and upcoming) | Verified live |
| `GET /2.3.0/launches/{id}/` | One launch (`id` is a UUID) | Assumed from the `url` field in responses: **TBD** |
| `launches/previous`, `launches/upcoming` | Past-only / future-only launch lists | Assumed from API convention: **TBD** |
| `pad`, `rocket.configuration`, `launch_service_provider`, `mission` | Embedded in each launch when `mode=detailed` | Verified live |

Base URL: `https://ll.thespacedevs.com`. Auth: none. Responses: JSON. Use `?mode=detailed` to get the nested objects shown below.

Pagination envelope: `count` (total matches, 8130 at time of check), `next` and `previous` (URLs, `null` at the ends), `results` (array). Page size is set with `limit` and `offset`. **Maximum `limit`: TBD.**

### 3.2 Rate limits

The free tier allows **15 unauthenticated requests per hour** ([source](https://thespacedevs.com/llapi)); higher rates need a paid plan. A full pull of ~8,000 launches will take many pages, so it must be spread over several hours. Fetch once, cache every page to `data/raw/`, and never re-poll. Whether a dev/snapshot endpoint exists is **TBD**.

### 3.3 Launch object fields

Types and examples are from the live response. "Nullable" is only marked where `null` was seen; other fields may also be `null` (**TBD**). Units are noted where the response or name makes them clear.

| Field | Type | Nullable | Unit / format | Notes |
|---|---|---|---|---|
| `id` | string (UUID) | no | | Primary key |
| `name` | string | no | | `"<Rocket> \| <Mission>"` |
| `slug`, `url` | string | no | | |
| `launch_designator` | string | maybe | COSPAR, e.g. `1957-001` | |
| `status` | object | no | `id`, `name`, `abbrev`, `description` | **Outcome label.** Only `id 3 = "Launch Successful"` (`Success`) was observed. The full status list (failure, partial failure, TBD, scheduled...) is **TBD** |
| `net` | string | no | ISO 8601, UTC | "No earlier than" launch time. Moves as the launch slips |
| `net_precision` | object | yes | | `null` in the sample. Presumably how exact `net` is: **TBD** |
| `window_start`, `window_end` | string | no | ISO 8601, UTC | Launch window. Window length is derivable |
| `last_updated` | string | no | ISO 8601, UTC | |
| `probability` | number | yes | | Forecast launch probability. `null` in the sample, units **TBD** |
| `weather_concerns` | string | yes | | `null` in the sample |
| `failreason` | string | no | free text | Empty string `""` when there is none |
| `launch_service_provider` | object | no | | `id`, `name`, `abbrev`, `type`, `country[]`, `founding_year`, `total_launch_count`, `successful_launches`, `failed_launches`, ... |
| `rocket.configuration` | object | no | | `id`, `name`, `full_name`, `variant`, `reusable` (boolean), `length`, `diameter`, `leo_capacity`, `gto_capacity`, `successful_launches`, `failed_launches`, ... Capacity and size fields were `null` in the sample; units **TBD** |
| `rocket.launcher_stage`, `rocket.spacecraft_stage`, `rocket.payloads` | arrays | no | | Stage/booster details. Contents **TBD** |
| `mission` | object | yes | | `name`, `type` (e.g. `Test Flight`), `description`, `orbit{name, abbrev}` |
| `pad` | object | no | | `id`, `name`, `latitude`, `longitude` (numbers, WGS84), `location{name, country, timezone_name, latitude, longitude}`. Used to look up weather |
| `*_launch_attempt_count`, `*_launch_attempt_count_year` | integer | no | count | Orbital / location / pad / agency counters |
| `pad_turnaround` | string | no | ISO 8601 duration (`P0D`) | |
| `webcast_live`, `vid_urls`, `info_urls`, `image`, `mission_patches`, `timeline`, `updates`, `program`, `hashtag`, `infographic`, `flightclub_url` | various | | | Media and metadata. Not model features |

**Delay hours are not a field.** LL2 has no "delay" value. `net` changes over time and only its latest value is returned by a normal request, so deriving a delay needs a defined baseline. That is a scoping decision still open in [`DELIVERABLES.md`](DELIVERABLES.md) (milestone 1). Whether LL2 exposes `net` history (e.g. via `updates`) is **TBD**.

### 3.4 Licensing

The API page states no license, terms or attribution requirement. **TBD: confirm with a PM** before publishing results (see the checklist at the top of this file).

### 3.5 If a data point is missing

Follow the [missing-data policy](#2-missing-data-policy). Cases to expect:

- `status` for upcoming launches has no outcome yet: these have no label and are excluded from training.
- `failreason` uses `""` rather than `null` for "none". Treat it as "no failure reason", not as a missing value.
- `probability`, `weather_concerns`, `net_precision` and the rocket capacity/size numbers can be `null`. Numbers among these are flagged per the policy.
- `mission` and `pad` fields may be sparse for old launches: **TBD**, check against a few pre-1990 records.

---

## 4. Open-Meteo Historical Weather API

### 4.1 Endpoint

`GET https://archive-api.open-meteo.com/v1/archive` (verified live 2026-10-20)

| Parameter | Required | Value we use | Notes |
|---|---|---|---|
| `latitude`, `longitude` | yes | launch site coordinates (WGS84) | Site coordinates come from `pad.latitude` / `pad.longitude` in LL2 ([§3.3](#33-launch-object-fields)) |
| `start_date`, `end_date` | yes | `yyyy-mm-dd` | |
| `hourly` | no | comma-separated variable list | No default. Daily aggregates also available via `daily` (requires `timezone`) |
| `temperature_unit` | no | `celsius` (default) | |
| `wind_speed_unit` | no | **`kn`** (default is `kmh`) | **Must be set explicitly**, see [§5](#5-unit-conversions) |
| `precipitation_unit` | no | `mm` (default) | |
| `timeformat` | no | `iso8601` (default) | |
| `timezone` | no | `GMT` (default) | Keep UTC so it matches `net` |

Example (Cape Canaveral area, tested):

```
https://archive-api.open-meteo.com/v1/archive?latitude=28.5729&longitude=-80.649&start_date=2020-05-30&end_date=2020-05-30&hourly=temperature_2m,wind_speed_10m,cloud_cover&wind_speed_unit=kn
```

### 4.2 Response shape

| Field | Type | Notes |
|---|---|---|
| `latitude`, `longitude` | float | Center of the grid cell actually used (may differ slightly from the request) |
| `elevation` | float, metres | Terrain model elevation |
| `generationtime_ms` | float | |
| `utc_offset_seconds` | integer | |
| `timezone`, `timezone_abbreviation` | string | |
| `hourly_units` | object | Unit string per variable, **always check this** |
| `hourly` | object | `time` = array of ISO 8601 strings, plus one array per requested variable (same length) |

Errors: HTTP 400 with `{"error": true, "reason": "..."}`.

### 4.3 Hourly variables (candidate set)

Units shown are what the API returns **with the settings in §4.1**. The final feature list is an analysis decision and is not made here.

| Variable | Type | Unit returned | Notes |
|---|---|---|---|
| `temperature_2m` | float | °C | Air temperature at 2 m |
| `relative_humidity_2m` | float | % | |
| `dew_point_2m` | float | °C | |
| `precipitation` | float | mm | Total over the preceding hour |
| `rain` | float | mm | |
| `snowfall` | float | cm | |
| `pressure_msl` | float | hPa | Sea-level pressure |
| `surface_pressure` | float | hPa | |
| `cloud_cover` | float | % | Also `_low`, `_mid`, `_high` |
| `wind_speed_10m` | float | **kn** | Only because we pass `wind_speed_unit=kn` |
| `wind_speed_100m` | float | **kn** | Same |
| `wind_gusts_10m` | float | **kn** | Same |
| `wind_direction_10m` | float | ° | Direction wind comes from |
| `weather_code` | integer | WMO code | Categorical, not a magnitude |

The full variable list (radiation, soil, evapotranspiration, daily aggregates) is in the [official docs](https://open-meteo.com/en/docs/historical-weather-api).

### 4.4 Rate limits (free tier)

| Window | Limit |
|---|---|
| Per minute | 600 calls |
| Per hour | 5,000 calls |
| Per day | under 10,000 calls |
| Per month | 300,000 calls |

Limits apply per IP and per application. Shared cloud hosts (Vercel, Netlify, Render, Google Sheets) can hit limits sooner. Misuse can get an IP blocked without notice. Request several days and many variables per call instead of many small calls.

### 4.5 Data availability

- ERA5 reaches back to 1940, ERA5-Land to 1950. Both lag real time by about 5 days, so very recent launches may have no data yet.
- Weather is a **gridded reanalysis estimate**, not a station measurement.

### 4.6 Licensing and attribution

- Free use is **non-commercial only**. Commercial use needs a paid plan and API key.
- Data is CC BY 4.0: **credit Open-Meteo** wherever results are shown (dashboard footer or report). Exact wording is on the [licence page](https://open-meteo.com/en/licence): **TBD, confirm with a PM.**
- Underlying data is Copernicus ERA5 / ERA5-Land: where shown, include "Generated using Copernicus Climate Change Service information".

### 4.7 If a data point is missing

Follow the [missing-data policy](#2-missing-data-policy): missing numbers stay `null` and are flagged. **How Open-Meteo marks a missing hourly value is not stated in its docs: TBD.** JSON `null` is expected; confirm by checking a response for dates near the 5-day lag and treat any array element that is `null` as missing. Also expect gaps when a launch date is too recent or the launch time is imprecise (`net_precision`).

---

## 5. Unit conversions

> ## ⚠️ CONVERSIONS REQUIRED ⚠️
> The raw data is **not** in SI. The physics code works in **SI** (see [`PHYSICS.md`](PHYSICS.md) and `src/physics/constants.py`). **Convert at the `raw` → `interim` step and never edit `raw/`.** Do not mix units inside a column; if a column is converted, the new column name or documentation must say so.

| Quantity | Stored in `raw/` as | Convert to | How |
|---|---|---|---|
| Wind speed (`wind_speed_*`, `wind_gusts_*`) | knots (`kn`) | m/s | × 0.514444 |
| Air temperature (`temperature_2m`, `dew_point_2m`) | °C | K | + 273.15 |
| Pressure (`pressure_msl`, `surface_pressure`) | hPa | Pa | × 100 |
| Precipitation | mm | m (if needed) | ÷ 1000 |
| Wind direction | degrees | radians (if needed) | × π / 180 |
| Time (`net`, `window_*`) | ISO 8601 string (UTC) | datetime (UTC) | `pd.to_datetime(x, utc=True)` |
| Relative humidity, cloud cover | % | fraction (if needed) | ÷ 100 |

Knots were chosen as the weather wind unit (the issue lists knots as an example unit). The Open-Meteo default is km/h, so forgetting `wind_speed_unit=kn` silently yields the wrong unit.

> **Current state (checked 2026-10-27):** `src/data/fetch_weather.py` does **not** pass `wind_speed_unit=kn`, so the wind columns in `data/raw/historical_weather.csv` are in **km/h**, not knots as the wind row above assumes. The cleaning script converts them with **÷ 3.6** to m/s. Use ÷ 3.6 for the current raw files and × 0.514444 only if the fetcher is changed to request knots. Which of the two to fix (fetcher or this table) is **TBD, for a PM**.

---

## 6. Storage layout (`data/`)

`data/` is a **local working area and is git-ignored** (only the empty `.gitkeep` placeholder files are tracked). **Never commit anything under it**, including samples. Commit the scripts that create the files, not the files.

```
data/
├── raw/         # exactly as received from the source
├── interim/     # cleaned / converted / joined intermediate steps
└── processed/   # final, model- and dashboard-ready tables
```

| Folder | Holds | Rules |
|---|---|---|
| `data/raw/` | Unmodified API responses (e.g. the LL2 launches JSON pages, Open-Meteo hourly JSON), saved straight from the fetcher | **Immutable.** Never edit by hand; re-fetch instead. Units are source units (knots, °C, hPa). |
| `data/interim/` | Intermediate outputs: unit conversions ([§5](#5-unit-conversions)), type fixes, LL2 launches joined to weather by pad coordinates and time | Reproducible from `raw/` by a tracked script. Safe to delete and regenerate. |
| `data/processed/` | Final feature tables for the XGBoost models and the dashboard | Reproducible from `interim/`. This is what training and the app read. |

Flow: `raw/` → `interim/` → `processed/`. Data only moves forward, and each step is a tracked script or notebook so any teammate can rebuild every folder from scratch.

File naming inside these folders is not yet decided: **TBD.**

---

## 7. EDA report: SpaceX launch feature table

Produced by `python src/data/eda.py` (checked 2026-10-27). It prints every table below and writes nothing to disk. SpaceX launches only (LL2 `lsp__id=121`), `net` from 2006-03-24 to 2026-10-27.

> **Dependency:** the input, `data/processed/ml_features.csv`, is written by `src/data/build_features.py`, which is in an open pull request (`data/feature-engineering`, PR #31) and not yet on `main`. Numbers below were produced from that script's output. A separate cleaning script (`data/clean-pipeline`, PR #29) writes a different table; see [§7.6](#76-discrepancy-between-the-two-processed-tables).

### 7.1 Pipeline schema

```
LL2 API          --fetch_spacex.py-->  data/raw/spacex_launches.csv      (742 rows, 7 columns)
Open-Meteo API   --fetch_weather.py--> data/raw/historical_weather.csv   (741 rows, 10 columns)
                          |
                    build_features.py: left join on launch_id (one-to-one), check that
                    time and coordinates agree, add wind_speed_ratio and payload_ratio
                          v
                 data/processed/ml_features.csv                          (742 rows, 18 columns)
```

Each launch has at most one weather record: the hourly value closest to `net`, at the pad coordinates. Units are source units (see [§7.2](#72-feature-table-columns)). File names are the ones the scripts use today ([§6](#6-storage-layout-data) still lists naming as TBD).

### 7.2 Feature table columns

| Column | Type | Unit / format | Notes |
|---|---|---|---|
| `launch_id` | string (UUID) | | LL2 `id`. Join key |
| `rocket_type` | string | | LL2 `rocket.configuration.name` (e.g. `Falcon 9`) |
| `payload_mass_kg` | float | kg | Sum of payload masses. Missing for 98.7% of launches (see [§7.4](#74-missing-values)) |
| `launchpad_latitude`, `launchpad_longitude` | float | degrees, WGS84 | LL2 `pad`. 7 distinct pad coordinates |
| `launch_timestamp_utc` | string | ISO 8601, UTC | LL2 `net` (latest value, not the original schedule) |
| `mission_success` | boolean | | **Target.** `True` = LL2 status 3. `False` = status 4 (failure) or 7 (partial failure). Anything else is null in the fetcher |
| `launch_time`, `latitude`, `longitude` | string / float | UTC / degrees | Copies of the launch time and pad coordinates, repeated by the weather file. Verified equal to the launch columns by the builder. Not used in the analysis |
| `weather_time` | string | ISO 8601, UTC | Hourly weather record used |
| `temperature_2m` | float | °C | Air temperature at 2 m |
| `wind_speed_10m` | float | **km/h** | Not converted. See [§5](#5-unit-conversions) |
| `precipitation` | float | mm | Over the preceding hour |
| `cloud_cover` | float | % | |
| `high_altitude_wind_assumed` | float | **km/h** | **Not a measurement.** The fetcher copies `wind_speed_10m`, so it is identical on every row. Placeholder until a high-altitude wind source is added |
| `wind_speed_ratio` | float | ratio | `high_altitude_wind_assumed / wind_speed_10m`. **Equals 1 on every row with weather**, because of the placeholder above. Carries no information yet |
| `payload_ratio` | float | ratio | `payload_mass_kg / max_payload_capacity_kg`. **Empty on every row**, because no rocket capacity column exists yet. Placeholder |

### 7.3 Summary statistics (feature table, 742 rows)

Outcome: **727 successes, 15 failures** (2.0%). Every result below rests on 15 failures.

| Column | n | Mean | Std | Min | Median | Max |
|---|---|---|---|---|---|---|
| `payload_mass_kg` | 10 | 2779.4 | 2031.8 | 1000.0 | 1900.0 | 6400.0 |
| `launchpad_latitude` | 742 | 30.298 | 3.397 | 9.048 | 28.562 | 34.632 |
| `launchpad_longitude` | 742 | -92.210 | 28.315 | -120.611 | -80.604 | 167.743 |
| `temperature_2m` (°C) | 741 | 20.198 | 6.007 | 4.800 | 20.800 | 34.500 |
| `wind_speed_10m` (km/h) | 741 | 13.432 | 6.706 | 0.400 | 12.900 | 34.900 |
| `precipitation` (mm) | 741 | 0.068 | 0.506 | 0.000 | 0.000 | 8.100 |
| `cloud_cover` (%) | 741 | 50.211 | 40.800 | 0 | 45 | 100 |

Success rate by rocket type:

| `rocket_type` | Launches | Failures | Success rate |
|---|---|---|---|
| Falcon 9 | 700 | 4 | 0.994 |
| Starship | 14 | 5 | 0.643 |
| Falcon Heavy | 14 | 0 | 1.000 |
| Starship Prototype | 9 | 3 | 0.667 |
| Falcon 1 | 5 | 3 | 0.400 |

### 7.4 Missing values

| Column(s) | Missing | Cause |
|---|---|---|
| `payload_mass_kg` | **732 of 742 (98.7%)** | LL2 lists a payload mass for only 10 launches |
| `payload_ratio` | **742 of 742 (100%)** | Placeholder: needs a rocket capacity column that does not exist yet |
| `launch_time`, `latitude`, `longitude`, `weather_time`, `temperature_2m`, `wind_speed_10m`, `precipitation`, `cloud_cover`, `high_altitude_wind_assumed`, `wind_speed_ratio` | **1 of 742 (0.1%)**, the same launch every time | `e2886a96-5ce9-4f45-872f-4e25a00be837` (Falcon 9, `net` 2026-10-27T07:25:51Z) has no weather record. It is inside the ~5-day ERA5 lag in [§4.5](#45-data-availability) |
| All other columns | 0 | |

The left join keeps the launch with no weather and leaves its weather columns empty, as the [§2](#2-missing-data-policy) interim rule asks (do not drop rows).

### 7.5 Correlation with launch outcome

Pearson correlation between each numeric feature and `mission_success` coded 0/1 (point-biserial). Computed on launches that have a value for the feature. The duplicate `latitude` and `longitude` columns are left out.

| Feature | n | Failures in n | Pearson r |
|---|---|---|---|
| `launchpad_latitude` | 742 | 15 | 0.279 |
| `launchpad_longitude` | 742 | 15 | -0.253 |
| `wind_speed_10m` | 741 | 15 | -0.097 |
| `high_altitude_wind_assumed` | 741 | 15 | -0.097 (identical copy of the above) |
| `temperature_2m` | 741 | 15 | -0.068 |
| `precipitation` | 741 | 15 | 0.019 |
| `cloud_cover` | 741 | 15 | 0.012 |
| `payload_mass_kg` | 10 | 0 | undefined (no failures among the 10 launches with a value) |
| `wind_speed_ratio` | 741 | 15 | undefined (constant 1) |
| `payload_ratio` | 0 | 0 | undefined (no values) |

How to read this:

- **Weather is weakly related to the outcome.** All four weather features have |r| below 0.10. With 15 failures, that is within what chance could produce, so these numbers are not evidence either way.
- **Latitude and longitude are proxies for the rocket program, not geography.** The largest values (|r| 0.25 to 0.28) coincide with Falcon 1 flying from Kwajalein (9.05, 167.74; 3 failures in 5 launches) and Starship and its prototypes flying from the Texas pad near 26.0, -97.2 (8 failures in 23 launches). Do not read them as "pad location causes failure".
- **Payload mass and both ratio columns cannot be analysed** yet. Re-run the script once a high-altitude wind source and a rocket capacity column are added.

### 7.6 Discrepancy between the two processed tables

Two scripts in open pull requests both write to `data/processed/` and produce different tables from the same raw files. This report uses the feature builder's table.

| | Feature builder (`build_features.py`, PR #31): **used here** | Cleaner (`clean_data.py`, PR #29) |
|---|---|---|
| Output file | `ml_features.csv` | `cleaned_launches.csv` |
| Rows | 742 (left join keeps the launch with no weather) | 741 (inner join; that launch is lost, and the script's "kept 741 of 741" message does not show it) |
| Wind units | km/h, unconverted | m/s (÷ 3.6) |
| Column names | Source names (`wind_speed_10m`) | Unit suffixes (`wind_speed_10m_ms`, `temperature_2m_c`) |
| Extra columns | `wind_speed_ratio`, `payload_ratio`, duplicate `launch_time` / `latitude` / `longitude` | None |
| Dropped rows | None | Drops any row missing a required value, which conflicts with the [§2](#2-missing-data-policy) "do not drop rows" rule |

Neither script reads the other's output. Correlation values match on either table (a change of unit does not alter Pearson r).

### 7.7 Delay analysis: not done

The issue asks for correlations against launch delays. **LL2 has no delay field** and the baseline for computing one is not defined ([§3.3](#33-launch-object-fields), milestone 1 in [`DELIVERABLES.md`](DELIVERABLES.md)), so this report uses the mission outcome instead. Delay correlations are pending a PM's definition of delay.

### 7.8 Still to document

Documentation for the physics data has not been added to this file yet.
