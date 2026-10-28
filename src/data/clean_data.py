from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
LAUNCHES_PATH = REPO_ROOT / "data" / "raw" / "spacex_launches.csv"
WEATHER_PATH = REPO_ROOT / "data" / "raw" / "historical_weather.csv"
OUTPUT_PATH = REPO_ROOT / "data" / "interim" / "cleaned_launches.csv"

KMH_TO_MS = 1 / 3.6

# Raw Open-Meteo column -> changed column name to include unit of measurement.
WEATHER_COLUMNS = {
    "temperature_2m": "temperature_2m_c",
    "wind_speed_10m": "wind_speed_10m_ms",
    "precipitation": "precipitation_mm",
    "cloud_cover": "cloud_cover_pct",
    "high_altitude_wind_assumed": "high_altitude_wind_assumed_ms",
}

# Rows missing any of these are dropped. Payload mass is an important value but most are missing so it can be treated as null.
REQUIRED_COLUMNS = [
    "launch_id",
    "rocket_type",
    "launch_timestamp_utc",
    "launchpad_latitude",
    "launchpad_longitude",
    "mission_success",
    "weather_time",
    *WEATHER_COLUMNS.values(),
]


def load_raw() -> pd.DataFrame:
    launches = pd.read_csv(LAUNCHES_PATH)
    weather = pd.read_csv(WEATHER_PATH)
    # The weather file repeats launch time and pad location; keep the launch file's copy.
    weather = weather.drop(columns=["launch_time", "latitude", "longitude"])
    return launches.merge(weather, on="launch_id", how="inner")


def parse_types(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for column in ["launch_timestamp_utc", "weather_time"]:
        df[column] = pd.to_datetime(df[column], utc=True, errors="coerce")
    numeric = ["payload_mass_kg", "launchpad_latitude", "launchpad_longitude", *WEATHER_COLUMNS]
    for column in numeric:
        df[column] = pd.to_numeric(df[column], errors="coerce")
    df["mission_success"] = df["mission_success"].map(
        {True: True, False: False, "True": True, "False": False}
    )
    return df


def normalize_units(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    # Open-Meteo reports wind in km/h. Temperature (C), precipitation (mm),
    # cloud cover (%) and payload mass (kg) are already in the target units.
    df["wind_speed_10m"] = df["wind_speed_10m"] * KMH_TO_MS
    df["high_altitude_wind_assumed"] = df["high_altitude_wind_assumed"] * KMH_TO_MS
    return df.rename(columns=WEATHER_COLUMNS)


def drop_invalid(df: pd.DataFrame) -> pd.DataFrame:
    df = df.drop_duplicates(subset="launch_id")
    df = df.dropna(subset=REQUIRED_COLUMNS)
    valid = (
        df["launchpad_latitude"].between(-90, 90)
        & df["launchpad_longitude"].between(-180, 180)
        & (df["wind_speed_10m_ms"] >= 0)
        & (df["high_altitude_wind_assumed_ms"] >= 0)
        & (df["precipitation_mm"] >= 0)
        & df["cloud_cover_pct"].between(0, 100)
    )
    df = df[valid].copy()
    # A non-positive payload mass is a bad value, not a reason to drop the launch.
    df.loc[df["payload_mass_kg"] <= 0, "payload_mass_kg"] = None
    return df


def main() -> None:
    raw = load_raw()
    cleaned = drop_invalid(normalize_units(parse_types(raw)))
    cleaned = cleaned.sort_values("launch_timestamp_utc").reset_index(drop=True)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    cleaned.to_csv(OUTPUT_PATH, index=False)
    print(f"Kept {len(cleaned)} of {len(raw)} launches; wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
