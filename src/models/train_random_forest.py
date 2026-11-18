"""Train a RandomForest launch-delay classifier (on time vs delayed) and report holdout metrics.

Uses the same labels, launches and time-ordered holdout as train_model.py, so its
numbers can be compared with the XGBoost model. It also uses the high-altitude wind
(upper_wind_max_kmh). The rare delayed class is upweighted with class_weight="balanced".
Launches missing any numeric input are left out (DATA.md §2). The model is retrained on
all usable launches and saved to models/random_forest_model.pkl.
"""

import pickle
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

from train_model import MODELS, NUMERIC_FEATURES, holdout_split, load_launches

REPO_ROOT = Path(__file__).resolve().parents[2]
MODEL_PATH = REPO_ROOT / "models" / "random_forest_model.pkl"

# XGBoost's numeric features plus the high-altitude wind (skipped if already listed).
RF_NUMERIC_FEATURES = NUMERIC_FEATURES + [
    column for column in ["upper_wind_max_kmh"] if column not in NUMERIC_FEATURES
]
RF_PARAMS = {
    "n_estimators": 500,
    "min_samples_leaf": 2,
    "class_weight": "balanced",  # weight each class so both count equally in total
    "random_state": 42,
    "n_jobs": -1,
}
THRESHOLD = 0.5


def rf_features(df: pd.DataFrame, rocket_categories: list[str]) -> pd.DataFrame:
    """Numeric features plus one column per rocket type (missing rocket types -> all zeros)."""
    numeric = df[RF_NUMERIC_FEATURES].apply(pd.to_numeric, errors="coerce")
    rockets = pd.get_dummies(
        pd.Categorical(df["rocket_type"], categories=rocket_categories),
        prefix="rocket",
        dtype=float,
    )
    rockets.index = df.index
    return pd.concat([numeric, rockets], axis=1)


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
    absent = [column for column in RF_NUMERIC_FEATURES if column not in launches]
    if absent:
        raise SystemExit(f"{absent} not in ml_features.csv; re-run fetch_weather.py and "
                         "build_features.py.")

    # Missing-data policy (DATA.md §2): a launch missing any numeric model input is
    # left out of training and evaluation. Missing rocket_type is kept.
    labelled = launches.dropna(subset=[target])
    gaps = labelled[RF_NUMERIC_FEATURES].isna()
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
