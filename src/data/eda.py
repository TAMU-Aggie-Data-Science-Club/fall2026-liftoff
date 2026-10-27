"""Print missing-value counts, summary statistics and outcome correlations.

Missing values come from the raw CSVs (the cleaned file has already lost its
gaps). Summary statistics and correlations come from the cleaned launch table,
data/processed/cleaned_launches.csv. Nothing is written to disk.
"""

from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
LAUNCHES_PATH = REPO_ROOT / "data" / "raw" / "spacex_launches.csv"
WEATHER_PATH = REPO_ROOT / "data" / "raw" / "historical_weather.csv"
CLEANED_PATH = REPO_ROOT / "data" / "processed" / "cleaned_launches.csv"

TARGET = "mission_success"


def missing_table(df: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        {"missing": df.isna().sum(), "pct_missing": (df.isna().mean() * 100).round(1)}
    )


def correlations(df: pd.DataFrame) -> pd.DataFrame:
    """Pearson correlation of each numeric feature with the 0/1 outcome.

    With a binary target this is the point-biserial correlation. Features with
    gaps are compared on the launches that have a value, so n and the number of
    failures among them are shown next to each coefficient.
    """
    outcome = df[TARGET].astype(int)
    rows = []
    for column in df.select_dtypes("number").columns:
        present = df[column].notna()
        failures = int((~df.loc[present, TARGET]).sum())
        # Undefined (NaN) when the outcome never varies among the launches with a value.
        r = df.loc[present, column].corr(outcome[present]) if 0 < failures < present.sum() else float("nan")
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
    launches = pd.read_csv(LAUNCHES_PATH)
    weather = pd.read_csv(WEATHER_PATH)
    cleaned = pd.read_csv(CLEANED_PATH)
    cleaned[TARGET] = cleaned[TARGET].astype(bool)

    print(f"== Raw launches: {len(launches)} rows, missing values ==")
    print(missing_table(launches), end="\n\n")
    print(f"== Raw weather: {len(weather)} rows, missing values ==")
    print(missing_table(weather), end="\n\n")

    no_weather = launches[~launches["launch_id"].isin(weather["launch_id"])]
    print(f"== Launches with no weather record: {len(no_weather)} ==")
    print(no_weather[["launch_id", "rocket_type", "launch_timestamp_utc"]], end="\n\n")

    print(f"== Cleaned table: {len(cleaned)} rows ==")
    print(f"Rows lost from raw launches: {len(launches) - len(cleaned)}\n")

    print("== Outcome counts ==")
    print(cleaned[TARGET].value_counts().rename({True: "success", False: "failure"}), end="\n\n")

    print("== Summary statistics (numeric columns) ==")
    print(cleaned.describe().T.round(3).to_string(), end="\n\n")

    print("== Pearson correlation with mission_success ==")
    print(correlations(cleaned).to_string(), end="\n\n")

    print("== Success rate by rocket type ==")
    by_rocket = cleaned.groupby("rocket_type")[TARGET].agg(
        launches="size", failures=lambda s: int((~s).sum()), success_rate="mean"
    )
    by_rocket["success_rate"] = by_rocket["success_rate"].round(3)
    print(by_rocket.sort_values("launches", ascending=False).to_string())


if __name__ == "__main__":
    main()
