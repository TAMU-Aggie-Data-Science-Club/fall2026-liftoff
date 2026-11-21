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
10. [Open questions for the PM](#10-open-questions-for-the-pm)

> Status: only Launch Library 2, Open-Meteo, GCAT (payload mass only) and NOAA IGRA2 (upper-air winds only) are documented so far. The earlier SpaceX community API was dropped (archived and unreachable). LL2 covers every provider, but `fetch_spacex.py` requests **SpaceX launches only** (`lsp__id=121`), so the NASA / other-provider delay rule in [`MODELING.md`](MODELING.md) §2 has no launches to apply to yet. NASA Space Shuttle data and CelesTrak / Space-Track TLEs (listed in [`DELIVERABLES.md`](DELIVERABLES.md)) will be added in later issues.

---

## 1. Source register

| Source | Origin / URL | Access method | License | Sensitivity | Notes |
|---|---|---|---|---|---|
| Launch Library 2 (LL2) API | `https://ll.thespacedevs.com/2.3.0` ([docs](https://thespacedevs.com/llapi), by The Space Devs) | Public HTTPS GET, JSON, no auth (free tier) | No named licence. The Space Devs' terms: free to use in any way, attribution optional but encouraged ([§3.4](#34-licensing)) | Public, no PII | Free tier is **15 unauthenticated requests per hour**. Covers all providers and historical launches; we fetch SpaceX only. Also the source of the schedule notes (`updates`) behind the delay label. Replaces the SpaceX community API. |
| Open-Meteo Historical Weather API | `https://archive-api.open-meteo.com/v1/archive` | Public HTTPS GET, JSON, no key (free tier) | CC BY 4.0. The free API is for **non-commercial use only** | Public, no PII | Attribution required: a "Weather data by Open-Meteo.com" link wherever the data is shown ([§4.6](#46-licensing-and-attribution)). Backed by ERA5 / ERA5-Land reanalysis. Surface variables only: the archive endpoint returns nothing for pressure levels. `fetch_weather.py` falls back to `https://historical-forecast-api.open-meteo.com/v1/forecast` for launches the archive cannot serve yet. |
| NOAA NCEI IGRA2 (Integrated Global Radiosonde Archive) | `https://www.ncei.noaa.gov/pub/data/igra/`. We download `data/data-por/<STATION>-data.txt.zip` | Plain HTTPS download of a zipped fixed-width text file per station (no API, no auth). Cached to `data/raw/igra/` | No licence stated by NCEI; U.S. federal government data, provided without warranty ([§9.1](#91-license-and-attribution)) | Public, no PII | **Source of the `upper_wind_*` columns**; see [§9](#9-high-altitude-winds-noaa-igra2-radiosondes). Measured balloon winds, about 2 soundings a day per station. Credit NOAA NCEI where shown. |
| GCAT (General Catalog of Artificial Space Objects) | `https://planet4589.org/space/gcat/` by Jonathan McDowell. We download the launch log `https://planet4589.org/space/gcat/tsv/launch/launch.tsv` | Plain HTTPS download of a TSV file (no API, no auth). Cached to `data/raw/gcat_launch.tsv` | CC BY 4.0 (stated on the GCAT site) | Public, no PII | **Source of `payload_mass_kg` only**; see [§8](#8-gcat-payload-mass). Citation required: "data from GCAT (J. McDowell, planet4589.org/space/gcat)". |

---

## 2. Missing-data policy

Decided 2026-11-17:

- **Text, labels and other values the model does not compute with** (for example `rocket_type`, `upper_wind_station`, `weather_source`): a gap is fine. Store it as `null` and keep the launch.
- **A missing number the model uses:** the launch is **left out of training and evaluation**. A launch cannot be modelled without the numbers it needs. Only the model's numeric inputs count (`NUMERIC_FEATURES` in `train_model.py`, `RF_NUMERIC_FEATURES` for the RandomForest). A gap in a column the model does not use, such as a fixed-height wind, does not remove the launch.
- **Exception: optional inputs** (`OPTIONAL_NUMERIC_FEATURES` in `train_model.py`). A launch missing one is kept, and the input stays blank; both models handle a blank natively. Today this is only `low_weather_go`, which most launches lack a week out (decided 2026-11-21, [§7.10](#710-weather-go-forecasts-checked-2026-11-18)).
- **Never fill a missing number** with 0 or any other value. Keep it as `null` (JSON `null` / pandas `NaN`).
- **The pipeline keeps every row.** The fetchers and `build_features.py` do not drop launches; the drop happens when the models load the data (`usable_launches()` in `train_model.py`), and the scripts print how many launches were left out and why. That way a gap that gets filled later (for example, NOAA publishing a late sounding) brings the launch back on the next fetch.
- Which columns are model inputs is set by the feature list, which the EDA ([§7.8](#78-recommendations)) may change. The rule follows that list automatically.

---

## 3. Launch Library 2 API

LL2 is a community-run launch database from The Space Devs. It covers launches from every provider and goes back to 1957, so it can also supply the historical comparison. Fields below were read from a live response (`/2.3.0/launches/?limit=1&mode=detailed`, checked 2026-10-22). Anything not seen in that response is marked **TBD**.

### 3.1 Endpoints

| Endpoint | Returns | Status |
|---|---|---|
| `GET /2.3.0/launches/` | Paginated list of all launches (past and upcoming) | Verified live |
| `GET /2.3.0/launches/{id}/` | One launch (`id` is a UUID) | Assumed from the `url` field in responses: **TBD** |
| `launches/previous` | Past launches only | Verified: `fetch_spacex.py` uses it |
| `launches/upcoming` | Future launches only | Not used; assumed from API convention |
| `pad`, `rocket.configuration`, `launch_service_provider`, `mission` | Embedded in each launch when `mode=detailed` | Verified live |

Base URL: `https://ll.thespacedevs.com`. Auth: none. Responses: JSON. Use `?mode=detailed` to get the nested objects shown below.

Pagination envelope: `count` (total matches, 8130 at time of check), `next` and `previous` (URLs, `null` at the ends), `results` (array). Page size is set with `limit` and `offset`. `fetch_spacex.py` uses `limit=100`; larger values are untested. With `mode=detailed`, pages of 100 sometimes time out (HTTP 504, seen 2026-11-17); re-running later worked.

### 3.2 Rate limits

The free tier allows **15 unauthenticated requests per hour** ([source](https://thespacedevs.com/llapi)); higher rates need a paid plan. A SpaceX-only pull is about 8 requests. A full pull of ~8,000 launches would take many pages, so it must be spread over several hours. Fetch once, keep the output in `data/raw/`, and avoid re-polling. The Space Devs also run a development API with no rate limit but stale data, and an API key (via Patreon) raises the limit.

### 3.3 Launch object fields

Types and examples are from the live response. "Nullable" is only marked where `null` was seen; other fields may also be `null` (**TBD**). Units are noted where the response or name makes them clear.

| Field | Type | Nullable | Unit / format | Notes |
|---|---|---|---|---|
| `id` | string (UUID) | no | | Primary key |
| `name` | string | no | | `"<Rocket> \| <Mission>"` |
| `slug`, `url` | string | no | | |
| `launch_designator` | string | maybe | COSPAR, e.g. `1957-001` | |
| `status` | object | no | `id`, `name`, `abbrev`, `description` | Launch outcome. `fetch_spacex.py` maps `id 3` (Success) to `mission_success = True` and `id 4` (Failure) / `id 7` (Partial Failure) to `False`; any other status is null. No longer the model target: the model predicts delay ([`MODELING.md`](MODELING.md) §2) |
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
| `updates` | array | | `comment`, `created_on` (ISO 8601, UTC), ... | Schedule notes posted over time (e.g. "Now targeting Nov 05 at 02:35 UTC"). Saved by `fetch_spacex.py` to `data/raw/spacex_launch_updates.csv` and used to build the delay label |
| `webcast_live`, `vid_urls`, `info_urls`, `image`, `mission_patches`, `timeline`, `program`, `hashtag`, `infographic`, `flightclub_url` | various | | | Media and metadata. Not model features |

**Delay is not a field.** LL2 has no "delay" value, and a normal request returns only the latest `net`. The schedule history comes from the `updates` notes instead: `train_model.py` parses the target dates in them and compares the actual launch with the baseline target. The definition (baseline, and 3 days for SpaceX / 7 days for other providers) is in [`MODELING.md`](MODELING.md) §2. Only launches with early-enough notes get a label: 362 of 745 on the 2026-11-17 fetch, all from 2020-12-19 onward.

### 3.4 Licensing

No licence is named. The Space Devs' terms ([FAQ](https://github.com/TheSpaceDevs/Tutorials/blob/main/faqs/faq_TSD.md), checked 2026-11-17) apply to all Launch Library 2 data:

- The data is free to use "in any way, shape, or form", and you may share what you build with it. They ask that you don't just forward the data on without adding value.
- **Attribution is optional** ("not mandatory, but is encouraged and appreciated"). Suggested credit where shown: "Launch data from Launch Library 2 by The Space Devs (thespacedevs.com)".
- Accuracy is not guaranteed, and they ask users to cache results rather than query the API repeatedly.

### 3.5 If a data point is missing

Follow the [missing-data policy](#2-missing-data-policy). Cases to expect:

- `status` for upcoming launches has no outcome yet: these have no label and are excluded from training.
- `failreason` uses `""` rather than `null` for "none". Treat it as "no failure reason", not as a missing value.
- `probability`, `weather_concerns`, `net_precision` and the rocket capacity/size numbers can be `null`. None of them is a model input, so a gap does not remove the launch.
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
| `wind_speed_unit` | no | not passed, so **`kmh`** (the default) | `fetch_weather.py` does not set it, so wind speeds arrive in km/h. See [§5](#5-unit-conversions) |
| `precipitation_unit` | no | `mm` (default) | |
| `timeformat` | no | `iso8601` (default) | |
| `timezone` | no | `GMT` (default) | Keep UTC so it matches `net` |

Example (Cape Canaveral area, tested):

```
https://archive-api.open-meteo.com/v1/archive?latitude=28.5729&longitude=-80.649&start_date=2020-05-30&end_date=2020-05-30&hourly=temperature_2m,wind_speed_10m,cloud_cover
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
| `wind_speed_10m` | float | **km/h** | Open-Meteo default; the fetcher does not change it |
| `wind_speed_100m` | float | **km/h** | Same |
| `wind_gusts_10m` | float | **km/h** | Same |
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

Checked 2026-11-17 against the [licence](https://open-meteo.com/en/licence) and [terms](https://open-meteo.com/en/terms) pages:

- **Licence:** API data is CC BY 4.0. Give credit, link to the licence, and say if the data was changed.
- **Required credit:** a link next to any place Open-Meteo data is shown, for example in the dashboard footer: [Weather data by Open-Meteo.com](https://open-meteo.com/).
- **Free API is non-commercial only.** Educational and non-profit use without subscriptions or ads is allowed. Commercial use needs a paid plan. Free-tier limits are in [§4.4](#44-rate-limits-free-tier).
- **Underlying data:** Open-Meteo lists the Copernicus Climate Change Service (C3S) as its reanalysis source. Where results are shown, also include "Generated using Copernicus Climate Change Service information".
- **Citation (optional, for reports):** Zippenfenig, P. (2023). Open-Meteo.com Weather API [Computer software]. Zenodo. https://doi.org/10.5281/ZENODO.7970649

### 4.7 If a data point is missing

Follow the [missing-data policy](#2-missing-data-policy): missing numbers stay `null`, and a launch missing a weather value the model uses is left out of training. **How Open-Meteo marks a missing hourly value is not stated in its docs: TBD.** JSON `null` is expected; confirm by checking a response for dates near the 5-day lag and treat any array element that is `null` as missing. Also expect gaps when a launch date is too recent or the launch time is imprecise (`net_precision`).

---

## 5. Unit conversions

> ## ⚠️ CONVERSIONS REQUIRED ⚠️
> The raw data is **not** in SI. The physics code works in **SI** (see [`PHYSICS.md`](PHYSICS.md) and `src/physics/constants.py`). **Convert at the `raw` → `interim` step and never edit `raw/`.** Do not mix units inside a column; if a column is converted, the new column name or documentation must say so.

| Quantity | Stored in `raw/` as | Convert to | How |
|---|---|---|---|
| Wind speed (`wind_speed_*`, `wind_gusts_*`, `upper_wind_*_kmh`) | km/h | m/s | ÷ 3.6 |
| Air temperature (`temperature_2m`, `dew_point_2m`) | °C | K | + 273.15 |
| Pressure (`pressure_msl`, `surface_pressure`) | hPa | Pa | × 100 |
| Precipitation | mm | m (if needed) | ÷ 1000 |
| Wind direction | degrees | radians (if needed) | × π / 180 |
| Time (`net`, `window_*`) | ISO 8601 string (UTC) | datetime (UTC) | `pd.to_datetime(x, utc=True)` |
| Relative humidity, cloud cover | % | fraction (if needed) | ÷ 100 |

**All wind speeds in `raw/` are km/h.** Open-Meteo's surface winds arrive in its default unit, km/h, because `fetch_weather.py` does not pass `wind_speed_unit`. The IGRA2 radiosonde winds are stored in the source file in tenths of m/s; the fetcher divides by 10 and multiplies by 3.6, so the `upper_wind_*` columns are km/h too (checked 2026-11-17: surface wind median 12.8, peak upper wind median 118.4, both plausible in km/h). `clean_data.py` converts the surface winds to m/s with ÷ 3.6. The models use km/h, and `src/physics/trajectory.py` converts its m/s inputs to km/h (× 3.6) before calling the model.

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
| `data/raw/` | Fetcher outputs: `spacex_launches.csv` and `spacex_launch_updates.csv` (from LL2), `historical_weather.csv` (Open-Meteo + IGRA2). Also holds `gcat_launch.tsv`, the GCAT launch log exactly as downloaded ([§8](#8-gcat-payload-mass)), and `igra/`, the zipped IGRA2 station files ([§9](#9-high-altitude-winds-noaa-igra2-radiosondes)) | **Immutable.** Never edit by hand; re-fetch instead. Units are source units (km/h, °C, hPa). |
| `data/interim/` | Intermediate outputs: unit conversions ([§5](#5-unit-conversions)), type fixes, LL2 launches joined to weather by pad coordinates and time | Reproducible from `raw/` by a tracked script. Safe to delete and regenerate. |
| `data/processed/` | Final feature tables for the XGBoost models and the dashboard | Reproducible from `interim/`. This is what training and the app read. |

Flow: `raw/` → `interim/` → `processed/`. Data only moves forward, and each step is a tracked script or notebook so any teammate can rebuild every folder from scratch.

File names are the ones the scripts write:

| File | Written by |
|---|---|
| `data/raw/spacex_launches.csv`, `data/raw/spacex_launch_updates.csv`, `data/raw/gcat_launch.tsv` | `fetch_spacex.py` |
| `data/raw/historical_weather.csv`, `data/raw/igra/<STATION>-data.txt.zip` | `fetch_weather.py` |
| `data/interim/cleaned_launches.csv` | `clean_data.py` |
| `data/processed/ml_features.csv` | `build_features.py` (what the models read) |

Because `data/` is git-ignored, nobody gets `gcat_launch.tsv` or the IGRA2 zips from the repo. `fetch_spacex.py` downloads the GCAT file and `fetch_weather.py` downloads the IGRA2 zips the first time they run, and both reuse the local copy after that. Delete a file to pull a fresh copy. The Cape Kennedy zip is about 50 MB (230 MB unzipped), so the first weather run is slow.

---

## 7. EDA report: SpaceX launch feature table

Produced by `python src/data/eda.py` (run 2026-11-18 on the 746-launch fetch). The target is the **delay label** `is_delayed` from `train_model.py` ([`MODELING.md`](MODELING.md) §2), so the EDA and the model use exactly the same labels. The script prints every table below. It writes nothing except a cache of the weather at each launch's target time (`data/interim/eda_target_weather.csv`, see [§7.5](#75-features-vs-delay)); delete the cache to re-fetch.

> **Pipeline:** the input, `data/processed/ml_features.csv`, is written by `src/data/build_features.py`. A separate cleaning script, `src/data/clean_data.py`, writes a different table to `data/interim/cleaned_launches.csv`; see [§7.9](#79-discrepancy-between-the-two-processed-tables).

### 7.1 Pipeline schema

```
LL2 API          --fetch_spacex.py-->  data/raw/spacex_launches.csv        (746 rows, 7 columns)
                                       data/raw/spacex_launch_updates.csv  (schedule notes; read by train_model.py for the delay label)
Open-Meteo API   --fetch_weather.py--> data/raw/historical_weather.csv     (746 rows, 47 columns)
NOAA IGRA2       --/                   (upper-air winds are added by the same script)
                          |
                    build_features.py: left join on launch_id (one-to-one), check that
                    time and coordinates agree
                          v
                 data/processed/ml_features.csv                            (746 rows, 53 columns)
```

Each launch has at most one weather record: the hourly value closest to the **actual** launch time (`net`), at the pad coordinates. Units are source units (see [§7.2](#72-feature-table-columns)). File names are listed in [§6](#6-storage-layout-data).

### 7.2 Feature table columns

| Column | Type | Unit / format | Notes |
|---|---|---|---|
| `launch_id` | string (UUID) | | LL2 `id`. Join key |
| `rocket_type` | string | | LL2 `rocket.configuration.name` (e.g. `Falcon 9`) |
| `payload_mass_kg` | float | kg | Payload delivered to orbit, from GCAT ([§8](#8-gcat-payload-mass)). See [§7.3](#73-missing-values) for gaps |
| `launchpad_latitude`, `launchpad_longitude` | float | degrees, WGS84 | LL2 `pad`. 7 distinct pad coordinates |
| `launch_timestamp_utc` | string | ISO 8601, UTC | LL2 `net` (latest value, not the original schedule) |
| `mission_success` | boolean | | Launch outcome. **Not the model target**; the delay label `is_delayed` is computed in `train_model.py`, not stored in this table. `True` = LL2 status 3. `False` = status 4 (failure) or 7 (partial failure) |
| `launch_time`, `latitude`, `longitude` | string / float | UTC / degrees | Copies of the launch time and pad coordinates, repeated by the weather file. Verified equal to the launch columns by the builder |
| `weather_time` | string | ISO 8601, UTC | Hourly weather record used |
| `temperature_2m` | float | °C | Air temperature at 2 m, at the actual launch time |
| `wind_speed_10m` | float | **km/h** | Surface wind at the actual launch time. See [§5](#5-unit-conversions) |
| `precipitation` | float | mm | Over the preceding hour |
| `cloud_cover` | float | % | |
| `weather_source` | string | | `era5_archive` or `historical_forecast` ([§4.5](#45-data-availability)). All 746 rows are `era5_archive` |
| `upper_wind_station`, `upper_wind_station_distance_km` | string / float | IGRA2 id / km | Radiosonde station used for the pad and its distance from the pad (11 to 35 km, see [§9](#9-high-altitude-winds-noaa-igra2-radiosondes)) |
| `upper_wind_sounding_time`, `upper_wind_sounding_offset_h` | string / float | ISO 8601 UTC / hours | The balloon launch used, and how far it is from the rocket launch (negative = balloon earlier). At most 12 h |
| `upper_wind_top_km` | float | km | Highest height the balloon reported a wind at |
| `upper_wind_max_kmh`, `upper_wind_max_alt_km` | float | **km/h** / km | Peak wind at or below 30 km and the height where it occurred (usually the jet stream) |
| `upper_wind_speed_<h>km_kmh`, `upper_wind_dir_<h>km_deg` | float | **km/h** / degrees | Wind speed and the direction it blows **from** (0 = north, 90 = east), at `<h>` = 2, 4, ... 30 km above sea level. Blank where the balloon did not reach `<h>` |

**Removed columns (2026-11-18):** `high_altitude_wind_assumed`, `wind_speed_ratio` and `payload_ratio` are no longer produced.

- `high_altitude_wind_assumed` was a stand-in for the high-altitude wind the weather fetcher was first asked for (Issue #3), which Open-Meteo could not supply (PR #17). It started as surface wind × 1.5 and then became a plain copy of `wind_speed_10m`. The measured `upper_wind_*` columns ([§9](#9-high-altitude-winds-noaa-igra2-radiosondes)) now cover that need.
- `wind_speed_ratio` was `high_altitude_wind_assumed / wind_speed_10m`, so it was always 1. Rebuilt from a real upper wind (`upper_wind_max_kmh / wind_speed_10m`), it mostly tracks 1 / surface wind (r = 0.89, AUC 0.44 for delays) and runs up to 188, so it adds nothing beyond `wind_speed_10m`.
- `payload_ratio` needed a rocket capacity column that never existed. LL2 does publish capacities per rocket variant (`leo_capacity`, e.g. Falcon 9 Block 5: 22,800 kg, checked 2026-11-18), but 342 of the 367 delay-labelled launches are Falcon 9, so the ratio would be payload mass divided by a near-constant. Those capacities are also for an expendable rocket in LEO, which fits neither reused boosters nor GTO payloads ([§8](#8-gcat-payload-mass)).

### 7.3 Missing values

| Column(s) | Missing (of 746) | Cause |
|---|---|---|
| `payload_mass_kg` | 29 | No GCAT mass: Starship and Starship Prototype (GCAT has no real payload value), the 2016 pad explosion, the 2020 Crew Dragon abort test, and the newest launches not yet in GCAT ([§8](#8-gcat-payload-mass)) |
| `upper_wind_max_kmh` and the other per-sounding columns | 39 | No radiosonde within 12 h (mostly 2026 launches in months IGRA2 has not published), plus the 2 launches blanked for corrupted soundings ([§9.2](#92-corrupted-soundings-decided)) |
| `upper_wind_speed_<h>km_kmh` | 40 at 2 km, rising to 137 at 30 km | The above, plus balloons that burst before reaching `<h>` |
| All other columns | 0 | |

The table keeps every launch; under the missing-data policy the **models** leave out launches missing a numeric input ([§2](#2-missing-data-policy)).

### 7.4 Delay labels and delay rates

367 of the 745 launches (Amos-6 excluded) have a delay label; 80 (22%) were delayed (more than 3 days past the baseline target). Labels start in December 2020, when LL2's schedule notes begin ([`MODELING.md`](MODELING.md) §2).

**Delays are becoming rarer.** This is the strongest pattern in the data:

| Year | Labelled | Delayed | Delay rate |
|---|---|---|---|
| 2021 | 13 | 4 | 31% |
| 2022 | 40 | 15 | 38% |
| 2023 | 66 | 16 | 24% |
| 2024 | 87 | 27 | 31% |
| 2025 | 78 | 10 | 13% |
| 2026 | 82 | 8 | 10% |

(2020: 1 launch, on time.) A model trained on older launches will over-predict delays for recent ones, and the newest launches, which form the test set, have few delays.

By rocket and pad there is little difference: Falcon 9 22% (342 launches), Falcon Heavy 25% (8), Starship 13% (15); Cape Canaveral SLC-40 22% (157), Vandenberg SLC-4E 24% (130), Kennedy LC-39A 17% (63). Starbase has too few labelled launches (17) to judge. By target month the rate ranges from 15% (June) to 32% (July) with 22 to 39 launches per month, which is within chance.

### 7.5 Features vs delay

For each feature: the median for on-time and delayed launches, and the **single-feature AUC**, the chance that a random delayed launch has a higher value than a random on-time one. 0.5 means no signal; the further from 0.5 in either direction, the more signal. With 80 delays, an AUC within about 0.43 to 0.57 is consistent with chance.

**Current model inputs and launch-time weather** (only known at liftoff):

| Feature | n | Median on time | Median delayed | AUC |
|---|---|---|---|---|
| `wind_speed_10m` (km/h) | 367 | 12.1 | 15.4 | **0.59** |
| `payload_mass_kg` | 347 | 15,000 | 15,750 | 0.52 |
| `upper_wind_max_kmh` | 347 | 114.8 | 118.4 | 0.50 |
| `upper_wind_speed_10km_kmh` / `12km` | 346 | 74.0 / 93.6 | 68.5 / 86.4 | 0.48 / 0.48 |
| `temperature_2m`, `cloud_cover`, `precipitation` | 367 | | | 0.48 to 0.49 |

**Schedule features** (built in `eda.py`, all known when the baseline note was posted, about a week before launch):

| Feature | What it is | n | Median on time | Median delayed | AUC |
|---|---|---|---|---|---|
| `days_since_prev_spacex` | Days from SpaceX's latest launch before the baseline note to the target time | 367 | 10.9 | 9.4 | **0.43** (shorter gap → more delays) |
| `target_moves_before_baseline` | Times the announced target had already changed before the baseline | 367 | 0 | 1 | **0.56** |
| `days_since_prev_pad` | Same, for the same pad | 365 | 13.5 | 13.9 | 0.47 |
| `target_month` | Month of the target | 367 | 7 | 7 | 0.53 |
| `target_hour_utc` | Hour of the target, when the note gave one | 81 | 13 | 11 | 0.51 |

**Weather at the baseline target time** (`target_*`, fetched by `eda.py` from the same Open-Meteo archive at the pad and target time; observed weather, not a forecast):

| Feature | n | Median on time | Median delayed | AUC |
|---|---|---|---|---|
| `target_wind_speed_10m` (km/h) | 367 | 11.2 | 12.3 | **0.56** |
| `target_cloud_cover` (%) | 367 | 56 | 74 | 0.53 |
| `target_temperature_2m`, `target_precipitation` | 367 | | | 0.48 / 0.52 |

How to read this:

- **No single feature is strongly related to delays.** The best are around 0.56 to 0.59, at or just past what chance could produce.
- **Surface wind is the most consistent signal.** It points the same way at both times: delayed launches had windier conditions at the target time and at liftoff. The launch-time value (0.59) cannot be used to predict a week ahead; the target-time value (0.56) can, given a forecast.
- **The schedule gives weak hints.** Launches whose target had already moved, and launches scheduled soon after another SpaceX launch, were delayed somewhat more often (AUC 0.56 and 0.43, at the edge of chance). Worth testing in the model, not yet proven.
- **Payload mass and the upper-air winds show no relationship with delays** (AUC 0.48 to 0.52).
- `target_hour_utc` is known for only 81 launches, because most baseline notes give a day without a time.

### 7.6 Features that add no information

| Column(s) | Why |
|---|---|
| `launch_time`, `latitude`, `longitude` | Copies of `launch_timestamp_utc`, `launchpad_latitude`, `launchpad_longitude` |
| `launchpad_latitude`, `launchpad_longitude`, `upper_wind_station_distance_km` | Fixed for each pad, so they only identify the pad (use a pad category instead if the pad is wanted) |
| `upper_wind_speed_8km_kmh` ~ `upper_wind_speed_10km_kmh` (r = 0.91), `upper_wind_max_kmh` ~ `upper_wind_speed_12km_kmh` (r = 0.91) | Near-duplicates: keep one of each pair at most |
| `target_temperature_2m` ~ `temperature_2m` (0.98), `days_since_prev_spacex` ~ `days_since_prev_pad` (0.99) | Near-duplicates found by the PCA ([§7.7](#77-pca-check)): temperature barely changes between the target time and liftoff, and the two launch gaps track each other |

### 7.7 PCA check

Principal component analysis (`pca_check()` in `eda.py`) on the 20 standardized candidate features from [§7.5](#75-features-vs-delay), using the 326 labelled launches with every feature present (72 delayed). PCA ignores the label, so it checks the redundancy findings directly; the delay link is checked by scoring each component, and models built on the components, against the label. (Re-run 2026-11-18 without the removed `high_altitude_wind_assumed` column, which was a copy of `wind_speed_10m`; the conclusions did not change.)

**Redundancy: confirmed.** The 20 features carry about 13 independent dimensions (13 components explain 95% of the variance, 9 explain 80%). The largest component (22%) is the jet stream: `upper_wind_max_kmh` and the 8, 10 and 12 km winds load on it almost equally (pairwise similarity 0.97 to 1.00), so they act as one feature. The second (17%) is the pad and temperature (pad latitude and longitude, similarity -1.00). PCA also found two near-duplicates the correlation scan missed ([§7.6](#76-features-that-add-no-information)).

**Signal: the main structure in the data is unrelated to delays.**

| Component | Variance | Mainly | Delay AUC |
|---|---|---|---|
| PC1 | 22% | Jet-stream winds | 0.50 |
| PC2 | 17% | Pad, temperature | 0.50 |
| PC3 | 10% | Days since the previous launch (+ payload) | 0.47 |
| PC4 | 7% | Cloud cover and precipitation | 0.50 |
| PC5 | 6% | Target moves and target-time weather | 0.57 |
| PC6 | 6% | Surface wind at both times | 0.60 |

Only PC5 and PC6 show a hint, and they are built from the same features [§7.5](#75-features-vs-delay) flagged (surface wind, schedule).

**Combined, the features do not predict delays.** Logistic regression, time-ordered 5-fold CV (always trained on earlier launches than it is tested on):

| Inputs | ROC-AUC |
|---|---|
| First 2 / 5 / 10 / 13 components | 0.51 / 0.47 / 0.50 / 0.50 |
| All 20 features | 0.50 |
| The 4 features known a week ahead (`days_since_prev_spacex`, `target_moves_before_baseline`, `target_wind_speed_10m`, `target_cloud_cover`) | 0.44 |

The weak single-feature hints do not hold up when predicting later launches. Together with the XGBoost and RandomForest results ([`MODELING.md`](MODELING.md)), this points to the features, not the model type: the current data carries no delay signal that is stable over time.

### 7.8 Recommendations

These are suggestions; changing the model's feature list is a team decision.

1. **Remove the redundant columns** in [§7.6](#76-features-that-add-no-information) from any feature list: keep at most one jet-stream wind, one launch-gap feature and one temperature.
2. **`upper_wind_max_kmh`** shows no relationship with delays (single-feature AUC 0.50, PC1 AUC 0.50), and under the missing-data policy it removes 20 labelled launches from training. Consider dropping it where it is a model input.
3. **Look for new information rather than more of the same.** The schedule and target-time weather features gave weak single-feature hints ([§7.5](#75-features-vs-delay)) but no predictive value in time-ordered CV ([§7.7](#77-pca-check)). Unused LL2 fields are the next candidates: `probability` (published weather-go percentage), `weather_concerns`, mission type, and launch window length.

**Tested 2026-11-18** (one-off scripts, not in the repo). Rolling test on the 2025-26 launches: they were split into 4 blocks in time order, and each block was predicted by a model trained only on earlier launches. About 150 test launches with 16 to 18 delays, so a 95% interval on each AUC is roughly ±0.14.

- **`payload_mass_kg`: kept.** On its own it shows no relationship with delays (AUC 0.52), but the XGBoost delay model does worse without it. On the same 148 test launches, ROC-AUC was 0.63 with payload and 0.54 without (paired difference +0.08, 95% interval -0.05 to +0.23). On `train_model.py`'s own holdout it was 0.52 with payload and 0.37 without. Logistic regression did not change (0.59 both ways). **Decision (2026-11-18): keep it as a model input.** The cost: GCAT has no payload for Starship ([§8](#8-gcat-payload-mass)), so all 17 Starship and Starship Prototype launches, plus 3 Falcon 9 launches, stay out of training (20 of 367 labelled launches, 5 of them delayed).
- **Training on recent launches only: not adopted.** Delays fell from about 30% (2021-24) to about 10% (2025-26), so training only on recent launches was tested:

  | Training window | Logistic regression | RandomForest |
  |---|---|---|
  | All earlier launches | 0.59 | 0.63 |
  | Last 24 months | 0.59 | 0.65 |
  | Last 12 months | 0.57 | 0.53 |

  Current model inputs; ROC-AUC on the 2025-26 test. Every interval but one includes 0.5 (the exception is RandomForest on the last 24 months, 0.51 to 0.79). The last 24 months scored about the same as all history, and the last 12 months did worse because it leaves only 9 to 26 delays to train on. The 4 features known a week ahead gave 0.55 to 0.62 with no consistent winner. **Decision (2026-11-18): keep training on all history.**
- **Open: predicted probabilities are too high.** Because training weights the classes equally, every model above gave an average delay probability of 0.33 to 0.50 on 2025-26 launches, while the actual rate was 0.11. A shorter training window did not fix this. Ranking metrics (ROC-AUC, PR-AUC) are unaffected, but a probability shown as a "risk" on the dashboard would overstate it. **Fixed 2026-11-18** with Platt calibration ([`MODELING.md`](MODELING.md) §5.1).

### 7.9 Discrepancy between the two processed tables

Two scripts produce different tables from the same raw files. This report and the models use the feature builder's table.

| | Feature builder (`build_features.py`): **used** | Cleaner (`clean_data.py`) |
|---|---|---|
| Output file | `data/processed/ml_features.csv` | `data/interim/cleaned_launches.csv` |
| Rows | 746 (left join keeps launches with no weather) | Inner join, and drops any row missing a required value, which conflicts with the [§2](#2-missing-data-policy) rule that the pipeline keeps every row |
| Wind units | km/h, unconverted | Surface wind in m/s (÷ 3.6). The `upper_wind_*` columns pass through unchanged in km/h |
| Column names | Source names (`wind_speed_10m`) | Unit suffixes (`wind_speed_10m_ms`, `temperature_2m_c`) |
| Extra columns | Duplicate `launch_time` / `latitude` / `longitude` | None |

Neither script reads the other's output.

### 7.10 Weather-go forecasts (checked 2026-11-18)

Research (one-off scripts, not in the repo). Since 2026-11-21 the pre-slip forecast is a model input, `low_weather_go` (see **Model input** at the end of this section). The question: does the published launch-weather forecast (the 45th Weather Squadron's "probability of GO") predict delays?

**LL2's stored fields: not used.** LL2's detailed launch data has `probability` (weather-go %) and `weather_concerns` (the weather rules at risk, e.g. "Cumulus Cloud Rule", "Liftoff Winds"). `fetch_spacex.py` does not save them. A one-off fetch (2026-11-18) found:

| Field | Labelled launches with a value | Relationship with delays |
|---|---|---|
| `probability` | 237 of 367 (53 delayed) | None: median 90% for both on-time and delayed launches, AUC 0.52 |
| `weather_concerns` | 142 of 367 | Backwards: launches with concerns were delayed *less* often (17% vs 25%) |

LL2 keeps only the **latest** value, which is the forecast for the day the rocket actually flew. For a delayed launch, that forecast was made after the delay, so it describes the outcome instead of predicting it. **Decision (2026-11-18): do not save or use these two fields.**

**Weather-go % in the schedule notes: a real signal, but only close to launch.** The notes in `spacex_launch_updates.csv` include time-stamped forecast updates, e.g. "Updated launch weather, 55% GO", "Weather 80%", "Updating Weather POG to 40%". 547 notes on 343 launches give a percentage (parsed from notes that mention weather, POG or "% GO"). They are posted a median of 1.8 days before liftoff and rarely more than 5 days before.

To avoid leakage, the value used for a launch is the latest one posted **before the baseline target and before any note moved that target**: the forecast as it stood before anyone knew the launch would slip. The model input below also ignores forecasts posted before the baseline note, since those were for an earlier target date (code review, 2026-11-21).

| When the value is read | Labelled launches | Delays | Median GO%, on time / delayed | AUC (lower GO% → delay) |
|---|---|---|---|---|
| By the baseline note (the week-ahead model's time) | 9 | 6 | 85 / 80 | too few |
| Before the baseline target and before any slip | **132** | 21 | **80 / 50** | **0.67** (95% interval 0.52 to 0.82) |
| Latest before actual liftoff (leaks the outcome, for comparison) | 204 | 45 | 85 / 85 | 0.52 |

- **Stable over time,** unlike every other feature in §7.5: AUC 0.66 for 2021-23 (59 launches, 14 delays) and 0.68 for 2024-26 (73 launches, 7 delays).
- **Easy to read:** with a forecast under 50% GO, 38% of launches were delayed (10 of 26). At 50% or above, 10% were (11 of 106). Under 70%: 28% vs 9%.
- **Not available a week ahead.** The forecast comes a median of 1.4 days before the target, so it cannot feed the week-ahead delay model ([`MODELING.md`](MODELING.md) §2). It suits a short-range prediction made a day or two before launch.
- **Fitted models could not be judged.** Logistic regressions trained only on earlier launches (GO% alone, with target-time weather, or with the schedule features) scored ROC-AUC 0.57 to 0.69 on the later 82 launches, but those hold only 9 delays, so every interval spans roughly 0.35 to 0.9. None beat reading GO% directly.
- **Coverage depends on LL2's volunteer editors** posting a forecast before the target (132 of 367 labelled launches), so the covered launches may not be typical.

**Decision (2026-11-18, replaced 2026-11-21 by the model input below):** no model change for now. Propose a short-range indicator (latest pre-launch forecast under 50% GO → delays historically about 4× more common) to the dashboard team ([§10](#10-open-questions-for-the-pm)), and revisit a fitted short-range model once more delays have a forecast.

**Helper:** `src/data/weather_go.py` has `parse_weather_go(comment)` (the percentage in one note) and `latest_weather_go(updates, launch_id, as_of, since=None)` (the latest value posted at or before `as_of`, and at or after `since` if given; pass the time the prediction is made, or it leaks the outcome). It uses the same parsing as the counts above. **Live use needs upcoming-launch notes:** `fetch_spacex.py` only downloads launches that have flown (`launches/previous/`), so an upcoming launch's notes would have to come from LL2's `launches/upcoming/` endpoint. How to get them (a fetch script or a call from the app) is still to be decided with the dashboard team.

**Model input (decided 2026-11-21):** `low_weather_go` is a numeric input to the delay models: **1** if the pre-slip forecast above was under 50% GO, **0** if it was 50% or more, **blank** if no forecast was posted in time. `train_model.py` builds it in `load_launches()` (`forecast_cutoff()`, `low_weather_go_by_launch()`, threshold `LOW_WEATHER_GO_PCT`), using `latest_weather_go()` above.
- **Why a yes/no flag and not the percentage:** in a rolling test on 2025-26 launches (131 launches, 14 delays, current inputs plus `upper_wind_max_kmh`), the flag raised ROC-AUC by +0.10 for both XGBoost (0.62 → 0.72, 95% interval +0.04 to +0.17) and the RandomForest (0.54 → 0.65, +0.04 to +0.18). The raw percentage gained +0.07 to +0.08.
- **Not a missingness effect:** launches without a forecast are delayed more often (25% vs 17%), but a "has a forecast" flag on its own added nothing (+0.00 / +0.01). The gain comes from the forecast's value. On the XGBoost holdout (2026-11-21 code review; 103 newest launches, 10 delays; mean of 5 seeds), the flag alone did add a little: ROC-AUC 0.518 without the input, 0.568 with only "has a forecast", 0.626 with `low_weather_go`. Reading every forecast at a fixed 24 h before the baseline target, instead of at the first slip, gave 0.623, so the slip-dependent cutoff is not inflating the result. At 48 h it gave 0.461, since most forecasts are not out yet.
- **Blank is allowed:** it is exempt from the missing-data policy ([§2](#2-missing-data-policy)). Of the 347 usable launches, 124 have a value (24 under 50% GO, 38% of them delayed; 100 at 50% or more, 9% delayed). The other 223 stay in training with a blank (26% delayed). (Before the 2026-11-21 fix that drops forecasts older than the baseline note: 129, 25 and 104.)
- **What it changes:** the model is no longer purely week-ahead. A week out the input is usually blank; a day or two before launch, once a forecast is posted, it sharpens the prediction ([`MODELING.md`](MODELING.md) §3).
- **Live use** still needs upcoming-launch notes (above). Until then, callers leave it blank.

### 7.11 Still to document

Documentation for the physics data has not been added to this file yet.

---

## 8. GCAT payload mass

`payload_mass_kg` in `data/raw/spacex_launches.csv` comes from GCAT, not LL2. LL2 had a payload mass for only 10 of 742 launches (checked 2026-10-31).

| Item | Detail |
|---|---|
| Source file | GCAT launch log, `https://planet4589.org/space/gcat/tsv/launch/launch.tsv`, saved unmodified as `data/raw/gcat_launch.tsv` |
| Format | Tab-separated. The first line is the header (starts with `#`) and the second is `# Updated ...`. No API |
| Field used | `OrbPay` ("Orbital Payload"): payload delivered to orbit (perigee above 80 km) for the whole launch. GCAT also has `OrbMass` ("Orbital Mass"): the **total** mass at orbit insertion, including the upper stage and its leftover propellant. We use `OrbPay` only, because the model needs the payload, not the rocket. (`OrbMass` was added to GCAT in July 2026 and its values are not filled in yet.) **Unit: metric tonnes**, confirmed in GCAT's [launch list column explanations](https://www.planet4589.org/space/gcat/web/launch/lcols.html). The fetcher multiplies by 1000 to get kg |
| Join to LL2 | GCAT has no LL2 ids. `fetch_spacex.py` matches each LL2 `net` to the nearest GCAT **Falcon** launch time within 2 hours |
| Replaces LL2? | Yes, completely. LL2 values are discarded, not used as a fallback |

**Coverage (checked 2026-10-31, 743 launches):** 717 have a GCAT mass and 26 are null, per the [missing-data policy](#2-missing-data-policy) (never filled with 0). All Falcon 1 and Falcon Heavy launches and nearly all Falcon 9 launches match. The null ones are:

- **Starship and Starship Prototype (23):** not matched. GCAT lists these flights, but `OrbPay` is 0 for the early prototype hops and 120 t for the later flights, which looks like the vehicle's capacity rather than a real payload.
- **Falcon 9 (3):** the 2016-09-03 pad explosion (never reached orbit, so not in GCAT), the 2020-01-19 Crew Dragon in-flight abort test (GCAT lists 0 because nothing reached orbit, so it is stored as null), and the newest launch, which GCAT had not logged yet.

**Cautions:**

- Where LL2 and GCAT both had a value (10 launches), 7 agreed within 10%.
- **The mass is not LEO-only.** `OrbPay` counts any payload that reaches orbit, whatever the orbit. GCAT's `Category` column, which is filled for all 717 launches with a mass, splits them into 607 in low Earth orbit (LEO 453, Sun-synchronous 94, ISS 60) and 110 in higher or elliptical orbits (GTO 39, super-synchronous transfer 31, elliptical Earth orbit 13, medium Earth orbit 10, other transfer orbits 9, geostationary 5, deep-space 2, Molniya-type 1). A GTO launch carries much less than a LEO one because the rocket spends fuel reaching the higher orbit, so a low `payload_mass_kg` can mean a lighter payload or a farther destination. Falcon 9's LEO maximum is about 18.9 t, which matches the largest value in the table. **Decision (2026-11-17): keep all orbits** as they are; no orbit filter or orbit column.
- GCAT's `Apogee` column cannot be used for this: it is filled for only 209 of the 717 launches. Use `Category`.
- GCAT may revise a launch's mass after the fact. Delete the cached `data/raw/gcat_launch.tsv` and re-run the fetcher to pick up updates.

### 8.1 License and attribution

GCAT is released under **CC BY 4.0** (the [GCAT site](https://planet4589.org/space/gcat/), checked 2026-11-17: "(c) 2020-2026 Jonathan McDowell", "CC-BY-4.0"). It may be freely reproduced as long as it is cited.

- **Short credit** (dashboard footer): "data from GCAT (J. McDowell, planet4589.org/space/gcat)".
- **Full citation** (reports): McDowell, Jonathan C., 2020. General Catalog of Artificial Space Objects, Release 1.8.9, https://planet4589.org/space/gcat. Use the release you downloaded; it is shown at the top of the GCAT site.

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

**Coverage (checked 2026-10-31, 743 launches):** 705 have a sounding and 38 do not (current counts in [§7.3](#73-missing-values)). Balloons reach a median of 32 to 34 km at the three US stations and 26 km at Kwajalein (only 2 launches have a sounding there). Speeds were reported for 704 launches at 10 km, 698 at 20 km and 606 at 30 km.

**Cautions:**

- **Not at the pad.** The station is up to 35 km away, and the balloon drifts downwind as it climbs, so the wind is the profile near the station and not exactly along the rocket's path.
- **Not at launch time.** The sounding can be up to 12 h from liftoff.
- **IGRA2 has gaps.** There are no soundings for April and May 2026, and the newest days are not published yet. Re-run `fetch_weather.py` later to fill recent launches. Delete the cached zip to pull a fresh copy.
- **Two corrupted soundings (now blanked).** Vandenberg's 2024-10-30 12 UTC and 2024-12-05 00 UTC soundings contain levels with winds of about 110 to 137 m/s (400 to 490 km/h) sitting beside neighbouring levels of 5 to 20 m/s. For example, at 6 km the 2024-12-05 sounding reports 111.1 m/s while the levels around it report 7 to 9 m/s. That is not physical: the strongest winds in a real jet stream are about 100 to 150 m/s, and only near 10 to 12 km, never as isolated spikes from one level to the next. The bad values are in the sounding's wind-only levels; its standard pressure levels look normal. **Fixed:** `fetch_weather.py` lists both soundings in `CORRUPTED_SOUNDINGS` and leaves the `upper_wind_*` columns blank for the launches that would use them (2024-10-30 and 2024-12-05), see [§9.2](#92-corrupted-soundings-decided). A spike check (a level more than 30 m/s from the median of its 4 nearest levels) flags 6 of the 683 soundings used: these two (31 and 38 spike levels) and 4 others with 1 to 4 levels each (one 2020 and one 2023 Cape sounding, two Vandenberg soundings from 2026). Those four have not been examined.
- **Largest believable values.** With the two corrupted soundings set aside, the strongest wind in the table is 281.5 km/h (78 m/s at 12 km, Cape Kennedy, 2025-01-07), a normal winter jet-stream value. 400 km/h is possible only in a few rare record-strength jets, not at 6 km or 28 km.
- **Kwajalein is thin.** Only 2 of its 5 launches (2006 and 2007) have a sounding; the three from 2008 and 2009 have none.

### 9.1 License and attribution

IGRA2 is a NOAA NCEI product. Neither the IGRA2 readme nor the [NCEI product page](https://www.ncei.noaa.gov/products/weather-balloon/integrated-global-radiosonde-archive) states a licence or use restriction (checked 2026-11-17). It is U.S. federal government data, provided without warranty of accuracy (the page notes the data "may still include jumps and other discontinuities").

- **Credit** (dashboard footer): "Integrated Global Radiosonde Archive (IGRA), NOAA NCEI".
- **Citation** (reports): NCEI gives no dataset citation. Cite the IGRA v2 paper it lists: Durre, I., Yin, X., Vose, R. S., Applequist, S., & Arnfield, J. (2018). Enhancing the Data Coverage in the Integrated Global Radiosonde Archive. *J. Atmos. Oceanic Technol.*, 35(9), 1753–1770. https://doi.org/10.1175/JTECH-D-17-0223.1

### 9.2 Corrupted soundings (decided)

**Decision (2026-11-17): blank the two launches' upper winds.** `fetch_weather.py` lists Vandenberg's 2024-10-30 12 UTC and 2024-12-05 00 UTC soundings in `CORRUPTED_SOUNDINGS`. When one of them is the sounding chosen for a launch, every `upper_wind_*` value for that launch is left blank (the station columns are kept), and the script prints which launches were affected. No other sounding is substituted. The raw IGRA2 file stays untouched.

Under the missing-data policy ([§2](#2-missing-data-policy)), a blank `upper_wind_max_kmh` leaves the launch out of training for any model that uses it. Only the 2024-12-05 launch has a delay label, so the model loses one launch.

The EDA in [§7](#7-eda-report-spacex-launch-feature-table) was run after this fix.

Not examined yet: four other soundings with 1 to 4 spike levels each (Cape Kennedy 2020-01-19 and 2023-03-02, Vandenberg 2026-01-25 and 2026-03-26). Some may be real wind shear.

---

## 10. Open questions for the PM

- **Short-range weather indicator (for the dashboard team):** show the latest LL2 weather-go forecast before launch, flagged when it is under 50% GO (delays were about 4× more common: 38% vs 10%, [§7.10](#710-weather-go-forecasts-checked-2026-11-18))? The data side can provide the parsed value; how and whether to show it is the dashboard team's call. (Since 2026-11-21 it is also a model input, `low_weather_go`.)

**Resolved (2026-11-18):**

- **Forecast weather (option C):** train on observed weather now; add a forecast archive (e.g. Open-Meteo's Previous Runs, from 2024) later. That archive will still need adding to the source register when adopted.
- **LL2 `probability` and `weather_concerns`:** not saved or used; LL2 stores the final-day value, which leaks the outcome ([§7.10](#710-weather-go-forecasts-checked-2026-11-18)).
- **Probability calibration:** the raw delay probabilities averaged 0.33 to 0.50 against an actual 2025-26 rate of 0.11 ([§7.8](#78-recommendations)). They are now calibrated with Platt scaling fitted on the last 12 months ([`MODELING.md`](MODELING.md) §5.1).
- **Placeholder and ratio columns:** `high_altitude_wind_assumed`, `wind_speed_ratio` and `payload_ratio` were removed ([§7.2](#72-feature-table-columns)).
- **Payload as a model input:** kept, because the XGBoost model does worse without it; Starship stays out of training as a result ([§7.8](#78-recommendations)).
- **Training window:** all history, not only recent launches ([§7.8](#78-recommendations)).

**Resolved (2026-11-17):**

- **Missing-data policy:** a launch missing a numeric model input is left out of training and evaluation; text/label gaps are fine ([§2](#2-missing-data-policy)).
- **Corrupted Vandenberg soundings:** the two launches' upper winds are left blank ([§9.2](#92-corrupted-soundings-decided)).
- **Payload orbit:** keep `OrbPay` for every orbit, with no filter or orbit column ([§8](#8-gcat-payload-mass)).
- **Upper-air wind instead of the placeholder:** the models use `upper_wind_max_kmh` directly ([`MODELING.md`](MODELING.md) §9.1). (The placeholder columns were later removed, 2026-11-18.)
- **Wind unit:** km/h everywhere in `raw/`, matching the fetcher ([§5](#5-unit-conversions)).
- **Licences and attribution:** confirmed from each source's own pages ([§3.4](#34-licensing), [§4.6](#46-licensing-and-attribution), [§8.1](#81-license-and-attribution), [§9.1](#91-license-and-attribution)).
