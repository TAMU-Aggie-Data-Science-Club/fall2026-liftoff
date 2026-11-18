# Modeling Overview

How the launch-delay model is built, trained, and evaluated. This file describes the code on `main` unless a section says otherwise.

**Status (2026-11-17):**
- **Reframed: the model predicts on time vs delayed.** The success/failure model was dropped; there is no failure class (§1, §2).
- Baseline training: `src/models/train_model.py` (PR #48).
- Evaluation and tuning: `src/models/evaluate.py` (PR #49), **not yet run end to end**.
- RandomForest comparison model: `src/models/train_random_forest.py` on `data/random-forest` (§5.1).
- Results (§7) and feature importance (§8): **placeholders** until the model techniques are implemented and compared on the same data.
- Upper-level winds: in the feature table; used by the RandomForest, not yet by XGBoost on `main`. See §9.1.

---

## 1. Model

One binary XGBoost classifier, saved in `models/baseline_model.pkl`. A launch is either **on time** (successfully launched within the delay window) or **delayed**.

| Model | Target column | Label = 1 means | Event we care about catching |
|---|---|---|---|
| `delay` | `is_delayed` | Launch lifted off more than its provider's threshold after its baseline target: 72 h for SpaceX, 7 days for others (§2) | Delays (label 1) |

The model outputs the probability of a delay; the on-time probability is `1 − p`.

**Why no failure class (2026-11-17):** the old `success` model predicted `mission_success`, which had 15 failures in 743 launches. The project now asks whether a launch happens on schedule, not whether it blows up. Amos-6, the only vehicle that exploded before launching, stays excluded. The 14 in-flight failures all lifted off, so they are labelled by timing like any other launch. They can be dropped later if the team decides to.

The pickle holds a dict with `models` (`{"delay": {...}}`, one XGBoost `Booster`), `feature_columns`, `rocket_categories`, `params`, `num_boost_round`, and `delay_definition`. Use the saved `rocket_categories` when preparing features for prediction so the categorical encoding matches training.

---

## 2. Labels

### 2.1 Launch delay (the only label)

There is no delay field in the API, so `train_model.py` derives one from LL2 schedule notes saved in `data/raw/spacex_launch_updates.csv` (written by `fetch_spacex.py`).

1. Keep notes that announce a schedule and contain a full date (month and day), for example "Now targeting Nov 05 at 02:35 UTC". A note qualifies if it has a schedule keyword (*target, NET, delay, slip, moved, scheduled, recycle, revert*), or a launch-date phrase (*GO for, window, launch on, attempt, opportunity, launch time, T-0, confirmed, planned for, pushing to, moving to, back on, expected to*) as long as it does not cancel a date (*no longer, standing down, no launch, not in position*). Month-only notes such as "NET April" are not used, because they give no exact day.
2. Parse the target date and time. If a note gives a day but no time, the whole day counts as on time. If it gives no year, the year is inferred from when the note was posted.
3. **Baseline:** the latest target announced in a note posted **at least 7 days** before the actual launch.
4. **Delayed:** the actual launch came more than the provider's threshold after the baseline: **72 hours (3 days) for SpaceX, 7 days for NASA and every other provider**. Otherwise it is **on time**, whatever happened after liftoff.
5. Launches with no qualifying note have a missing label and are excluded from the delay model. On the 2026-11-17 fetch, 367 of 745 launches have a label (80 delayed, 22%), all from 2020-12-19 onward. After the missing-data policy (§3), 327 (72 delayed) are usable once `upper_wind_max_kmh` is an input (20 lack a payload mass, 20 lack the upper wind). Most unlabelled launches since 2021 have only early notes with no date in the text ("Added launch.", "GO for launch."), which no parser can recover; a shorter baseline window would add launches but lose most of the delays, so it stays at 7 days.

| Constant | Value | Meaning |
|---|---|---|
| `DELAY_BASELINE_DAYS` | 7 | How far before launch the baseline note must be posted |
| `DELAY_THRESHOLD_HOURS_BY_PROVIDER` | `{"SpaceX": 72}` | Slip beyond the baseline that counts as delayed, per provider |
| `DEFAULT_DELAY_THRESHOLD_HOURS` | 168 (7 days) | Threshold for NASA and any provider not listed above |

**The delay window depends on the launch provider** (PM decision, 2026-11-17):

| Provider | Baseline | Delay threshold | Status |
|---|---|---|---|
| SpaceX | Latest target announced ≥ 7 days before launch | > 72 h (3 days) | In use (was 24 h, set 2026-11-08) |
| NASA and all other providers | Same rule | > 7 days | Defined, but no such launches are fetched yet |

`delay_threshold()` reads a `launch_provider` column when the feature table has one. Launches without one count as SpaceX, because `fetch_spacex.py` only fetches SpaceX. A fetcher that adds other providers must also fill `launch_provider`.

The 3-day and 7-day figures are **team definitions**. We found no published SpaceX rule that defines a delay. The 7-day threshold is separate from the 7-day baseline rule (`DELAY_BASELINE_DAYS`); they just happen to match.

Amos-6 (exploded on the pad in 2016, never launched) is excluded from training.

---

## 3. Features

| Feature | Type | Units | Source |
|---|---|---|---|
| `temperature_2m` | numeric | °C | Open-Meteo, hourly record nearest launch time, at pad coordinates |
| `wind_speed_10m` | numeric | km/h | Open-Meteo (surface wind) |
| `precipitation` | numeric | mm | Open-Meteo |
| `cloud_cover` | numeric | % | Open-Meteo |
| `payload_mass_kg` | numeric | kg | GCAT `OrbPay` (tonnes × 1000), matched to each LL2 launch by time. Missing when GCAT has no real value (see [`DATA.md`](DATA.md) §8) |
| `rocket_type` | categorical | — | LL2 rocket configuration name |

These are XGBoost's inputs on `main`. The RandomForest also uses `upper_wind_max_kmh`, and `feature/add-windspeed` adds it to XGBoost (§9.1).

- Weather units are Open-Meteo's defaults, since `fetch_weather.py` doesn't request other units. The m/s conversion in `clean_data.py` only affects `data/interim/cleaned_launches.csv`, which the model does not read.
- **Missing-data policy ([`DATA.md`](DATA.md) §2):** a launch missing any numeric model input is left out of training and evaluation (`usable_launches()`, which keys on `NUMERIC_FEATURES`). Missing `rocket_type` is kept. No imputation is done. At prediction time a missing number is still passed to the model as `NaN`; whether predictions should refuse instead is an open question.
- `rocket_type` uses XGBoost's native categorical support. Rocket types not seen in training become missing at prediction time.

---

## 4. Feature engineering pipeline

```
fetch_spacex.py   → data/raw/spacex_launches.csv, data/raw/spacex_launch_updates.csv
fetch_weather.py  → data/raw/historical_weather.csv
build_features.py → data/processed/ml_features.csv   (left join on launch_id)
train_model.py    → models/baseline_model.pkl
```

`build_features.py` checks that each weather row matches its launch's time and pad coordinates. It used to add two derived columns, `wind_speed_ratio` (always 1, built from the placeholder copy of surface wind `high_altitude_wind_assumed`) and `payload_ratio` (always empty, no capacity column). All three were removed on 2026-11-18 because they carried no information; [`DATA.md`](DATA.md) §7.2 explains why neither ratio was rebuilt from real data.

---

## 5. Training and hyperparameters

| Setting | Value |
|---|---|
| Objective | `binary:logistic` |
| Eval metric | `logloss` |
| `max_depth` | 3 |
| `eta` (learning rate) | 0.1 |
| Boosting rounds | 200 |
| Seed | 42 |
| Class weighting | Each class weighted so both contribute equally in total, which upweights the rare class |
| Decision threshold | 0.5 |

The script prints a quick check before saving: it trains on older launches and reports accuracy, events caught, false alarms, and ROC-AUC on the newest ones (holdout rule in §6). The **saved** model is then retrained on all labelled launches.

---

## 6. Validation method

`src/models/evaluate.py` (PR #49):

1. Sort labelled launches by date and hold out the **newest launches**. They are not used for tuning. The holdout starts at the newest 20%. If that contains fewer than `MIN_TEST_EVENTS` (10) delays, the cutoff moves earlier until it does, up to `MAX_HOLDOUT_FRACTION` (40%). Time order is kept, so the model never trains on launches newer than the ones it is tested on. If 40% still has too few delays, the script prints a warning. Both constants are in `train_model.py`, and both scripts use the same `holdout_split()`.
2. **Grid search** on the training split (every launch older than the holdout) using **5-fold `TimeSeriesSplit`**. Each fold trains on the past and tests on the future.

   | Parameter | Values |
   |---|---|
   | `max_depth` | 2, 3, 4 |
   | `eta` | 0.05, 0.1 |
   | Boosting rounds | 100, 200 |

   Selection rule: highest mean ROC-AUC across folds where it is defined (both classes present). If no fold has a defined ROC-AUC, it falls back to the §5 settings.
3. Re-run cross-validation with the chosen settings.
4. Score the holdout once.
5. Compute feature importance by **gain** on the training split.

Metrics, reported per fold and on the holdout: **accuracy, precision, recall, F1, ROC-AUC and PR-AUC** (average precision). Precision, recall, F1 and PR-AUC treat a **delay** as the positive class. Delays are the minority class, so accuracy alone is misleading: a model that always says "on time" scores high. Read accuracy alongside precision and recall. Output goes to `reports/model_evaluation.json`.

---

## 7. Results

> **Placeholder.** Filled in once the model techniques (XGBoost, RandomForest, and any third) are implemented and run on the same labels and holdout, so their metrics can be compared side by side.

| Model | Labelled launches | Delays | Best settings | CV mean ROC-AUC | Holdout accuracy | Holdout precision | Holdout recall | Holdout F1 | Holdout ROC-AUC | Holdout PR-AUC |
|---|---|---|---|---|---|---|---|---|---|---|
| XGBoost | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
| RandomForest | TBD | TBD | TBD | n/a (not in `evaluate.py` yet) | TBD | TBD | TBD | TBD | TBD | TBD |

Things to note once results arrive:
- Delays may be rare in some time folds. ROC-AUC and PR-AUC are undefined for folds with no delays, and those folds are skipped. Report how many folds were valid.
- The delay model only covers launches with schedule notes, mostly from 2020 onward. It should not be read as covering earlier launches.

---

## 8. Feature importance

> **Placeholder.** Filled in alongside §7. XGBoost importance comes from `feature_importance` in `reports/model_evaluation.json` (gain); the RandomForest prints impurity-based importance, which is on a different scale.

| Rank | `delay` model feature | Gain |
|---|---|---|
| 1 | TBD | TBD |
| 2 | TBD | TBD |
| 3 | TBD | TBD |
| 4 | TBD | TBD |
| 5 | TBD | TBD |
| 6 | TBD | TBD |

A gain of 0 means the feature was never used in a split. Gain shows how much a feature helps the trees. It does not show which direction it pushes predictions.

---

## 9. Known gaps

### 9.1 Upper-level winds

The project's issue #36 asks how upper-level wind shear affects predictions. Where things stand:

| Piece | Where | Status |
|---|---|---|
| Upper-air data | `fetch_weather.py` on `main` (PR #38, via `data/integration`) | Measured NOAA IGRA2 radiosonde winds: `upper_wind_max_kmh`, `upper_wind_max_alt_km`, and `upper_wind_speed_{2..30}km_kmh` / `upper_wind_dir_{2..30}km_deg`, all in km/h ([`DATA.md`](DATA.md) §9). On the 2026-11-17 fetch, 708 of 745 launches have `upper_wind_max_kmh` |
| XGBoost | `train_model.py` | **Not used on `main`.** `feature/add-windspeed` adds `upper_wind_max_kmh` to `NUMERIC_FEATURES` (not merged yet) |
| RandomForest | `train_random_forest.py` on `data/random-forest` | Uses `upper_wind_max_kmh` (§5.1) |
| Trajectory risk link | `src/physics/trajectory.py` on `physics/ml-solver-fusion` | Passes an optional `upper_wind_max` (m/s, converted to km/h) to the model |
| Placeholder | `high_altitude_wind_assumed`, `wind_speed_ratio` | Removed 2026-11-18 (they were copies of the surface wind, and the ratio was always 1) |

Cautions:
- Two corrupted Vandenberg soundings (2024-10-30 and 2024-12-05) are still in the `upper_wind_*` values. See [`DATA.md`](DATA.md) §9.2; the fix is waiting on a PM decision.
- Only the peak wind is used so far. Fixed-height winds or a derived shear (speed difference between height bands, not computed anywhere yet) are still options for issue #36.

### 9.2 Other open items
- `payload_mass_kg` stays an input: the XGBoost model does worse without it, though it leaves Starship out of training ([`DATA.md`](DATA.md) §7.8).

---

## 10. Reproducing

```bash
python src/data/fetch_spacex.py
python src/data/fetch_weather.py
python src/data/build_features.py
python src/models/train_model.py   # writes models/baseline_model.pkl
python src/models/evaluate.py      # writes reports/model_evaluation.json
```

All data outputs stay under the git-ignored `data/` folder (see [`DATA.md`](DATA.md)).
