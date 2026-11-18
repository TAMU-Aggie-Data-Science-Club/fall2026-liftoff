"""Train the baseline XGBoost launch-delay model (on time vs delayed); save it to models/baseline_model.pkl."""

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
# One model: on time (0) vs delayed (1). The old success/failure model was dropped
# (2026-11-17); in-flight failures are labelled by launch timing like any other launch.
MODELS = {
    "delay": {"target": "is_delayed", "event_value": 1, "event_name": "delays"},
}

# Delay definition (team decision 2026-11-17, open to change):
# baseline = latest target time stated in an LL2 note posted at least
# DELAY_BASELINE_DAYS before the actual launch; delayed if the launch came more
# than the provider's threshold after that baseline. No baseline -> left blank.
# Labels are by timing only: a launch that failed in flight but lifted off on time is on time.
DELAY_BASELINE_DAYS = 7
# Threshold depends on the launch provider: SpaceX 3 days; NASA and every other
# provider 7 days. Launches without a launch_provider column count as SpaceX, since
# fetch_spacex.py only fetches SpaceX launches today.
DELAY_THRESHOLD_HOURS_BY_PROVIDER = {"SpaceX": 72}
DEFAULT_DELAY_THRESHOLD_HOURS = 7 * 24
DEFAULT_PROVIDER = "SpaceX"

# Launches left out of training (they stay in the data files).
EXCLUDED_LAUNCHES = {
    # Amos-6: exploded on the pad during a pre-launch test, so it never launched.
    # Left out as an outlier (PM decision, 2026-11-08).
    "3622669f-6e06-467a-86f3-47b56b1114c1",
}

# Holdout = newest launches. Start with HOLDOUT_FRACTION; if that holds fewer than
# MIN_TEST_EVENTS events, move the cutoff earlier, up to MAX_HOLDOUT_FRACTION.
HOLDOUT_FRACTION = 0.2
MAX_HOLDOUT_FRACTION = 0.4
MIN_TEST_EVENTS = 10
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
# Notes that name the launch date without those words, e.g. "GO for launch on June 18",
# "Added launch window for February 16", "Next opportunity on April 19".
LAUNCH_DATE_NOTE = re.compile(
    r"\bgo for\b|\bwindow\b|launch(?:ing)? on|\battempt\b|opportunit|launch time|\bT-0\b|confirmed"
    r"|planned for|pushing to|moving to|back on|expected to",
    re.IGNORECASE,
)
# ...but not ones that cancel a date, e.g. "No longer listed for July 15",
# "Standing down from the August 28 launch opportunities".
NOT_A_TARGET = re.compile(
    r"no longer|standing down|stand down|\bno launch\b|not in position", re.IGNORECASE
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
    if not isinstance(comment, str):
        return None
    if not SCHEDULE_NOTE.search(comment) and (
        not LAUNCH_DATE_NOTE.search(comment) or NOT_A_TARGET.search(comment)
    ):
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


def delay_threshold(launches: pd.DataFrame) -> pd.Series:
    """Per-launch slip allowed before a launch counts as delayed (SpaceX 72 h, others 7 days)."""
    if "launch_provider" in launches:
        provider = launches["launch_provider"].fillna(DEFAULT_PROVIDER)
    else:
        provider = pd.Series(DEFAULT_PROVIDER, index=launches.index)
    hours = provider.map(DELAY_THRESHOLD_HOURS_BY_PROVIDER).fillna(DEFAULT_DELAY_THRESHOLD_HOURS)
    return pd.to_timedelta(hours, unit="h")


def schedule_notes() -> pd.DataFrame:
    """Every LL2 schedule note that names a launch date, with its parsed target time."""
    updates = pd.read_csv(UPDATES_PATH)
    updates["created_on"] = pd.to_datetime(updates["created_on"], utc=True)
    updates["target"] = [
        parse_note_target(comment, created)
        for comment, created in zip(updates["comment"], updates["created_on"])
    ]
    updates = updates.dropna(subset=["target"])
    updates["target"] = pd.to_datetime(updates["target"], utc=True)
    return updates.sort_values("created_on")


def baseline_notes(launches: pd.DataFrame) -> pd.DataFrame:
    """Per launch_id: the baseline target and when it was announced (created_on).

    The baseline is the latest target in a note posted at least DELAY_BASELINE_DAYS
    before the actual launch. Launches without such a note are absent.
    """
    updates = schedule_notes()
    actual = launches.set_index("launch_id")["launch_timestamp_utc"]
    updates["actual"] = updates["launch_id"].map(actual)
    cutoff = updates["actual"] - pd.Timedelta(days=DELAY_BASELINE_DAYS)
    early = updates[updates["created_on"] <= cutoff]
    return early.groupby("launch_id")[["target", "created_on"]].last()


def delay_labels(launches: pd.DataFrame) -> pd.Series:
    """is_delayed per launch (1/0), or NaN when no target was announced early enough."""
    baseline = baseline_notes(launches)["target"]

    gap = launches["launch_timestamp_utc"] - launches["launch_id"].map(baseline)
    is_delayed = (gap > delay_threshold(launches)).astype(float)
    return is_delayed.where(gap.notna())


def load_launches() -> pd.DataFrame:
    df = pd.read_csv(FEATURES_PATH)
    df = df[~df["launch_id"].isin(EXCLUDED_LAUNCHES)].copy()
    df["mission_success"] = df["mission_success"].map(
        {True: 1, False: 0, "True": 1, "False": 0}
    )
    df["launch_timestamp_utc"] = pd.to_datetime(df["launch_timestamp_utc"], utc=True)
    df["is_delayed"] = delay_labels(df)
    return df.sort_values("launch_timestamp_utc").reset_index(drop=True)


def usable_launches(
    launches: pd.DataFrame, target: str, numeric_features: list[str] = NUMERIC_FEATURES
) -> pd.DataFrame:
    """Labelled launches with every numeric model input present, sorted by launch time.

    Missing-data policy (DATA.md §2): a launch missing a numeric value the model uses
    is left out of training and evaluation. Text/category gaps (rocket_type) are kept.
    The data files themselves keep every launch.
    """
    labelled = launches.dropna(subset=[target])
    missing = labelled[numeric_features].isna()
    dropped = {column: int(count) for column, count in missing.sum().items() if count}
    if dropped:
        print(f"  Left out {int(missing.any(axis=1).sum())} of {len(labelled)} labelled "
              f"launches missing a numeric model input: {dropped}")
    complete = labelled[~missing.any(axis=1)]
    return complete.sort_values("launch_timestamp_utc").reset_index(drop=True)


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
    """Probability that the target is 1 (delayed)."""
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


def holdout_split(df: pd.DataFrame, spec: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split date-sorted launches into older train / newer test, keeping time order.

    The newest HOLDOUT_FRACTION is the starting test set. If it has fewer than
    MIN_TEST_EVENTS events, the cutoff moves earlier one launch at a time until it
    does, but the test set never exceeds MAX_HOLDOUT_FRACTION.
    """
    is_event = (df[spec["target"]] == spec["event_value"]).to_numpy()
    events_from = np.cumsum(is_event[::-1])[::-1]  # events in df.iloc[i:]
    split = int(len(df) * (1 - HOLDOUT_FRACTION))
    earliest = int(len(df) * (1 - MAX_HOLDOUT_FRACTION))
    while split > earliest and events_from[split] < MIN_TEST_EVENTS:
        split -= 1
    return df.iloc[:split], df.iloc[split:]


def report_holdout(df: pd.DataFrame, spec: dict, rocket_categories: list[str]) -> None:
    train_df, test_df = holdout_split(df, spec)
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
        f"tested on the newest {len(test_df)} ({len(test_df) / len(df):.0%})"
    )
    if actual_event.sum() < MIN_TEST_EVENTS:
        print(f"    Warning: fewer than {MIN_TEST_EVENTS} {name} even with a "
              f"{MAX_HOLDOUT_FRACTION:.0%} holdout; treat these numbers as rough.")
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
        # Unlabelled launches have nothing to learn from; incomplete ones are left out (DATA.md §2).
        df = usable_launches(launches, spec["target"])
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
                    "threshold_hours_by_provider": DELAY_THRESHOLD_HOURS_BY_PROVIDER,
                    "default_threshold_hours": DEFAULT_DELAY_THRESHOLD_HOURS,
                },
            },
            file,
        )
    print(f"Saved {', '.join(saved_models)} models to {MODEL_PATH}")


if __name__ == "__main__":
    main()
