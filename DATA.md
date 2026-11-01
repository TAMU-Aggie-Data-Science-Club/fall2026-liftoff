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
8. [GCAT payload mass](#8-gcat-payload-mass)
9. [High-altitude winds (NOAA IGRA2 radiosondes)](#9-high-altitude-winds-noaa-igra2-radiosondes)

> Status: only Launch Library 2, Open-Meteo, GCAT (payload mass only) and NOAA IGRA2 (upper-air winds only) are documented so far. The earlier SpaceX community API was dropped (archived and unreachable). NASA Space Shuttle data and CelesTrak / Space-Track TLEs (listed in [`DELIVERABLES.md`](DELIVERABLES.md)) will be added in later issues.

---

## 1. Source register

| Source | Origin / URL | Access method | License | Sensitivity | Notes |
|---|---|---|---|---|---|
| Launch Library 2 (LL2) API | `https://ll.thespacedevs.com/2.3.0` ([docs](https://thespacedevs.com/llapi), by The Space Devs) | Public HTTPS GET, JSON, no auth (free tier) | Not stated on the API page: **TBD** | Public, no PII | Free tier is **15 unauthenticated requests per hour**. Covers all providers and historical launches, not just SpaceX. Replaces the SpaceX community API. |
| Open-Meteo Historical Weather API | `https://archive-api.open-meteo.com/v1/archive` | Public HTTPS GET, JSON, no key (free tier) | CC BY 4.0, **non-commercial use only** on the free tier | Public, no PII | Attribution required. Backed by ERA5 / ERA5-Land reanalysis. Surface variables only: the archive endpoint returns nothing for pressure levels. `fetch_weather.py` falls back to `https://historical-forecast-api.open-meteo.com/v1/forecast` for launches the archive cannot serve yet. |
| NOAA NCEI IGRA2 (Integrated Global Radiosonde Archive) | `https://www.ncei.noaa.gov/pub/data/igra/`. We download `data/data-por/<STATION>-data.txt.zip` | Plain HTTPS download of a zipped fixed-width text file per station (no API, no auth). Cached to `data/raw/igra/` | No license found in the IGRA2 readme; NOAA data is generally free to use: **TBD, confirm with a PM** | Public, no PII | **Source of the `upper_wind_*` columns**; see [§9](#9-high-altitude-winds-noaa-igra2-radiosondes). Measured balloon winds, about 2 soundings a day per station. Credit NOAA NCEI where shown. |
| GCAT (General Catalog of Artificial Space Objects) | `https://planet4589.org/space/gcat/` by Jonathan McDowell. We download the launch log `https://planet4589.org/space/gcat/tsv/launch/launch.tsv` | Plain HTTPS download of a TSV file (no API, no auth). Cached to `data/raw/gcat_launch.tsv` | CC BY, per the GCAT site: **TBD, confirm with a PM** | Public, no PII | **Source of `payload_mass_kg` only**; see [§8](#8-gcat-payload-mass). Attribution required. Suggested wording: "data from GCAT (J. McDowell, planet4589.org/space/gcat)". |

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
| `rocket.launcher_stage`, `rocket.spacecraft_stage`, `rocket.payloads` | arrays | no | | Stage/booster details. Contents **TBD**. LL2 payload masses are almost always empty, so `payload_mass_kg` comes from GCAT instead ([§8](#8-gcat-payload-mass)) |
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

- ERA5 reaches back to 1940, ERA5-Land to 1950. Both lag real time by about 5 days, so very recent launches may have no data yet. `fetch_weather.py` retries those launches against the historical-forecast API and records the choice in the `weather_source` column. Tested 2026-10-31: the archive served data for the same day (hours earlier than the "5 days" above suggests), so the fallback only triggers for future times or an archive error. A future launch time falls back and returns a **forecast**, not an observation, and `weather_source` is `historical_forecast` for it. A simulated archive outage (bad URL) fell back correctly for 2024 and 2018 launch times.
- Pressure-level winds are **not** available from the archive endpoint (every `wind_speed_<n>hPa` variable returns "undefined"). The historical-forecast endpoint has them only from about mid-2022, so [§9](#9-high-altitude-winds-noaa-igra2-radiosondes) uses radiosondes instead.
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
| `data/raw/` | Unmodified API responses (e.g. the LL2 launches JSON pages, Open-Meteo hourly JSON), saved straight from the fetcher. Also holds `gcat_launch.tsv`, the GCAT launch log exactly as downloaded ([§8](#8-gcat-payload-mass)), and `igra/`, the zipped IGRA2 station files ([§9](#9-high-altitude-winds-noaa-igra2-radiosondes)) | **Immutable.** Never edit by hand; re-fetch instead. Units are source units (knots, °C, hPa). |
| `data/interim/` | Intermediate outputs: unit conversions ([§5](#5-unit-conversions)), type fixes, LL2 launches joined to weather by pad coordinates and time | Reproducible from `raw/` by a tracked script. Safe to delete and regenerate. |
| `data/processed/` | Final feature tables for the XGBoost models and the dashboard | Reproducible from `interim/`. This is what training and the app read. |

Flow: `raw/` → `interim/` → `processed/`. Data only moves forward, and each step is a tracked script or notebook so any teammate can rebuild every folder from scratch.

File naming inside these folders is not yet decided: **TBD.**

Because `data/` is git-ignored, nobody gets `gcat_launch.tsv` or the IGRA2 zips from the repo. `fetch_spacex.py` downloads the GCAT file and `fetch_weather.py` downloads the IGRA2 zips the first time they run, and both reuse the local copy after that. Delete a file to pull a fresh copy. The Cape Kennedy zip is about 50 MB (230 MB unzipped), so the first weather run is slow.

---

## 7. EDA report: SpaceX launch feature table

Produced by `python src/data/eda.py` (checked 2026-10-31, after `payload_mass_kg` was switched to GCAT and the upper-air winds were added). It prints every table below and writes nothing to disk. SpaceX launches only (LL2 `lsp__id=121`), `net` from 2006-03-24 to 2026-10-31.

> **Pipeline:** the input, `data/processed/ml_features.csv`, is written by `src/data/build_features.py`. A separate cleaning script, `src/data/clean_data.py`, writes a different table to `data/interim/cleaned_launches.csv`; see [§7.6](#76-discrepancy-between-the-two-processed-tables). Both are on `main`.

### 7.1 Pipeline schema

```
LL2 API          --fetch_spacex.py-->  data/raw/spacex_launches.csv      (743 rows, 7 columns)
Open-Meteo API   --fetch_weather.py--> data/raw/historical_weather.csv   (743 rows, 48 columns)
NOAA IGRA2       --/                   (upper-air winds are added by the same script)
                          |
                    build_features.py: left join on launch_id (one-to-one), check that
                    time and coordinates agree, add wind_speed_ratio and payload_ratio
                          v
                 data/processed/ml_features.csv                          (743 rows, 56 columns)
```

Each launch has at most one weather record: the hourly value closest to `net`, at the pad coordinates. Units are source units (see [§7.2](#72-feature-table-columns)). File names are the ones the scripts use today ([§6](#6-storage-layout-data) still lists naming as TBD).

### 7.2 Feature table columns

| Column | Type | Unit / format | Notes |
|---|---|---|---|
| `launch_id` | string (UUID) | | LL2 `id`. Join key |
| `rocket_type` | string | | LL2 `rocket.configuration.name` (e.g. `Falcon 9`) |
| `payload_mass_kg` | float | kg | Payload delivered to orbit, from GCAT ([§8](#8-gcat-payload-mass)). Null for 26 launches (see [§7.4](#74-missing-values)) |
| `launchpad_latitude`, `launchpad_longitude` | float | degrees, WGS84 | LL2 `pad`. 7 distinct pad coordinates |
| `launch_timestamp_utc` | string | ISO 8601, UTC | LL2 `net` (latest value, not the original schedule) |
| `mission_success` | boolean | | **Target.** `True` = LL2 status 3. `False` = status 4 (failure) or 7 (partial failure). Anything else is null in the fetcher |
| `launch_time`, `latitude`, `longitude` | string / float | UTC / degrees | Copies of the launch time and pad coordinates, repeated by the weather file. Verified equal to the launch columns by the builder. Not used in the analysis |
| `weather_time` | string | ISO 8601, UTC | Hourly weather record used |
| `temperature_2m` | float | °C | Air temperature at 2 m |
| `wind_speed_10m` | float | **km/h** | Not converted. See [§5](#5-unit-conversions) |
| `precipitation` | float | mm | Over the preceding hour |
| `cloud_cover` | float | % | |
| `weather_source` | string | | `era5_archive` or `historical_forecast`: which Open-Meteo endpoint supplied the surface weather ([§4.5](#45-data-availability)). All 743 rows are `era5_archive` |
| `high_altitude_wind_assumed` | float | **km/h** | **Not a measurement.** The fetcher copies `wind_speed_10m`, so it is identical on every row. Kept so `build_features.py` and `clean_data.py` keep working. The real winds are the `upper_wind_*` columns below |
| `upper_wind_station`, `upper_wind_station_distance_km` | string / float | IGRA2 id / km | Radiosonde station used for the pad and its distance from the pad (11 to 35 km, see [§9](#9-high-altitude-winds-noaa-igra2-radiosondes)). See [§9](#9-high-altitude-winds-noaa-igra2-radiosondes) |
| `upper_wind_sounding_time`, `upper_wind_sounding_offset_h` | string / float | ISO 8601 UTC / hours | The balloon launch used, and how far it is from the rocket launch (negative = balloon earlier). At most 12 h |
| `upper_wind_top_km` | float | km | Highest height the balloon reported a wind at |
| `upper_wind_max_kmh`, `upper_wind_max_alt_km` | float | **km/h** / km | Peak wind at or below 30 km and the height where it occurred (usually the jet stream) |
| `upper_wind_speed_<h>km_kmh`, `upper_wind_dir_<h>km_deg` | float | **km/h** / degrees | Wind speed and the direction it blows **from** (0 = north, 90 = east), at `<h>` = 2, 4, ... 30 km above sea level. 30 columns. Blank where the balloon did not reach `<h>` |
| `wind_speed_ratio` | float | ratio | `high_altitude_wind_assumed / wind_speed_10m`. **Equals 1 on every row**, because of the placeholder above. Carries no information yet. Not yet switched to a real upper-air wind |
| `payload_ratio` | float | ratio | `payload_mass_kg / max_payload_capacity_kg`. **Empty on every row**, because no rocket capacity column exists yet. Placeholder |

### 7.3 Summary statistics (feature table, 743 rows)

Outcome: **728 successes, 15 failures** (2.0%). Every result below rests on 15 failures.

| Column | n | Mean | Std | Min | Median | Max |
|---|---|---|---|---|---|---|
| `payload_mass_kg` | 717 | 12442.0 | 5462.0 | 20.0 | 15500.0 | 18940.0 |
| `launchpad_latitude` | 743 | 30.304 | 3.399 | 9.048 | 28.562 | 34.632 |
| `launchpad_longitude` | 743 | -92.248 | 28.315 | -120.611 | -80.604 | 167.743 |
| `temperature_2m` (°C) | 743 | 20.186 | 6.003 | 4.800 | 20.800 | 34.500 |
| `wind_speed_10m` (km/h) | 743 | 13.428 | 6.708 | 0.400 | 12.900 | 34.900 |
| `precipitation` (mm) | 743 | 0.068 | 0.505 | 0.000 | 0.000 | 8.100 |
| `cloud_cover` (%) | 743 | 50.166 | 40.759 | 0 | 45 | 100 |
| `upper_wind_max_kmh` (km/h) | 705 | 127.3 | 51.8 | 24.1 | 118.4 | 494.6 |
| `upper_wind_max_alt_km` (km) | 705 | 15.5 | 6.4 | 0.83 | 13.2 | 30.0 |
| `upper_wind_speed_10km_kmh` (km/h) | 704 | 82.6 | 51.2 | 3.0 | 72.4 | 252.3 |
| `upper_wind_speed_20km_kmh` (km/h) | 698 | 31.1 | 19.6 | 0.7 | 27.6 | 269.7 |
| `upper_wind_speed_30km_kmh` (km/h) | 606 | 56.9 | 33.2 | 1.8 | 53.6 | 338.9 |

The other `upper_wind_*` columns follow the same pattern (strongest near 12 km, weakest near 20 km); `eda.py` prints all of them. The largest values (400 km/h at 6 km, 423.6 km/h at 28 km, 494.6 km/h for the peak) are **bad data**, not real winds: they come from two corrupted Vandenberg soundings, see [§9](#9-high-altitude-winds-noaa-igra2-radiosondes). They are still in the table and the statistics above. Without those two launches the largest value anywhere is about 281 km/h, at 12 km.

Success rate by rocket type:

| `rocket_type` | Launches | Failures | Success rate |
|---|---|---|---|
| Falcon 9 | 701 | 4 | 0.994 |
| Starship | 14 | 5 | 0.643 |
| Falcon Heavy | 14 | 0 | 1.000 |
| Starship Prototype | 9 | 3 | 0.667 |
| Falcon 1 | 5 | 3 | 0.400 |

### 7.4 Missing values

| Column(s) | Missing | Cause |
|---|---|---|
| `payload_mass_kg` | **26 of 743 (3.5%)** | No GCAT mass: Starship and Starship Prototype (23, GCAT has no real payload value), the 2016 Falcon 9 pad explosion, the 2020 Crew Dragon abort test (GCAT lists 0, stored as null), and the newest launch, not yet in GCAT. See [§8](#8-gcat-payload-mass) |
| `payload_ratio` | **743 of 743 (100%)** | Placeholder: needs a rocket capacity column that does not exist yet |
| `upper_wind_sounding_time`, `_offset_h`, `upper_wind_top_km`, `upper_wind_max_kmh`, `upper_wind_max_alt_km` | **38 of 743 (5.1%)** | No radiosonde within 12 h. 28 are 2026 launches from February to May (23 of them in April and May: Cape Kennedy has 1 sounding in April and none in May, Vandenberg none in either month), plus the 2026-10-31 launch, which has no sounding published yet. The other 9 are 2 in August 2025, 2 in July 2022, 2 in 2008, and one each in 2009, 2013 and 2021. See [§9](#9-high-altitude-winds-noaa-igra2-radiosondes) |
| `upper_wind_speed_<h>km_kmh`, `upper_wind_dir_<h>km_deg` | **39 of 743 at 2 km, rising to 137 (18.4%) at 30 km** | The 38 above, plus balloons that burst before reaching `<h>`. Counts per height are in the `eda.py` output |
| All other columns | 0 | Weather is now present for every launch |

The left join keeps launches with a missing value and leaves the columns empty, as the [§2](#2-missing-data-policy) interim rule asks (do not drop rows). The two newest launches that used to have no weather now have it; the 2026-10-31 launch (`57ce0a39-d035-4f16-a418-bd6108f78199`) still has no upper-air winds.

### 7.5 Correlation with launch outcome

Pearson correlation between each numeric feature and `mission_success` coded 0/1 (point-biserial). Computed on launches that have a value for the feature. The duplicate `latitude` and `longitude` columns are left out.

| Feature | n | Failures in n | Pearson r |
|---|---|---|---|
| `launchpad_latitude` | 743 | 15 | 0.279 |
| `launchpad_longitude` | 743 | 15 | -0.253 |
| `wind_speed_10m` | 743 | 15 | -0.097 |
| `high_altitude_wind_assumed` | 743 | 15 | -0.097 (identical copy of the above) |
| `temperature_2m` | 743 | 15 | -0.068 |
| `precipitation` | 743 | 15 | 0.019 |
| `cloud_cover` | 743 | 15 | 0.012 |
| `payload_mass_kg` | 717 | 6 | 0.107 |
| `upper_wind_max_kmh` | 705 | 13 | 0.014 |
| `upper_wind_speed_10km_kmh` | 704 | 13 | 0.018 |
| `upper_wind_speed_20km_kmh` | 698 | 13 | 0.052 |
| `upper_wind_speed_30km_kmh` | 606 | 11 | 0.027 |
| `upper_wind_station_distance_km` | 743 | 15 | -0.436 |
| `wind_speed_ratio` | 743 | 15 | undefined (constant 1) |
| `payload_ratio` | 0 | 0 | undefined (no values) |

How to read this:

- **Weather is weakly related to the outcome.** All four weather features have |r| below 0.10. With 15 failures, that is within what chance could produce, so these numbers are not evidence either way.
- **Latitude and longitude are proxies for the rocket program, not geography.** The largest values (|r| 0.25 to 0.28) coincide with Falcon 1 flying from Kwajalein (9.05, 167.74; 3 failures in 5 launches) and Starship and its prototypes flying from the Texas pad near 26.0, -97.2 (8 failures in 23 launches). Do not read them as "pad location causes failure".
- **Payload mass is weakly related to the outcome** (r = 0.107, 6 failures among 717 launches). It also tracks the rocket: Falcon 1 carries tens of kg and Falcon 9 about 15 t, so it largely reflects which rocket flew, not payload weight on its own. The Starship flights have no value, so the Starship failures are not in this number.
- **Upper-air winds show no relationship with the outcome.** Every `upper_wind_*` speed and direction column has |r| below 0.06, and only 11 to 13 failures have a value. That is within chance, so it is not evidence either way. The `upper_wind_*` rows above are a sample; `eda.py` prints all 30 columns.
- **`upper_wind_station_distance_km` (r = -0.436) is a pad proxy, not a cause.** The distance is nearly fixed per pad (Cape 11 to 17 km, Vandenberg 14 km, Brownsville 28 km, Kwajalein 35 km), so it only identifies the pad, and with it the rocket program. Do not use it as a feature.
- **`wind_speed_ratio` and `payload_ratio` cannot be analysed** yet. `wind_speed_ratio` needs to be pointed at a real upper-air wind instead of the placeholder, and `payload_ratio` needs a rocket capacity column.

### 7.6 Discrepancy between the two processed tables

Two scripts on `main` produce different tables from the same raw files. This report uses the feature builder's table.

| | Feature builder (`build_features.py`): **used here** | Cleaner (`clean_data.py`) |
|---|---|---|
| Output file | `data/processed/ml_features.csv` | `data/interim/cleaned_launches.csv` |
| Rows | 743 (left join keeps launches with no weather) | 743 (inner join, but every launch now has weather, so none are lost. It would still drop any launch without a weather record; before the weather fix it lost two) |
| Columns | 56 | 51 |
| Wind units | km/h, unconverted | Surface wind and `high_altitude_wind_assumed` in m/s (÷ 3.6). The `upper_wind_*` columns pass through unchanged in km/h, which the column names still say |
| Column names | Source names (`wind_speed_10m`) | Unit suffixes (`wind_speed_10m_ms`, `temperature_2m_c`) |
| Extra columns | `wind_speed_ratio`, `payload_ratio`, duplicate `launch_time` / `latitude` / `longitude` | None |
| Dropped rows | None | Drops any row missing a required value, which conflicts with the [§2](#2-missing-data-policy) "do not drop rows" rule |

Neither script reads the other's output. Correlation values match on either table (a change of unit does not alter Pearson r).

### 7.7 Delay analysis: not done

The issue asks for correlations against launch delays. **LL2 has no delay field** and the baseline for computing one is not defined ([§3.3](#33-launch-object-fields), milestone 1 in [`DELIVERABLES.md`](DELIVERABLES.md)), so this report uses the mission outcome instead. Delay correlations are pending a PM's definition of delay.

### 7.8 Still to document

Documentation for the physics data has not been added to this file yet.

---

## 8. GCAT payload mass

`payload_mass_kg` in `data/raw/spacex_launches.csv` comes from GCAT, not LL2. LL2 had a payload mass for only 10 of 742 launches (checked 2026-10-31).

| Item | Detail |
|---|---|
| Source file | GCAT launch log, `https://planet4589.org/space/gcat/tsv/launch/launch.tsv`, saved unmodified as `data/raw/gcat_launch.tsv` |
| Format | Tab-separated. The first line is the header (starts with `#`) and the second is `# Updated ...`. No API |
| Field used | `OrbPay` ("Orbital Payload"): payload delivered to orbit (perigee above 80 km) for the whole launch. **Unit: metric tonnes**, confirmed in GCAT's [launch list column explanations](https://www.planet4589.org/space/gcat/web/launch/lcols.html). The fetcher multiplies by 1000 to get kg |
| Join to LL2 | GCAT has no LL2 ids. `fetch_spacex.py` matches each LL2 `net` to the nearest GCAT **Falcon** launch time within 2 hours |
| Replaces LL2? | Yes, completely. LL2 values are discarded, not used as a fallback |

**Coverage (checked 2026-10-31, 743 launches):** 717 have a GCAT mass and 26 are null, per the [missing-data policy](#2-missing-data-policy) (never filled with 0). All Falcon 1 and Falcon Heavy launches and nearly all Falcon 9 launches match. The null ones are:

- **Starship and Starship Prototype (23):** not matched. GCAT lists these flights, but `OrbPay` is 0 for the early prototype hops and 120 t for the later flights, which looks like the vehicle's capacity rather than a real payload.
- **Falcon 9 (3):** the 2016-09-03 pad explosion (never reached orbit, so not in GCAT), the 2020-01-19 Crew Dragon in-flight abort test (GCAT lists 0 because nothing reached orbit, so it is stored as null), and the newest launch, which GCAT had not logged yet.

**Cautions:**

- Where LL2 and GCAT both had a value (10 launches), 7 agreed within 10%.
- GCAT may revise a launch's mass after the fact. Delete the cached `data/raw/gcat_launch.tsv` and re-run the fetcher to pick up updates.

### 8.1 License and attribution

GCAT is released under CC BY. Credit it wherever results are shown, for example in the dashboard footer or report: "data from GCAT (J. McDowell, planet4589.org/space/gcat)". The license was read from the GCAT site and is not yet confirmed by a PM: **TBD.**

---

## 9. High-altitude winds (NOAA IGRA2 radiosondes)

The `upper_wind_*` columns in `data/raw/historical_weather.csv` hold measured winds from the ground to about 30 km. Open-Meteo cannot supply them: its ERA5 archive endpoint returns nothing for pressure levels, and its historical-forecast endpoint has them only from about mid-2022 ([§4.5](#45-data-availability)). They are added by `src/data/fetch_weather.py`.

| Item | Detail |
|---|---|
| Source | NOAA NCEI Integrated Global Radiosonde Archive 2: `https://www.ncei.noaa.gov/pub/data/igra/data/data-por/<STATION>-data.txt.zip`. Saved unmodified in `data/raw/igra/` |
| Format | Fixed-width text. A header line per sounding (`#`, station, date, nominal hour) followed by one line per level. Wind speed is in **tenths of m/s**, height is geopotential height in m, direction is in degrees, and `-9999` means missing |
| Stations | `USM00074794` Cape Kennedy (Cape Canaveral and KSC pads, 11 to 17 km away), `USM00072393` Vandenberg AFB (14 km), `USM00072250` Brownsville (Starbase, 28 km), `RMM00091366` Kwajalein (35 km). Each pad uses its nearest station |
| Timing | Balloons are released about 00 and 12 UTC. For each launch the script takes the sounding closest in time within **12 h**, preferring one that reaches at least 20 km over a nearer one that bursts lower. The gap averages 3.5 h and is at most 12 h |
| Heights | Winds are interpolated to every 2 km from 2 to 30 km above sea level. Direction is interpolated through the east-west and north-south wind components, so a wind near north does not average to south. Heights above the balloon's top are left blank, never extrapolated |
| Units | Speeds in **km/h** (m/s × 3.6), to match `wind_speed_10m`. Directions are the direction the wind blows from |

**Coverage (checked 2026-10-31, 743 launches):** 705 have a sounding and 38 do not ([§7.4](#74-missing-values)). Balloons reach a median of 32 to 34 km at the three US stations and 26 km at Kwajalein (only 2 launches have a sounding there). Speeds were reported for 704 launches at 10 km, 698 at 20 km and 606 at 30 km.

**Cautions:**

- **Not at the pad.** The station is up to 35 km away, and the balloon drifts downwind as it climbs, so the wind is the profile near the station and not exactly along the rocket's path.
- **Not at launch time.** The sounding can be up to 12 h from liftoff.
- **IGRA2 has gaps.** There are no soundings for April and May 2026, and the newest days are not published yet. Re-run `fetch_weather.py` later to fill recent launches. Delete the cached zip to pull a fresh copy.
- **Two corrupted soundings are in the data.** Vandenberg's 2024-10-30 12 UTC and 2024-12-05 00 UTC soundings contain levels with winds of about 110 to 137 m/s (400 to 490 km/h) sitting beside neighbouring levels of 5 to 20 m/s. For example, at 6 km the 2024-12-05 sounding reports 111.1 m/s while the levels around it report 7 to 9 m/s. That is not physical: the strongest winds in a real jet stream are about 100 to 150 m/s, and only near 10 to 12 km, never as isolated spikes from one level to the next. The pattern looks like a scaling error in the source file (values about 10 times too large). Both soundings are used by the launches on 2024-10-30 and 2024-12-05, and those launches' `upper_wind_*` values are **unreliable**. A spike check (a level more than 30 m/s from the median of its 4 nearest levels) flags 6 of the 683 soundings used: these two (31 and 38 spike levels) and 4 others with 1 to 4 levels each (one 2020 and one 2023 Cape sounding, two Vandenberg soundings from 2026). Those four have not been examined. Not yet fixed in `fetch_weather.py`.
- **Largest believable values.** With the two corrupted soundings set aside, the strongest wind in the table is 281.5 km/h (78 m/s at 12 km, Cape Kennedy, 2025-01-07), a normal winter jet-stream value. 400 km/h is possible only in a few rare record-strength jets, not at 6 km or 28 km.
- **Kwajalein is thin.** Only 2 of its 5 launches (2006 and 2007) have a sounding; the three from 2008 and 2009 have none.
- **Placeholder still in use.** `high_altitude_wind_assumed` and `wind_speed_ratio` have **not** been switched to these winds.

### 9.1 License and attribution

IGRA2 is a NOAA NCEI product. Credit it wherever results are shown, for example "Integrated Global Radiosonde Archive, NOAA NCEI". No license or use restriction appears in the IGRA2 readme (checked 2026-10-31); the NCEI product page returned no text to check. NOAA data is generally free to use, but the terms have not been confirmed by a PM: **TBD.**

### 9.2 Open question for the PM: corrupted soundings

**Decision needed (TBD, for a PM):** what to do about the corrupted Vandenberg soundings described in [§9](#9-high-altitude-winds-noaa-igra2-radiosondes). Nothing has been changed yet, so the two launches on 2024-10-30 and 2024-12-05 still carry unreliable `upper_wind_*` values, and every statistic in this file that includes the `upper_wind_*` columns includes them.

| Option | What it does | Cost |
|---|---|---|
| **A. Drop the spike levels (suggested)** | Remove any level more than 30 m/s from the median of its 4 nearest levels before interpolating, and add an `upper_wind_levels_dropped` column so affected launches can be found. The raw IGRA2 file stays untouched | Needs a re-run of `fetch_weather.py`, which makes one Open-Meteo request per launch (743). The 30 m/s threshold is a judgment call and could remove real wind shear |
| **B. Blank the two launches' upper winds** | Set every `upper_wind_*` value to null for those two soundings | Loses the usable levels. Needs the same re-run |
| **C. Leave as is** | Keep the values and document the problem | Bad values stay in any model trained on these columns |

Also open: four other soundings are flagged with 1 to 4 spike levels each (Cape Kennedy 2020-01-19 and 2023-03-02, Vandenberg 2026-01-25 and 2026-03-26). They have not been examined and some may be real wind shear, so check them before choosing a threshold.

**API limit:** the re-run is held until the PM decides. Open-Meteo's free tier allows 600 calls a minute and under 10,000 a day ([§4.4](#44-rate-limits-free-tier)), so one full run is well inside it. The IGRA2 zips are cached in `data/raw/igra/` and are not downloaded again.
