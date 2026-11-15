# Modeling Overview

How the launch-outcome models are built, trained, and evaluated. This file describes the code on `main` unless a section says otherwise.

**Status (2026-11-10):**
- Baseline training: merged to `main` (PR #48, `src/models/train_model.py`).
- Evaluation and tuning: proposed in PR #49 (`src/models/evaluate.py`), **not yet merged or run end to end**.
- Results (§7) and feature importance (§8): **placeholders** until the evaluation runs on the full dataset, including `spacex_launch_updates.csv`.
- Upper-level winds: **not used by the model yet**. See §9.

---

## 1. Models

Two binary XGBoost classifiers are trained by one script and saved together in `models/baseline_model.pkl`.

| Model | Target column | Label = 1 means | Event we care about catching |
|---|---|---|---|
| `success` | `mission_success` | Launch succeeded | Failures (label 0) |
| `delay` | `is_delayed` | Launch was delayed > 24 h | Delays (label 1) |

Both models output the probability that the label is 1. For the success model, the failure risk is `1 − p`.

> **Note:** [`DELIVERABLES.md`](DELIVERABLES.md) and [`README.md`](README.md) describe the delay model as a *regressor* for delay hours. The implemented model is a *classifier* (delayed or not). Those docs have not been updated to match.

The pickle holds a dict with `models` (one XGBoost `Booster` per target), `feature_columns`, `rocket_categories`, `params`, `num_boost_round`, and `delay_definition`. Use the saved `rocket_categories` when preparing features for prediction so the categorical encoding matches training.

---

## 2. Labels

### 2.1 Mission success

From the Launch Library 2 launch status in `fetch_spacex.py`:

| LL2 status | `mission_success` |
|---|---|
| Success | 1 |
| Failure, Partial Failure | 0 |
| Anything else (TBD, Go, In Flight, …) | missing → launch dropped from this model |

Pad failures (for example, Amos-6 in 2016) count as failures on `main`. A follow-up commit on `data/ml-baseline` (`ba62d46`) excludes Amos-6, but it has not been merged.

### 2.2 Launch delay

There is no delay field in the API, so `train_model.py` derives one from LL2 schedule notes saved in `data/raw/spacex_launch_updates.csv` (written by `fetch_spacex.py`).

1. Keep notes that announce a schedule (keywords: *target, NET, delay, slip, moved, scheduled, recycle, revert*) and contain a date, for example "Now targeting Nov 05 at 02:35 UTC".
2. Parse the target date and time. If a note gives a day but no time, the whole day counts as on time. If it gives no year, the year is inferred from when the note was posted.
3. **Baseline:** the latest target announced in a note posted **at least 7 days** before the actual launch.
4. **Delayed:** the actual launch came **more than 24 hours** after the baseline.
5. Launches with no qualifying note have a missing label and are excluded from the delay model. This covers most launches before about 2020.

| Constant | Value | Meaning |
|---|---|---|
| `DELAY_BASELINE_DAYS` | 7 | How far before launch the baseline note must be posted |
| `DELAY_THRESHOLD_HOURS` | 24 | Slip beyond the baseline that counts as delayed |

The team agreed on these values on 2026-11-08, and they are open to change.

---

## 3. Features

| Feature | Type | Units | Source |
|---|---|---|---|
| `temperature_2m` | numeric | °C | Open-Meteo, hourly record nearest launch time, at pad coordinates |
| `wind_speed_10m` | numeric | km/h | Open-Meteo (surface wind) |
| `precipitation` | numeric | mm | Open-Meteo |
| `cloud_cover` | numeric | % | Open-Meteo |
| `payload_mass_kg` | numeric | kg | LL2. Sum of payload masses × amount. Missing if any payload's mass is unknown |
| `rocket_type` | categorical | — | LL2 rocket configuration name |

- Weather units are Open-Meteo's defaults, since `fetch_weather.py` doesn't request other units. The m/s conversion in `clean_data.py` only affects `data/interim/cleaned_launches.csv`, which the model does not read.
- Missing numeric values are passed to XGBoost as `NaN`, which it handles natively. No imputation is done.
- `rocket_type` uses XGBoost's native categorical support. Rocket types not seen in training become missing at prediction time.

---

## 4. Feature engineering pipeline

```
fetch_spacex.py   → data/raw/spacex_launches.csv, data/raw/spacex_launch_updates.csv
fetch_weather.py  → data/raw/historical_weather.csv
build_features.py → data/processed/ml_features.csv   (left join on launch_id)
train_model.py    → models/baseline_model.pkl
```

`build_features.py` checks that each weather row matches its launch's time and pad coordinates, then adds two derived columns. **The model doesn't use either one yet:**

| Column | Why it isn't a model input |
|---|---|
| `wind_speed_ratio` | Computed as `high_altitude_wind_assumed / wind_speed_10m`, but on `main` `high_altitude_wind_assumed` is a placeholder copy of the surface wind, so the ratio is always 1. |
| `payload_ratio` | Needs a `max_payload_capacity_kg` column, which no source provides yet, so it is empty. |

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

The script prints a quick check before saving: it trains on the oldest 80% of labelled launches and reports accuracy, events caught, false alarms, and ROC-AUC on the newest 20%. The **saved** model is then retrained on all labelled launches.

---

## 6. Validation method

*Proposed in PR #49 (`src/models/evaluate.py`). Not yet merged.*

For each model:

1. Sort labelled launches by date and hold out the **newest 20%**. They are not used for tuning.
2. **Grid search** on the older 80% using **5-fold `TimeSeriesSplit`**. Each fold trains on the past and tests on the future.

   | Parameter | Values |
   |---|---|
   | `max_depth` | 2, 3, 4 |
   | `eta` | 0.05, 0.1 |
   | Boosting rounds | 100, 200 |

   Selection rule: highest mean ROC-AUC across folds where it is defined (both classes present). If no fold has a defined ROC-AUC, it falls back to the §5 settings.
3. Re-run cross-validation with the chosen settings.
4. Score the held-out newest 20% once.
5. Compute feature importance by **gain** on the 80% training split.

Precision, recall, and F1 treat the **event** as the positive class: failures for the success model, delays for the delay model. Output goes to `reports/model_evaluation.json`.

---

## 7. Results

> **Placeholder.** Fill these in from `reports/model_evaluation.json` once PR #49 is merged and run. The delay model is waiting on `data/raw/spacex_launch_updates.csv`.

| Model | Labelled launches | Events | Best `max_depth` / `eta` / rounds | CV mean ROC-AUC | Holdout precision | Holdout recall | Holdout F1 | Holdout ROC-AUC |
|---|---|---|---|---|---|---|---|---|
| `success` | TBD | TBD failures | TBD | TBD | TBD | TBD | TBD | TBD |
| `delay` | TBD | TBD delays | TBD | TBD | TBD | TBD | TBD | TBD |

Things to note once results arrive:
- Failures are rare, so some time folds may contain no failures. ROC-AUC is undefined for those folds and they are skipped. Report how many folds were valid.
- The delay model only covers launches with schedule notes, mostly from 2020 onward. It should not be read as covering earlier launches.

---

## 8. Feature importance

> **Placeholder.** Fill in from `feature_importance` in `reports/model_evaluation.json`.

| Rank | `success` model feature | Gain | `delay` model feature | Gain |
|---|---|---|---|---|
| 1 | TBD | TBD | TBD | TBD |
| 2 | TBD | TBD | TBD | TBD |
| 3 | TBD | TBD | TBD | TBD |
| 4 | TBD | TBD | TBD | TBD |
| 5 | TBD | TBD | TBD | TBD |
| 6 | TBD | TBD | TBD | TBD |

A gain of 0 means the feature was never used in a split. Gain shows how much a feature helps the trees. It does not show which direction it pushes predictions.

---

## 9. Known gaps

### 9.1 Upper-level winds are not in the model

The project's issue #36 asks how upper-level wind shear affects predictions. **The current model can't answer that**, because no upper-air feature reaches it:

- **The upper-air data exists but isn't on `main`.** PR #38 added IGRA radiosonde winds to `fetch_weather.py`, with columns such as `upper_wind_max_kmh`, `upper_wind_max_alt_km`, and `upper_wind_speed_{2..30}km_kmh` / `upper_wind_dir_{2..30}km_deg`. It was merged into `data/integration`, not `main`.
- **The model branch was cut before that work.** `data/ml-baseline` branched from `main` at `f084530` (Oct 30), so `train_model.py` was written against a dataset without upper-air columns.
- **The placeholder on `main` adds nothing.** `high_altitude_wind_assumed` equals the surface wind (§4).

To add them:
1. Merge `data/integration` into `main`.
2. Re-run `fetch_weather.py` and `build_features.py`.
3. Add the chosen upper-air columns to `NUMERIC_FEATURES` in `train_model.py`.

Which columns to use is still a team decision: maximum wind, wind at fixed altitudes, or a derived shear (for example, the speed difference between altitude bands, which is not computed anywhere yet).

### 9.2 Other open items
- Delay is a classifier, not the regressor described in DELIVERABLES (§1).
- The Amos-6 exclusion is unmerged (§2.1).
- `payload_ratio` is unused because there is no capacity source (§4).

---

## 10. Reproducing

```bash
python src/data/fetch_spacex.py
python src/data/fetch_weather.py
python src/data/build_features.py
python src/models/train_model.py   # writes models/baseline_model.pkl
python src/models/evaluate.py      # after PR #49 merges; writes reports/model_evaluation.json
```

All data outputs stay under the git-ignored `data/` folder (see [`DATA.md`](DATA.md)).
