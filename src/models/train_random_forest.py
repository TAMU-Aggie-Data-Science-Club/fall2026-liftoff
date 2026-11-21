"""Train a RandomForest launch-delay classifier (on time vs delayed) and report holdout metrics.

Uses the same labels, launches and time-ordered holdout as train_model.py, so its
numbers can be compared with the XGBoost model. It also uses the high-altitude wind
(upper_wind_max_kmh) and the pre-slip weather-go forecast flag (low_weather_go). The rare
delayed class is upweighted with class_weight="balanced". Launches missing any numeric
input are left out (DATA.md §2), except low_weather_go, which is blank for most launches
and stays blank. The model is retrained on all usable launches and saved to
models/random_forest_model.pkl.
"""

import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)

from train_model import (
    DELAY_BASELINE_DAYS,
    MODELS,
    NUMERIC_FEATURES,
    UPDATES_PATH,
    holdout_split,
    load_launches,
    parse_note_target,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
from src.data.weather_go import latest_weather_go  # noqa: E402

MODEL_PATH = REPO_ROOT / "models" / "random_forest_model.pkl"

# XGBoost's numeric features plus the high-altitude wind and the weather-go flag
# (each skipped if already listed).
RF_NUMERIC_FEATURES = NUMERIC_FEATURES + [
    column for column in ["upper_wind_max_kmh", "low_weather_go"]
    if column not in NUMERIC_FEATURES
]
# Numeric inputs that may be blank: launches missing them are kept, not dropped
# (user decision 2026-11-21). RandomForest handles a blank natively (scikit-learn >= 1.4).
OPTIONAL_NUMERIC_FEATURES = ["low_weather_go"]

# low_weather_go: 1 if the latest weather-go forecast posted after the baseline note, before
# the baseline target, and before the target first moved, was under this percentage; 0 if at or above it;
# blank if none was posted in time. Same rule as low_weather_go in train_model.py on
# data/weather-go-feature; once both branches are merged, use that one instead.
LOW_WEATHER_GO_PCT = 50
# A later note counts as moving the target if it shifts it by more than this.
TARGET_MOVE_TOLERANCE = pd.Timedelta(hours=1)
RF_PARAMS = {
    "n_estimators": 500,
    "min_samples_leaf": 2,
    "class_weight": "balanced",  # weight each class so both count equally in total
    "random_state": 42,
    "n_jobs": -1,
}
THRESHOLD = 0.5


def rf_features(df: pd.DataFrame, rocket_categories: list[str]) -> pd.DataFrame:
    """Numeric features plus one column per rocket type (missing rocket types -> all zeros).

    An optional input the caller did not supply (e.g. no weather-go forecast yet) is blank.
    """
    absent = {c: np.nan for c in OPTIONAL_NUMERIC_FEATURES if c not in df}
    numeric = df.assign(**absent)[RF_NUMERIC_FEATURES].apply(pd.to_numeric, errors="coerce")
    rockets = pd.get_dummies(
        pd.Categorical(df["rocket_type"], categories=rocket_categories),
        prefix="rocket",
        dtype=float,
    )
    rockets.index = df.index
    return pd.concat([numeric, rockets], axis=1)


def low_weather_go_flag(go_pct: float | None) -> float:
    """1.0 if a weather-go % is under LOW_WEATHER_GO_PCT, 0.0 if not, NaN if there is none.

    For a live prediction, pass the GO % the dashboard user entered (None if left empty).
    """
    if go_pct is None or pd.isna(go_pct):
        return np.nan
    return float(go_pct < LOW_WEATHER_GO_PCT)


def schedule_and_baseline(
    launches: pd.DataFrame, updates: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Schedule notes with their parsed target, and per launch_id the baseline note
    (as in delay_labels(): the latest target in a note posted at least DELAY_BASELINE_DAYS
    before launch; columns target, created_on)."""
    notes = updates.assign(created_on=pd.to_datetime(updates["created_on"], utc=True))
    notes["target"] = pd.to_datetime(
        [parse_note_target(c, t) for c, t in zip(notes["comment"], notes["created_on"])],
        utc=True,
    )
    notes = notes.dropna(subset=["target"]).sort_values("created_on")
    actual = notes["launch_id"].map(launches.set_index("launch_id")["launch_timestamp_utc"])
    early = notes[notes["created_on"] <= actual - pd.Timedelta(days=DELAY_BASELINE_DAYS)]
    return notes, early.groupby("launch_id")[["target", "created_on"]].last()


def forecast_cutoff(launches: pd.DataFrame, updates: pd.DataFrame) -> pd.Series:
    """Per launch_id: the latest time a weather-go forecast may be posted and still be used.

    That is the baseline target, or the first later note that moves the target by more than
    TARGET_MOVE_TOLERANCE, whichever comes first. A forecast posted after a move already
    knows about the delay, so using it would leak the outcome.
    """
    notes, baseline = schedule_and_baseline(launches, updates)
    later = notes.join(baseline.add_suffix("_base"), on="launch_id", how="inner")
    moved = later[
        (later["created_on"] > later["created_on_base"])
        & ((later["target"] - later["target_base"]).abs() > TARGET_MOVE_TOLERANCE)
    ]
    first_move = moved.groupby("launch_id")["created_on"].min()
    return pd.concat([baseline["target"], first_move], axis=1).min(axis=1)


def add_low_weather_go(launches: pd.DataFrame, updates: pd.DataFrame) -> pd.DataFrame:
    """launches with a low_weather_go column (blank where no forecast came in time).

    Forecasts posted before the baseline note are ignored: they were for an earlier target date.
    """
    cutoff = forecast_cutoff(launches, updates)
    since = schedule_and_baseline(launches, updates)[1]["created_on"]
    flags = {
        launch_id: low_weather_go_flag(
            latest_weather_go(updates, launch_id, as_of, since.get(launch_id))
        )
        for launch_id, as_of in cutoff.items()
    }
    return launches.assign(low_weather_go=launches["launch_id"].map(flags).astype(float))


def delay_probability(model: RandomForestClassifier, features: pd.DataFrame) -> np.ndarray:
    return model.predict_proba(features)[:, list(model.classes_).index(1)]


def holdout_metrics(actual: np.ndarray, probability: np.ndarray) -> dict:
    predicted = (probability >= THRESHOLD).astype(int)
    both_classes = len(np.unique(actual)) == 2
    return {
        "accuracy": accuracy_score(actual, predicted),
        "precision": precision_score(actual, predicted, zero_division=0),
        "recall": recall_score(actual, predicted, zero_division=0),
        "f1": f1_score(actual, predicted, zero_division=0),
        "roc_auc": roc_auc_score(actual, probability) if both_classes else None,
        "pr_auc": average_precision_score(actual, probability) if both_classes else None,
    }


def main() -> None:
    spec = MODELS["delay"]
    target = spec["target"]
    launches = load_launches()  # sorted by launch time
    if "low_weather_go" not in launches:
        launches = add_low_weather_go(launches, pd.read_csv(UPDATES_PATH))
    absent = [column for column in RF_NUMERIC_FEATURES if column not in launches]
    if absent:
        raise SystemExit(f"{absent} not in ml_features.csv; re-run fetch_weather.py and "
                         "build_features.py.")

    # Missing-data policy (DATA.md §2): a launch missing any numeric model input is
    # left out of training and evaluation. Missing rocket_type and missing optional
    # inputs (low_weather_go) are kept.
    labelled = launches.dropna(subset=[target])
    required = [c for c in RF_NUMERIC_FEATURES if c not in OPTIONAL_NUMERIC_FEATURES]
    gaps = labelled[required].isna()
    dropped = {column: int(count) for column, count in gaps.sum().items() if count}
    if dropped:
        print(f"  Left out {int(gaps.any(axis=1).sum())} of {len(labelled)} labelled launches "
              f"missing a numeric model input: {dropped}")
    df = labelled[~gaps.any(axis=1)].reset_index(drop=True)
    labels = df[target].astype(int)
    print(f"delay model (RandomForest): {len(df)} labelled launches ({labels.sum()} delays)")

    train_df, test_df = holdout_split(df, spec)
    y_train = train_df[target].astype(int)
    if y_train.nunique() < 2:
        raise SystemExit("Training split has only one class; cannot train.")
    rocket_categories = sorted(train_df["rocket_type"].dropna().unique())
    model = RandomForestClassifier(**RF_PARAMS).fit(
        rf_features(train_df, rocket_categories), y_train
    )

    actual = test_df[target].astype(int).to_numpy()
    probability = delay_probability(model, rf_features(test_df, rocket_categories))
    print(
        f"  Holdout: trained on {len(train_df)} launches up to "
        f"{train_df['launch_timestamp_utc'].max():%Y-%m-%d}, tested on the newest "
        f"{len(test_df)} ({len(test_df) / len(df):.0%}), {actual.sum()} delays"
    )
    for name, value in holdout_metrics(actual, probability).items():
        print(f"    {name}:".ljust(16) + ("n/a (one class in test)" if value is None
                                          else f"{value:.3f}"))

    importance = pd.Series(model.feature_importances_, index=model.feature_names_in_)
    print("  Feature importance (mean impurity decrease):")
    print(importance.sort_values(ascending=False).round(3).to_string())

    # Final model on every labelled launch, as train_model.py does.
    all_categories = sorted(df["rocket_type"].dropna().unique())
    final = RandomForestClassifier(**RF_PARAMS).fit(rf_features(df, all_categories), labels)
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(MODEL_PATH, "wb") as file:
        pickle.dump(
            {
                "model": final,
                "numeric_features": RF_NUMERIC_FEATURES,
                "rocket_categories": all_categories,
                "params": RF_PARAMS,
                "threshold": THRESHOLD,
            },
            file,
        )
    print(f"Saved RandomForest delay model to {MODEL_PATH}")


if __name__ == "__main__":
    main()
