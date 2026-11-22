
from pathlib import Path
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]

SPACEX_FILE = PROJECT_ROOT / "data" / "raw" / "spacex_launches.csv"
WEATHER_FILE = PROJECT_ROOT / "data" / "raw" / "historical_weather.csv"
OUTPUT_FILE = PROJECT_ROOT / "data" / "processed" / "ml_features.csv"


def main():
    spacex = pd.read_csv(SPACEX_FILE)
    weather = pd.read_csv(WEATHER_FILE)

    # Check for duplicate IDs before merging
    if spacex["launch_id"].duplicated().any():
        raise ValueError("Duplicate launch IDs in SpaceX data.")

    if weather["launch_id"].duplicated().any():
        raise ValueError("Duplicate launch IDs in weather data.")

    # Merge launch details and matching weather
    merged = pd.merge(
        spacex,
        weather,
        on="launch_id",
        how="left",
        suffixes=("", "_weather"),
        validate="one_to_one",
        indicator=True
    )

    matched = (merged["_merge"] == "both")
    print(f"SpaceX launches: {len(spacex)}")
    print(f"Weather records: {len(weather)}")
    print(f"Matched launches: {matched.sum()}")
    print(f"Missing weather matches: {(~matched).sum()}")

    # Verify that the matched weather belongs to the same launch
    launch_times = pd.to_datetime(
        merged["launch_timestamp_utc"], utc=True
    )
    weather_launch_times = pd.to_datetime(
        merged["launch_time"], utc=True
    )

    time_matches = launch_times == weather_launch_times

    lat_matches = (
        merged["launchpad_latitude"] - merged["latitude"]
    ).abs() < 0.001

    lon_matches = (
        merged["launchpad_longitude"] - merged["longitude"]
    ).abs() < 0.001

    invalid_matches = matched & ~(
        time_matches & lat_matches & lon_matches
    )

    if invalid_matches.any():
        raise ValueError(
            f"{invalid_matches.sum()} launches have mismatched "
            "times or coordinates."
        )

    merged = merged.drop(columns=["_merge"])

    # Save output
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(OUTPUT_FILE, index=False)

    print(f"Final dataset: {len(merged)} rows")
    print(f"Saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
