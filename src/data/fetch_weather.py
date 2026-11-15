
import bisect
import csv
import io
import math
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import requests


BASE_URL = "https://archive-api.open-meteo.com/v1/archive"
# The ERA5 archive lags about 5 days, so the newest launches fall back to this one.
RECENT_URL = "https://historical-forecast-api.open-meteo.com/v1/forecast"

# NOAA IGRA2 radiosonde archive: measured winds from the ground to balloon burst
# (usually 25-35 km), released at about 00 and 12 UTC.
IGRA_URL = "https://www.ncei.noaa.gov/pub/data/igra/data/data-por/{station}-data.txt.zip"
IGRA_STATIONS = {
    "USM00074794": (28.4667, -80.5500),  # Cape Kennedy, for Cape Canaveral / KSC
    "USM00072393": (34.7500, -120.5666),  # Vandenberg AFB
    "USM00072250": (25.9167, -97.4192),  # Brownsville, for Starbase
    "RMM00091366": (8.7333, 167.7333),  # Kwajalein
}
# Longest gap between a launch and the radiosonde used for it
MAX_SOUNDING_GAP = timedelta(hours=12)
# A sounding that reaches this height is preferred over a nearer one that bursts lower
PREFERRED_TOP_M = 20_000
UPPER_WIND_HEIGHTS_M = list(range(2_000, 30_001, 2_000))
MS_TO_KMH = 3.6
IGRA_MISSING = -9999

PROJECT_ROOT = Path(__file__).resolve().parents[2]
IGRA_DIR = PROJECT_ROOT / "data" / "raw" / "igra"
INPUT_FILE = PROJECT_ROOT / "data" / "raw" / "spacex_launches.csv"
OUTPUT_FILE = PROJECT_ROOT / "data" / "raw" / "historical_weather.csv"

WEATHER_VARIABLES = [
    "temperature_2m",
    "wind_speed_10m",
    "precipitation",
    "cloud_cover",
]

UPPER_WIND_COLUMNS = [
    "upper_wind_station",
    "upper_wind_station_distance_km",
    "upper_wind_sounding_time",
    "upper_wind_sounding_offset_h",
    "upper_wind_top_km",
    "upper_wind_max_kmh",
    "upper_wind_max_alt_km",
]
for _height in UPPER_WIND_HEIGHTS_M:
    UPPER_WIND_COLUMNS.append(f"upper_wind_speed_{_height // 1000}km_kmh")
    UPPER_WIND_COLUMNS.append(f"upper_wind_dir_{_height // 1000}km_deg")


def request_hourly(url, latitude, longitude, launch_time):
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

    response = requests.get(url, params=params, timeout=30)
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


def fetch_weather(latitude, longitude, launch_time):
    try:
        result = request_hourly(BASE_URL, latitude, longitude, launch_time)
        source = "era5_archive"
        if result["wind_speed_10m"] is None:
            raise ValueError("archive has no data yet")
    except (requests.RequestException, ValueError):
        result = request_hourly(RECENT_URL, latitude, longitude, launch_time)
        source = "historical_forecast"
    result["weather_source"] = source
    result["high_altitude_wind_assumed"] = result["wind_speed_10m"]
    return result


def nearest_station(latitude, longitude):
    """Return (station id, distance in km) of the closest IGRA radiosonde station."""

    def distance_km(station_latitude, station_longitude):
        lat1, lon1, lat2, lon2 = map(
            math.radians, (latitude, longitude, station_latitude, station_longitude)
        )
        a = (
            math.sin((lat2 - lat1) / 2) ** 2
            + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
        )
        return 2 * 6371 * math.asin(math.sqrt(a))

    station = min(IGRA_STATIONS, key=lambda s: distance_km(*IGRA_STATIONS[s]))
    return station, distance_km(*IGRA_STATIONS[station])


def read_igra_soundings(station, launch_times):
    """Return {sounding time: array of (height m, wind speed m/s, wind direction deg)}.

    Only soundings within MAX_SOUNDING_GAP of a launch are kept, since the full
    station file is hundreds of MB of text.
    """
    IGRA_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = IGRA_DIR / f"{station}-data.txt.zip"
    if not zip_path.exists():
        response = requests.get(IGRA_URL.format(station=station), timeout=600)
        response.raise_for_status()
        zip_path.write_bytes(response.content)

    ordered_launches = sorted(launch_times)

    def near_a_launch(time):
        i = bisect.bisect_left(ordered_launches, time)
        neighbours = ordered_launches[max(i - 1, 0):i + 1]
        return any(abs(time - t) <= MAX_SOUNDING_GAP for t in neighbours)

    soundings = {}
    with zipfile.ZipFile(zip_path) as archive:
        with archive.open(archive.namelist()[0]) as raw:
            current = None
            for line in io.TextIOWrapper(raw, encoding="ascii", errors="replace"):
                if line.startswith("#"):
                    hour = int(line[24:26])
                    if hour == 99:  # nominal hour missing, use the release hour
                        hour = int(line[27:29])
                    current = None
                    if hour < 24:
                        time = datetime(
                            int(line[13:17]), int(line[18:20]), int(line[21:23]),
                            hour, tzinfo=timezone.utc,
                        )
                        if near_a_launch(time):
                            current = []
                            soundings[time] = current
                elif current is not None:
                    # Fixed width: GPH 17-21, WDIR 41-45, WSPD 47-51 (tenths of m/s)
                    height = int(line[16:21])
                    direction = int(line[40:45])
                    speed = int(line[46:51])
                    if IGRA_MISSING in (height, direction, speed):
                        continue
                    if height < 0 or speed < 0 or direction > 360:
                        continue
                    current.append((height, speed / 10, direction))
    return {
        time: np.array(levels)
        for time, levels in soundings.items()
        if len(levels) > 1
    }


def fetch_upper_winds(launch_time, soundings):
    """Interpolate the best nearby sounding's winds to fixed heights."""
    candidates = [
        (time, levels)
        for time, levels in soundings.items()
        if abs(time - launch_time) <= MAX_SOUNDING_GAP
    ]
    if not candidates:
        return {}

    def rank(candidate):
        time, levels = candidate
        reaches_preferred_top = levels[:, 0].max() >= PREFERRED_TOP_M
        return (not reaches_preferred_top, abs(time - launch_time))

    time, levels = min(candidates, key=rank)

    # Interpolate u/v components so a wind direction near north does not average to south.
    height, unique = np.unique(levels[:, 0], return_index=True)
    speed = levels[unique, 1]
    direction = np.radians(levels[unique, 2])
    u, v = -speed * np.sin(direction), -speed * np.cos(direction)

    result = {
        "upper_wind_sounding_time": time.isoformat(),
        "upper_wind_sounding_offset_h": round(
            (time - launch_time).total_seconds() / 3600, 2
        ),
        "upper_wind_top_km": round(height[-1] / 1000, 2),
    }

    within_range = height <= UPPER_WIND_HEIGHTS_M[-1]
    if within_range.any():
        peak = int(np.argmax(np.where(within_range, speed, -1)))
        result["upper_wind_max_kmh"] = round(speed[peak] * MS_TO_KMH, 1)
        result["upper_wind_max_alt_km"] = round(height[peak] / 1000, 2)

    for target in UPPER_WIND_HEIGHTS_M:
        if target < height[0] or target > height[-1]:
            continue  # the balloon did not report this height
        km = target // 1000
        u_t = np.interp(target, height, u)
        v_t = np.interp(target, height, v)
        result[f"upper_wind_speed_{km}km_kmh"] = round(math.hypot(u_t, v_t) * MS_TO_KMH, 1)
        result[f"upper_wind_dir_{km}km_deg"] = round(
            math.degrees(math.atan2(-u_t, -v_t)) % 360
        )
    return result


def main():
    results = []

    with open(INPUT_FILE, newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)

        for launch in reader:
            try:
                launch_id = launch["launch_id"]
                latitude = float(launch["launchpad_latitude"])
                longitude = float(launch["launchpad_longitude"])

                launch_time = datetime.fromisoformat(
                    launch["launch_timestamp_utc"].replace("Z", "+00:00")
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

    # Upper-air winds: one radiosonde station file per launch site.
    by_station = {}
    for row in results:
        station, distance = nearest_station(row["latitude"], row["longitude"])
        row["upper_wind_station"] = station
        row["upper_wind_station_distance_km"] = round(distance, 1)
        by_station.setdefault(station, []).append(row)

    for station, rows in by_station.items():
        launch_times = [datetime.fromisoformat(r["launch_time"]) for r in rows]
        soundings = read_igra_soundings(station, launch_times)
        print(f"Station {station}: {len(soundings)} soundings near {len(rows)} launches")
        for row, launch_time in zip(rows, launch_times):
            row.update(fetch_upper_winds(launch_time, soundings))

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    columns = [
        "launch_id",
        "launch_time",
        "latitude",
        "longitude",
        "weather_time",
        *WEATHER_VARIABLES,
        "high_altitude_wind_assumed",
        "weather_source",
        *UPPER_WIND_COLUMNS,
    ]

    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(results)

    print(f"Saved {len(results)} records to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
