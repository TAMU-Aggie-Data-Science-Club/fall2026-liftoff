# Liftoff - Data Sources, Schemas & Storage

Look-up reference for the data Liftoff uses: where it comes from, what the fields mean, what units they are in, how to handle gaps, and where files live on disk. Datasets themselves are **never committed**. Only the scripts that fetch and process them are tracked in git.

**Contents**

1. [Source register](#1-source-register)
2. [Missing-data policy](#2-missing-data-policy)
3. [SpaceX REST API](#3-spacex-rest-api)
4. [Open-Meteo Historical Weather API](#4-open-meteo-historical-weather-api)
5. [Unit conversions](#5-unit-conversions)
6. [Storage layout (`data/`)](#6-storage-layout-data)

> Status: only the SpaceX API and Open-Meteo are documented so far. NASA Space Shuttle data and CelesTrak / Space-Track TLEs (listed in [`DELIVERABLES.md`](DELIVERABLES.md)) will be added in later issues.

---

## 1. Source register

| Source | Origin / URL | Access method | License | Sensitivity | Notes |
|---|---|---|---|---|---|
| SpaceX REST API (v5) | `https://api.spacexdata.com/v5` (community project: [r-spacex/SpaceX-API](https://github.com/r-spacex/SpaceX-API)) | Public HTTPS GET, JSON, no auth | Repo code is Apache-2.0. Data license not stated: **TBD** | Public, no PII | **Repo archived 2026-06-06; API was unreachable on 2026-10-20** (see [§3.1](#31--access-warning)). Not affiliated with SpaceX. |
| Open-Meteo Historical Weather API | `https://archive-api.open-meteo.com/v1/archive` | Public HTTPS GET, JSON, no key (free tier) | CC BY 4.0, **non-commercial use only** on the free tier | Public, no PII | Attribution required. Backed by ERA5 / ERA5-Land reanalysis. |

---

## 2. Missing-data policy

> ## ⚠️ NEEDS DISCUSSION WITH PM ⚠️
> **Interim rule: if a source does not provide a data point, store it as `null` (JSON `null` / pandas `NaN` / `None`). Do not impute, drop rows, or fill with 0 in the pipeline.**
>
> This is a placeholder. Whether to impute, drop, or flag missing values (and per-field) has **not** been decided and **must be discussed with a PM** before feature engineering starts. Do not build logic that depends on the current choice.

---

## 3. SpaceX REST API

### 3.1  ⚠️ Access warning

> **Trouble accessing this API.**
> - The upstream repo `r-spacex/SpaceX-API` was **archived (read-only) on 2026-06-06**. Last code push was 2024-08-17.
> - On **2026-10-20** requests to `https://api.spacexdata.com/v4/launches/latest`, `/v5/launches/latest` and `/v5/launchpads` failed with Cloudflare errors **522 / 525** (or no connection). The status page (`status.spacexdata.com`) still loaded.
> - Because of this, **the fields below come from the repo's schema file, not from live responses.** Field names, types and defaults are from the schema; **units and descriptions are not given there and are marked `TBD`/assumed**. Re-verify against a live response once the API responds.
> - Flag to PM: this source is at risk of staying down. A replacement would be a data-source decision (not made here).

### 3.2 Endpoints

| Endpoint | Returns | Status |
|---|---|---|
| `GET /v5/launches` | All launches (past and upcoming) | Path from the repo's launches schema; not re-tested live |
| `GET /v5/launches/latest` | Latest launch | Named in the README example |
| `GET /v5/launches/{id}` | One launch | Assumed from API convention: **TBD** |
| `rockets`, `launchpads`, `landpads`, `payloads`, `cores`, `capsules`, `starlink` | Related datasets referenced by UUID from launches | Dataset names from the README; **exact paths and schemas TBD** |

Base URL: `https://api.spacexdata.com`. Auth: none. Responses: JSON.

### 3.3 Rate limits

Not stated in the repo or README. **TBD.** Until confirmed, fetch politely: one bulk request for `/v5/launches`, cache to `data/raw/`, don't re-poll.

### 3.4 Launch object fields (`/v5/launches`)

Types are from the schema file. "Nullable" means the schema default is `null`. Units are **TBD** unless obvious from the name.

| Field | Type | Nullable | Unit / format | Notes |
|---|---|---|---|---|
| `flight_number` | number | no | count | Sequential launch number |
| `name` | string | no | | Unique mission name |
| `date_utc` | string | no | ISO 8601, UTC | |
| `date_unix` | number | no | Unix time (seconds, assumed) | |
| `date_local` | string | no | ISO 8601 with local offset | |
| `date_precision` | string | no | enum: `half`, `quarter`, `year`, `month`, `day`, `hour` | How exact the date is. Low precision means the time of day is unreliable. |
| `static_fire_date_utc` | string | yes | ISO 8601, UTC | |
| `static_fire_date_unix` | number | yes | Unix time (seconds, assumed) | |
| `tbd` | boolean | no (default `false`) | | Date to be determined. Note: the schema file spells this `tdb`. **Check the live key name.** |
| `net` | boolean | no (default `false`) | | "No earlier than" date |
| `window` | number | yes | seconds (assumed) | Launch window length |
| `rocket` | UUID | yes | | Foreign key to rockets dataset |
| `success` | boolean | yes | | **Outcome label.** `null` for upcoming or unknown launches |
| `failures[]` | array of object | no | | `time` (number, seconds after liftoff, assumed), `altitude` (number, km, assumed), `reason` (string) |
| `upcoming` | boolean | no | | `true` means no outcome yet. Exclude from training |
| `details` | string | yes | free text | |
| `fairings` | object | no | | `reused`, `recovery_attempt`, `recovered` (boolean, nullable), `ships` (array of UUID) |
| `crew[]` | array of object | no | | `crew` (UUID, nullable), `role` (string, nullable) |
| `ships`, `capsules`, `payloads` | array of UUID | no | | Foreign keys. Payload mass lives in the payloads dataset |
| `launchpad` | UUID | yes | | Foreign key to launchpads dataset. Needed to look up weather coordinates |
| `cores[]` | array of object | no | | `core` (UUID), `flight` (number, this core's flight count), `gridfins`, `legs`, `reused`, `landing_attempt`, `landing_success` (boolean), `landing_type` (string), `landpad` (UUID). All nullable |
| `links` | object | no | URLs | `patch.{small,large}`, `reddit.{campaign,launch,media,recovery}`, `flickr.{small,original}` (arrays), `presskit`, `webcast`, `youtube_id`, `article`, `wikipedia`. Not model features |
| `auto_update` | boolean | no (default `true`) | | Internal flag |

**Delay hours are not a field.** The API has no "delay" value. Defining delay (and deriving it, e.g. from `date_utc` vs. an original planned date) is a scoping decision still open in [`DELIVERABLES.md`](DELIVERABLES.md) (milestone 1).

### 3.5 If a data point is missing

Follow the [missing-data policy](#2-missing-data-policy): keep `null`. Specific cases to expect:

- `success = null` on upcoming launches: these have no label.
- `rocket`, `launchpad`, `window`, `details` can be `null`.
- Core and fairing booleans can be `null` (for example no landing attempted).
- `date_precision` coarser than `hour`: the time of day is not reliable for matching weather.

---

## 4. Open-Meteo Historical Weather API

### 4.1 Endpoint

`GET https://archive-api.open-meteo.com/v1/archive` (verified live 2026-10-20)

| Parameter | Required | Value we use | Notes |
|---|---|---|---|
| `latitude`, `longitude` | yes | launch site coordinates (WGS84) | Site coordinates come from the SpaceX launchpads dataset (**TBD**) |
| `start_date`, `end_date` | yes | `yyyy-mm-dd` | |
| `hourly` | no | comma-separated variable list | No default. Daily aggregates also available via `daily` (requires `timezone`) |
| `temperature_unit` | no | `celsius` (default) | |
| `wind_speed_unit` | no | **`kn`** (default is `kmh`) | **Must be set explicitly**, see [§5](#5-unit-conversions) |
| `precipitation_unit` | no | `mm` (default) | |
| `timeformat` | no | `iso8601` (default) | |
| `timezone` | no | `GMT` (default) | Keep UTC so it matches `date_utc` |

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

Follow the [missing-data policy](#2-missing-data-policy): keep `null`. **How Open-Meteo marks a missing hourly value is not stated in its docs: TBD.** JSON `null` is expected; confirm by checking a response for dates near the 5-day lag and treat any array element that is `null` as missing. Also expect gaps when a launch date is too recent or the launch time is imprecise (`date_precision`).

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
| Time (`date_unix`) | Unix seconds (assumed) | datetime (UTC) | `pd.to_datetime(x, unit="s", utc=True)` |
| Relative humidity, cloud cover | % | fraction (if needed) | ÷ 100 |

Knots were chosen as the weather wind unit (the issue lists knots as an example unit). The Open-Meteo default is km/h, so forgetting `wind_speed_unit=kn` silently yields the wrong unit.

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
| `data/raw/` | Unmodified API responses (e.g. the SpaceX launches JSON, Open-Meteo hourly JSON), saved straight from the fetcher | **Immutable.** Never edit by hand; re-fetch instead. Units are source units (knots, °C, hPa). |
| `data/interim/` | Intermediate outputs: unit conversions ([§5](#5-unit-conversions)), type fixes, SpaceX launches joined to weather by launchpad coordinates and time | Reproducible from `raw/` by a tracked script. Safe to delete and regenerate. |
| `data/processed/` | Final feature tables for the XGBoost models and the dashboard | Reproducible from `interim/`. This is what training and the app read. |

Flow: `raw/` → `interim/` → `processed/`. Data only moves forward, and each step is a tracked script or notebook so any teammate can rebuild every folder from scratch.

File naming inside these folders is not yet decided: **TBD.**
