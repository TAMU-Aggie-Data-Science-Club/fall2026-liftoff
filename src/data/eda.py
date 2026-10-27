"""Print missing-value counts, summary statistics and outcome correlations.

Reads the feature table built by src/data/build_features.py
(data/processed/ml_features.csv). That table is a left join, so launches
without a weather record are kept and their gaps are visible here.
Nothing is written to disk.
"""

from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
FEATURES_PATH = REPO_ROOT / "data" / "processed" / "ml_features.csv"

TARGET = "mission_success"
# launch_time, latitude and longitude repeat launch_timestamp_utc and the launchpad_* columns.
DUPLICATE_COLUMNS = ["launch_time", "latitude", "longitude"]


def missing_table(df: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        {"missing": df.isna().sum(), "pct_missing": (df.isna().mean() * 100).round(1)}
    )


def correlations(df: pd.DataFrame) -> pd.DataFrame:
    """Pearson correlation of each numeric feature with the 0/1 outcome.

    With a binary target this is the point-biserial correlation. Features with
    gaps are compared on the launches that have a value, so n and the number of
    failures among them are shown next to each coefficient. The coefficient is
    NaN when it is undefined: no failures among those launches, or a constant column.
    """
    outcome = df[TARGET].astype(int)
    rows = []
    for column in df.select_dtypes("number").columns:
        present = df[column].notna()
        failures = int((~df.loc[present, TARGET]).sum())
        defined = 0 < failures < present.sum() and df.loc[present, column].nunique() > 1
        r = df.loc[present, column].corr(outcome[present]) if defined else float("nan")
        rows.append(
            {
                "feature": column,
                "n": int(present.sum()),
                "failures": failures,
                "pearson_r": r,
            }
        )
    return pd.DataFrame(rows).set_index("feature").round(3)


def main() -> None:
    features = pd.read_csv(FEATURES_PATH)
    features[TARGET] = features[TARGET].astype(bool)

    print(f"== Feature table: {len(features)} rows, missing values ==")
    print(missing_table(features), end="\n\n")

    no_weather = features[features["weather_time"].isna()]
    print(f"== Launches with no weather record: {len(no_weather)} ==")
    print(no_weather[["launch_id", "rocket_type", "launch_timestamp_utc"]], end="\n\n")

    print("== Outcome counts ==")
    print(features[TARGET].value_counts().rename({True: "success", False: "failure"}), end="\n\n")

    analysed = features.drop(columns=DUPLICATE_COLUMNS)

    print("== Summary statistics (numeric columns) ==")
    print(analysed.describe().T.round(3).to_string(), end="\n\n")

    print("== Pearson correlation with mission_success ==")
    print(correlations(analysed).to_string(), end="\n\n")

    print("== Success rate by rocket type ==")
    by_rocket = analysed.groupby("rocket_type")[TARGET].agg(
        launches="size", failures=lambda s: int((~s).sum()), success_rate="mean"
    )
    by_rocket["success_rate"] = by_rocket["success_rate"].round(3)
    print(by_rocket.sort_values("launches", ascending=False).to_string())


if __name__ == "__main__":
    main()
