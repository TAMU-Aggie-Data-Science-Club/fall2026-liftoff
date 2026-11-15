
"""Evaluate XGBoost launch prediction models using cross-validation."""
from itertools import product
import json
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb

from sklearn.metrics import (
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
)
from sklearn.model_selection import TimeSeriesSplit

from train_model import (
    MODELS,
    PARAMS,
    NUM_BOOST_ROUND,
    FEATURE_COLUMNS,
    load_launches,
    prepare_features,
    class_weights,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
REPORT_PATH = REPO_ROOT / "reports" / "model_evaluation.json"

N_SPLITS = 5

def cross_validate(df, spec, params=PARAMS, num_boost_round=NUM_BOOST_ROUND):
    """Evaluate a model across multiple time-ordered splits."""

    target = spec["target"]
    event_value = spec["event_value"]

    # Only use launches with known outcomes
    df = df.dropna(subset=[target]).sort_values(
        "launch_timestamp_utc"
    ).reset_index(drop=True)

    if len(df) < N_SPLITS + 1:
        print(f"Not enough labelled launches for {target}.")
        return []

    splitter = TimeSeriesSplit(n_splits=N_SPLITS)
    results = []

    for fold, (train_idx, test_idx) in enumerate(
        splitter.split(df), start=1
    ):
        train_df = df.iloc[train_idx]
        test_df = df.iloc[test_idx]

        y_train = train_df[target].astype(int)
        y_test = test_df[target].astype(int)

        # XGBoost needs both classes in the training data
        if y_train.nunique() < 2:
            print(f"Fold {fold}: skipped (training has only one class)")
            continue

        # Learn rocket categories from training data only
        rocket_categories = sorted(
            train_df["rocket_type"].dropna().unique().tolist()
        )

        X_train = prepare_features(train_df, rocket_categories)
        X_test = prepare_features(test_df, rocket_categories)

        dtrain = xgb.DMatrix(
            X_train,
            label=y_train,
            weight=class_weights(y_train),
            enable_categorical=True,
        )

        dtest = xgb.DMatrix(
            X_test,
            enable_categorical=True,
        )

        # Train a new model for this fold
        model = xgb.train(
            params,
            dtrain,
            num_boost_round=num_boost_round,
        )

        # XGBoost probabilities correspond to label 1
        probabilities = model.predict(dtest)

        # Convert probabilities to the event we care about
        event_probabilities = (
            probabilities if event_value == 1
            else 1 - probabilities
        )

        actual = (y_test.to_numpy() == event_value).astype(int)
        predicted = (event_probabilities >= 0.5).astype(int)

        result = {
            "fold": fold,
            "train_size": len(train_df),
            "test_size": len(test_df),
            "events_in_test": int(actual.sum()),
            "precision": float(
                precision_score(actual, predicted, zero_division=0)
            ),
            "recall": float(
                recall_score(actual, predicted, zero_division=0)
            ),
            "f1": float(
                f1_score(actual, predicted, zero_division=0)
            ),
            "roc_auc": (
                float(roc_auc_score(actual, event_probabilities))
                if len(np.unique(actual)) == 2
                else None
            ),
        }

        results.append(result)

        print(
            f"Fold {fold}: "
            f"Precision={result['precision']:.3f}, "
            f"Recall={result['recall']:.3f}, "
            f"F1={result['f1']:.3f}, "
            f"ROC-AUC={result['roc_auc']}"
        )

    return results


def tune_hyperparameters(df, spec):
    """Find the best XGBoost settings using time-ordered cross-validation."""

    # Small search grid to keep training reasonably manageable
    param_grid = {
        "max_depth": [2, 3, 4],
        "eta": [0.05, 0.1],
        "num_boost_round": [100, 200],
    }

    best_params = None
    best_rounds = None
    best_score = -1
    tuning_results = []

    for depth, eta, rounds in product(
        param_grid["max_depth"],
        param_grid["eta"],
        param_grid["num_boost_round"],
    ):
        params = PARAMS.copy()
        params["max_depth"] = depth
        params["eta"] = eta

        folds = cross_validate(
            df,
            spec,
            params=params,
            num_boost_round=rounds,
        )

        # Only use folds where ROC-AUC was measurable
        auc_scores = [
            fold["roc_auc"]
            for fold in folds
            if fold["roc_auc"] is not None
        ]

        mean_auc = (
            float(np.mean(auc_scores))
            if auc_scores
            else None
        )

        tuning_results.append({
            "max_depth": depth,
            "eta": eta,
            "num_boost_round": rounds,
            "mean_roc_auc": mean_auc,
            "valid_auc_folds": len(auc_scores),
        })

        print(
            f"Tuning: depth={depth}, eta={eta}, rounds={rounds}, "
            f"mean ROC-AUC={mean_auc}"
        )

        if mean_auc is not None and mean_auc > best_score:
            best_score = mean_auc
            best_params = params.copy()
            best_rounds = rounds

    return {
        "best_params": best_params,
        "best_num_boost_round": best_rounds,
        "best_roc_auc": best_score if best_params is not None else None,
        "results": tuning_results,
    }

def get_feature_importance(df, spec, params, num_boost_round):
    """Train a model and return feature importance rankings."""

    target = spec["target"]

    # Only use launches with known outcomes
    df = df.dropna(subset=[target]).sort_values(
        "launch_timestamp_utc"
    ).reset_index(drop=True)

    # Make sure both outcome classes are represented
    if df[target].nunique() < 2:
        return []

    rocket_categories = sorted(
        df["rocket_type"].dropna().unique().tolist()
    )

    features = prepare_features(df, rocket_categories)
    labels = df[target].astype(int)

    dtrain = xgb.DMatrix(
        features,
        label=labels,
        weight=class_weights(labels),
        enable_categorical=True,
    )

    model = xgb.train(
        params,
        dtrain,
        num_boost_round=num_boost_round,
    )

    # Gain measures how much each feature improves tree splits
    importance = model.get_score(importance_type="gain")

    rankings = [
        {
            "feature": feature,
            "importance": float(importance.get(feature, 0.0)),
        }
        for feature in FEATURE_COLUMNS
    ]

    rankings.sort(
        key=lambda item: item["importance"],
        reverse=True,
    )

    return rankings

def evaluate_holdout(train_df, test_df, spec, params, num_boost_round):
    """Train on older launches and evaluate on untouched newer launches."""

    target = spec["target"]
    event_value = spec["event_value"]

    y_train = train_df[target].astype(int)
    y_test = test_df[target].astype(int)

    if y_train.nunique() < 2:
        print(f"Skipping {target}: training data has only one class.")
        return None

    rocket_categories = sorted(
        train_df["rocket_type"].dropna().unique().tolist()
    )

    dtrain = xgb.DMatrix(
        prepare_features(train_df, rocket_categories),
        label=y_train,
        weight=class_weights(y_train),
        enable_categorical=True,
    )

    dtest = xgb.DMatrix(
        prepare_features(test_df, rocket_categories),
        enable_categorical=True,
    )

    model = xgb.train(
        params,
        dtrain,
        num_boost_round=num_boost_round,
    )

    # XGBoost predicts the probability of label 1.
    probabilities = model.predict(dtest)

    # Evaluate failures (0) or delays (1), depending on the model.
    event_probabilities = (
        probabilities if event_value == 1
        else 1 - probabilities
    )

    actual = (y_test.to_numpy() == event_value).astype(int)
    predicted = (event_probabilities >= 0.5).astype(int)

    return {
        "train_size": len(train_df),
        "test_size": len(test_df),
        "events_in_test": int(actual.sum()),
        "precision": float(
            precision_score(actual, predicted, zero_division=0)
        ),
        "recall": float(
            recall_score(actual, predicted, zero_division=0)
        ),
        "f1": float(
            f1_score(actual, predicted, zero_division=0)
        ),
        "roc_auc": (
            float(roc_auc_score(actual, event_probabilities))
            if len(np.unique(actual)) == 2
            else None
        ),
    }


def main():
    """Run tuning, cross-validation, and evaluation for both targets."""

    launches = load_launches()
    report = {}

    for name, spec in MODELS.items():
        print(f"\n{'=' * 50}")
        print(f"Evaluating {name.upper()} model")
        print(f"{'=' * 50}")

        # Use only launches with known outcomes, sorted by date.
        df = launches.dropna(
            subset=[spec["target"]]
        ).sort_values(
            "launch_timestamp_utc"
        ).reset_index(drop=True)

        # Reserve newest 20% for final evaluation.
        split = int(len(df) * 0.8)
        train_df = df.iloc[:split].copy()
        test_df = df.iloc[split:].copy()

        if (
            len(train_df) < N_SPLITS + 1
            or len(test_df) == 0
            or train_df[spec["target"]].nunique() < 2
        ):
            print("Insufficient training or testing data. Skipping.")
            report[name] = {"status": "insufficient_data"}
            continue

        print("\n1. Tuning hyperparameters...")
        tuning = tune_hyperparameters(train_df, spec)

        # Fall back to baseline settings if ROC-AUC is undefined.
        best_params = tuning["best_params"] or PARAMS.copy()
        best_rounds = (
            tuning["best_num_boost_round"] or NUM_BOOST_ROUND
        )

        print("\n2. Cross-validating selected parameters...")
        cv_results = cross_validate(
            train_df,
            spec,
            params=best_params,
            num_boost_round=best_rounds,
        )

        print("\n3. Evaluating untouched holdout...")
        holdout = evaluate_holdout(
            train_df,
            test_df,
            spec,
            params=best_params,
            num_boost_round=best_rounds,
        )

        print(f"Holdout metrics: {holdout}")

        print("\n4. Calculating feature importance...")
        importance = get_feature_importance(
            train_df,
            spec,
            params=best_params,
            num_boost_round=best_rounds,
        )

        report[name] = {
            "target": spec["target"],
            "event_value": spec["event_value"],
            "best_params": best_params,
            "best_num_boost_round": best_rounds,
            "tuning_results": tuning["results"],
            "cross_validation": cv_results,
            "holdout_metrics": holdout,
            "feature_importance": importance,
        }

    # Export evaluation report as JSON.
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(REPORT_PATH, "w", encoding="utf-8") as file:
        json.dump(report, file, indent=2)

    print(f"\nEvaluation report saved to {REPORT_PATH}")


if __name__ == "__main__":
    main()
