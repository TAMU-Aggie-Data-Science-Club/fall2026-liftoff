"""Train baseline XGBoost models for launch success and launch delay; save them to models/baseline_model.pkl."""

import pickle
import re
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb

REPO_ROOT = Path(__file__).resolve().parents[2]
FEATURES_PATH = REPO_ROOT / "data" / "processed" / "ml_features.csv"
UPDATES_PATH = REPO_ROOT / "data" / "raw" / "spacex_launch_updates.csv"
MODEL_PATH = REPO_ROOT / "models" / "baseline_model.pkl"

NUMERIC_FEATURES = [
    "temperature_2m",
    "wind_speed_10m",
    "precipitation",
    "cloud_cover",
    "payload_mass_kg",
]
CATEGORICAL_FEATURES = ["rocket_type"]
FEATURE_COLUMNS = NUMERIC_FEATURES + CATEGORICAL_FEATURES

# Each model: target column, the label value we care about catching, and its name.
MODELS = {
    "success": {"target": "mission_success", "event_value": 0, "event_name": "failures"},
    "delay": {"target": "is_delayed", "event_value": 1, "event_name": "delays"},
}

# Delay definition (team decision 2026-11-08, open to change):
# baseline = latest target time stated in an LL2 note posted at least
# DELAY_BASELINE_DAYS before the actual launch; delayed if the launch came more
# than DELAY_THRESHOLD_HOURS after that baseline. No baseline -> left blank.
DELAY_BASELINE_DAYS = 7
DELAY_THRESHOLD_HOURS = 24

HOLDOUT_FRACTION = 0.2  # newest launches held out for a quick check
PARAMS = {
    "objective": "binary:logistic",
    "eval_metric": "logloss",
    "max_depth": 3,
    "eta": 0.1,
    "seed": 42,
}
NUM_BOOST_ROUND = 200

# Notes that announce a schedule, e.g. "Now targeting Nov 05 at 02:35 UTC",
# "Delayed to NET December 23", "NET October 5, 2023".
SCHEDULE_NOTE = re.compile(
    r"target|\bNET\b|delay|slip|moved|scheduled|recycl|revert", re.IGNORECASE
)
TARGET_DATE = re.compile(
    r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+"
    r"(\d{1,2})(?:st|nd|rd|th)?\b"
    r"(?:,?\s+(\d{4}))?"
    r"(?:\s+at\s+(?:approximately\s+)?(\d{1,2}):(\d{2})(?::(\d{2}))?)?",
    re.IGNORECASE,
)
MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]


def parse_note_target(comment: str, created_on: pd.Timestamp) -> pd.Timestamp | None:
    """Return the launch target a note announces, or None if it gives no exact day."""
    if not isinstance(comment, str) or not SCHEDULE_NOTE.search(comment):
        return None
    match = TARGET_DATE.search(comment)
    if not match:
        return None
    month_name, day, year, hour, minute, second = match.groups()
    month = MONTHS.index(month_name[:3].lower()) + 1
    try:
        date = pd.Timestamp(
            year=int(year) if year else created_on.year, month=month, day=int(day), tz="UTC"
        )
    except ValueError:
        return None
    # Notes rarely give a year: a December note saying "Jan 5" means next January.
    if not year and date < created_on - pd.Timedelta(days=60):
        date = date.replace(year=date.year + 1)
    if hour is None:
        # A day with no time: anything on that day counts as on time.
        return date + pd.Timedelta(days=1)
    return date + pd.Timedelta(hours=int(hour), minutes=int(minute), seconds=int(second or 0))


def delay_labels(launches: pd.DataFrame) -> pd.Series:
    """is_delayed per launch (1/0), or NaN when no target was announced early enough."""
    updates = pd.read_csv(UPDATES_PATH)
    updates["created_on"] = pd.to_datetime(updates["created_on"], utc=True)
    updates["target"] = [
        parse_note_target(comment, created)
        for comment, created in zip(updates["comment"], updates["created_on"])
    ]
    updates = updates.dropna(subset=["target"])
    updates["target"] = pd.to_datetime(updates["target"], utc=True)

    actual = launches.set_index("launch_id")["launch_timestamp_utc"]
    updates["actual"] = updates["launch_id"].map(actual)
    cutoff = updates["actual"] - pd.Timedelta(days=DELAY_BASELINE_DAYS)
    early = updates[updates["created_on"] <= cutoff]
    baseline = early.sort_values("created_on").groupby("launch_id")["target"].last()

    gap = launches["launch_timestamp_utc"] - launches["launch_id"].map(baseline)
    is_delayed = (gap > pd.Timedelta(hours=DELAY_THRESHOLD_HOURS)).astype(float)
    return is_delayed.where(gap.notna())


def load_launches() -> pd.DataFrame:
    df = pd.read_csv(FEATURES_PATH)
    df["mission_success"] = df["mission_success"].map(
        {True: 1, False: 0, "True": 1, "False": 0}
    )
    df["launch_timestamp_utc"] = pd.to_datetime(df["launch_timestamp_utc"], utc=True)
    df["is_delayed"] = delay_labels(df)
    return df.sort_values("launch_timestamp_utc").reset_index(drop=True)


def prepare_features(df: pd.DataFrame, rocket_categories: list[str]) -> pd.DataFrame:
    """Select model inputs; rocket types unseen in training become missing."""
    features = df[FEATURE_COLUMNS].copy()
    for column in NUMERIC_FEATURES:
        features[column] = pd.to_numeric(features[column], errors="coerce")
    features["rocket_type"] = pd.Categorical(
        features["rocket_type"], categories=rocket_categories
    )
    return features


def class_weights(labels: pd.Series) -> np.ndarray:
    # Weight each class so both count equally in total; the rare class gets weighted up.
    counts = labels.value_counts()
    return labels.map(len(labels) / (len(counts) * counts)).to_numpy()


def train(df: pd.DataFrame, target: str, rocket_categories: list[str]) -> xgb.Booster:
    labels = df[target].astype(int)
    dtrain = xgb.DMatrix(
        prepare_features(df, rocket_categories),
        label=labels,
        weight=class_weights(labels),
        enable_categorical=True,
    )
    return xgb.train(PARAMS, dtrain, num_boost_round=NUM_BOOST_ROUND)


def predict_probability(
    booster: xgb.Booster, df: pd.DataFrame, rocket_categories: list[str]
) -> np.ndarray:
    """Probability that the target is 1 (success for the success model, delayed for the delay model)."""
    dmatrix = xgb.DMatrix(
        prepare_features(df, rocket_categories), enable_categorical=True
    )
    return booster.predict(dmatrix)


def roc_auc(labels: np.ndarray, scores: np.ndarray) -> float | None:
    # Rank-based AUC: chance that a random positive scores above a random negative.
    n_pos = (labels == 1).sum()
    n_neg = (labels == 0).sum()
    if n_pos == 0 or n_neg == 0:
        return None
    ranks = pd.Series(scores).rank().to_numpy()
    return (ranks[labels == 1].sum() - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg)


def report_holdout(df: pd.DataFrame, spec: dict, rocket_categories: list[str]) -> None:
    split = int(len(df) * (1 - HOLDOUT_FRACTION))
    train_df, test_df = df.iloc[:split], df.iloc[split:]
    booster = train(train_df, spec["target"], rocket_categories)

    labels = test_df[spec["target"]].astype(int).to_numpy()
    probs = predict_probability(booster, test_df, rocket_categories)
    predicted_event = (probs >= 0.5).astype(int) == spec["event_value"]
    actual_event = labels == spec["event_value"]
    auc = roc_auc(labels, probs)
    name = spec["event_name"]

    print(
        f"  Holdout check: trained on {len(train_df)} launches up to "
        f"{train_df['launch_timestamp_utc'].max():%Y-%m-%d}, "
        f"tested on the newest {len(test_df)}"
    )
    print(f"    {name.capitalize()} in test set:".ljust(28) + f"{actual_event.sum()}")
    print(f"    Accuracy:".ljust(28) + f"{(predicted_event == actual_event).mean():.3f}")
    print(f"    {name.capitalize()} caught:".ljust(28)
          + f"{(predicted_event & actual_event).sum()} of {actual_event.sum()}")
    print(f"    False alarms:".ljust(28) + f"{(predicted_event & ~actual_event).sum()}")
    print(f"    ROC-AUC:".ljust(28) + (f"{auc:.3f}" if auc is not None
                                        else "n/a (test set has only one outcome)"))


def main() -> None:
    launches = load_launches()
    rocket_categories = sorted(launches["rocket_type"].dropna().unique())
    saved_models = {}

    for name, spec in MODELS.items():
        # Launches without a label for this target have nothing to learn from.
        df = launches.dropna(subset=[spec["target"]]).reset_index(drop=True)
        events = (df[spec["target"]] == spec["event_value"]).sum()
        print(f"{name} model: {len(df)} labelled launches ({events} {spec['event_name']})")
        report_holdout(df, spec, rocket_categories)
        saved_models[name] = {
            "booster": train(df, spec["target"], rocket_categories),
            "target": spec["target"],
            "trained_on_rows": len(df),
        }

    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(MODEL_PATH, "wb") as file:
        pickle.dump(
            {
                "models": saved_models,
                "feature_columns": FEATURE_COLUMNS,
                "rocket_categories": rocket_categories,
                "params": PARAMS,
                "num_boost_round": NUM_BOOST_ROUND,
                "delay_definition": {
                    "baseline_days_before_launch": DELAY_BASELINE_DAYS,
                    "threshold_hours": DELAY_THRESHOLD_HOURS,
                },
            },
            file,
        )
    print(f"Saved {', '.join(saved_models)} models to {MODEL_PATH}")


if __name__ == "__main__":
    main()
