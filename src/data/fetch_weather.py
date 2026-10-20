
import csv
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests


BASE_URL = "https://archive-api.open-meteo.com/v1/archive"

PROJECT_ROOT = Path(__file__).resolve().parents[2]
INPUT_FILE = PROJECT_ROOT / "data" / "raw" / "test_launches.csv"
OUTPUT_FILE = PROJECT_ROOT / "data" / "raw" / "historical_weather.csv"

WEATHER_VARIABLES = [
    "temperature_2m",
    "wind_speed_10m",
    "precipitation",
    "cloud_cover",
    "wind_speed_250hPa",
]


def fetch_weather(latitude, longitude, launch_time):
    # Include the adjacent days for launches near midnight.
    start_date = (launch_time - timedelta(days=1)).date()
    end_date = (launch_time + timedelta(days=1)).date()

    params = {
        "latitude": latitude,
        "longitude": longitude,
        "start_date": str(start_date),
        "end_date": str(end_date),
        "hourly": ",".join(WEATHER_VARIABLES),
        "timezone": "GMT",
    }

    response = requests.get(BASE_URL, params=params, timeout=30)
    response.raise_for_status()

    data = response.json()
    hourly = data["hourly"]

    # Convert returned timestamps into datetime objects.
    times = [
        datetime.fromisoformat(t).replace(tzinfo=timezone.utc)
        for t in hourly["time"]
    ]

    # Find the hourly record closest to launch time.
    position = min(
        range(len(times)),
        key=lambda i: abs(times[i] - launch_time)
    )

    result = {
        "weather_time": times[position].isoformat()
    }

    for variable in WEATHER_VARIABLES:
        values = hourly.get(variable)
        result[variable] = (
            values[position]
            if values is not None and position < len(values)
            else None
        )

    return result


def main():
    results = []

    with open(INPUT_FILE, newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)

        for launch in reader:
            launch_id = launch["launch_id"]

            try:
                latitude = float(launch["latitude"])
                longitude = float(launch["longitude"])

                launch_time = datetime.fromisoformat(
                    launch["launch_time"].replace("Z", "+00:00")
                ).astimezone(timezone.utc)

                weather = fetch_weather(
                    latitude, longitude, launch_time
                )

                row = {
                    "launch_id": launch_id,
                    "launch_time": launch_time.isoformat(),
                    "latitude": latitude,
                    "longitude": longitude,
                }

                row.update(weather)
                results.append(row)

                print(f"Fetched weather for launch {launch_id}")

            except (ValueError, KeyError, requests.RequestException) as error:
                print(f"Failed for launch {launch_id}: {error}")

    if not results:
        print("No weather records collected.")
        return

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    columns = [
        "launch_id",
        "launch_time",
        "latitude",
        "longitude",
        "weather_time",
        *WEATHER_VARIABLES,
    ]

    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(results)

    print(f"Saved {len(results)} records to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
