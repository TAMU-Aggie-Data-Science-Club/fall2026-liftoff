#Download the Falcon 9 acent telemetry

""" Source: github.com/shahar603/Telemetry-Data (The Unlicense / public domain),
telemetry captured from SpaceX launch webcasts.
Output: data/reference/telemetry/<mission>/ as the original JSON plus CSV copies."""

import json
from pathlib import Path

import pandas as pd
import requests

BASE_URL = "https://raw.githubusercontent.com/shahar603/Telemetry-Data/master"
OUT_DIR = Path("data/reference/telemetry")

# mission folder name in the source repo -> (short name, files to download)
MISSIONS = {
    "SpaceX CRS-12": ("crs12", ["SpaceX CRS-12 raw.json", "events.json"]),
    "Iridium NEXT 1": ("iridium_next_1", ["Iridium NEXT 1 raw.json", "events.json"]),
    "DM-1": ("dm1", ["DM-1.json", "events.json"]),
}


def download(mission, short_name, filename):
    url = f"{BASE_URL}/{mission}/JSON/{filename}".replace(" ", "%20")
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    data = response.json()

    folder = OUT_DIR / short_name
    folder.mkdir(parents=True, exist_ok=True)
    stem = filename.replace(".json", "").replace(" ", "_").lower()

    (folder / f"{stem}.json").write_text(json.dumps(data, indent=2))
    print(f"saved {folder / stem}.json")

    # Telemetry files look like {"time": [...], "velocity": [...], ...}: also save as CSV
    if isinstance(data, dict) and "time" in data:
        try:
            pd.DataFrame(data).to_csv(folder / f"{stem}.csv", index=False)
            print(f"saved {folder / stem}.csv")
        except ValueError as err:
            print(f"skipped CSV for {stem}: {err}")


if __name__ == "__main__":
    for mission, (short_name, files) in MISSIONS.items():
        for filename in files:
            download(mission, short_name, filename)