"""Fetch past SpaceX launches from the Launch Library 2 API and save a local CSV.

Payload mass is not taken from LL2 (it is almost always empty there). It comes
from GCAT, Jonathan McDowell's General Catalog of Artificial Space Objects.
"""

from pathlib import Path

import pandas as pd
import requests

API_URL = "https://ll.thespacedevs.com/2.3.0/launches/previous/"
GCAT_URL = "https://planet4589.org/space/gcat/tsv/launch/launch.tsv"
SPACEX_AGENCY_ID = 121
REPO_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_PATH = REPO_ROOT / "data" / "raw" / "spacex_launches.csv"
GCAT_PATH = REPO_ROOT / "data" / "raw" / "gcat_launch.tsv"

# Max gap between an LL2 `net` and the GCAT launch time for the two to be the same launch
GCAT_MATCH_TOLERANCE = pd.Timedelta(hours=2)
GCAT_TONNES_TO_KG = 1000

# LL2 launch status ids
STATUS_SUCCESS = 3
STATUS_FAILURE = 4
STATUS_PARTIAL_FAILURE = 7


def fetch_launches() -> list[dict]:
    # The free tier allows 15 requests per hour; one full run uses about 8.
    url = API_URL
    params = {"lsp__id": SPACEX_AGENCY_ID, "mode": "detailed", "limit": 100}
    launches = []
    while url:
        response = requests.get(url, params=params, timeout=120)
        if response.status_code == 429:
            raise SystemExit(
                "Launch Library 2 rate limit reached (15 requests/hour). "
                "Wait and run again."
            )
        response.raise_for_status()
        page = response.json()
        launches.extend(page["results"])
        url = page.get("next")
        params = None  # the next URL already carries the query string
    return launches


def load_gcat_launches() -> pd.DataFrame:
    # Cached in data/raw/ like the other raw files; delete it to pull a fresh copy.
    if not GCAT_PATH.exists():
        response = requests.get(GCAT_URL, timeout=120)
        response.raise_for_status()
        GCAT_PATH.parent.mkdir(parents=True, exist_ok=True)
        GCAT_PATH.write_bytes(response.content)
    # Line 1 is the column header (starts with "#"), line 2 is "# Updated ..."
    gcat = pd.read_csv(GCAT_PATH, sep="\t", dtype=str)
    gcat.columns = [col.lstrip("#") for col in gcat.columns]
    gcat = gcat.apply(lambda col: col.str.strip())
    gcat = gcat[~gcat["Launch_Tag"].str.startswith("#")]
    gcat = gcat[gcat["LV_Type"].str.startswith("Falcon", na=False)]
    # "2024 Oct 15 1033" has no seconds and some times end in "?" (uncertain)
    launch_time = (
        gcat["Launch_Date"]
        .str.replace("?", "", regex=False)
        .str.replace(r"\s+", " ", regex=True)
        .str.replace(r"^(\d{4} \w{3} \d+ \d{4})$", r"\1:00", regex=True)
    )
    gcat["launch_time"] = pd.to_datetime(
        launch_time, format="%Y %b %d %H%M:%S", utc=True, errors="coerce"
    )
    # OrbPay is the payload delivered to orbit, in tonnes. "-" means unknown and 0
    # means nothing reached orbit; both become null rather than a real mass.
    orbit_payload = pd.to_numeric(gcat["OrbPay"], errors="coerce")
    gcat["payload_mass_kg"] = orbit_payload.where(orbit_payload > 0) * GCAT_TONNES_TO_KG
    return gcat.dropna(subset=["launch_time"]).sort_values("launch_time")


def add_gcat_payload_mass(launches: pd.DataFrame) -> pd.DataFrame:
    """Replace payload_mass_kg with GCAT's value for the matching launch (NaN if none)."""
    gcat = load_gcat_launches()
    launches = launches.copy()
    launches["_net"] = pd.to_datetime(launches["launch_timestamp_utc"], utc=True)
    order = launches.sort_values("_net")
    matched = pd.merge_asof(
        order[["_net"]],
        gcat[["launch_time", "payload_mass_kg"]],
        left_on="_net",
        right_on="launch_time",
        direction="nearest",
        tolerance=GCAT_MATCH_TOLERANCE,
    )
    launches["payload_mass_kg"] = pd.Series(
        matched["payload_mass_kg"].to_numpy(), index=order.index
    )
    return launches.drop(columns="_net")


def mission_success(launch: dict) -> bool | None:
    status_id = (launch.get("status") or {}).get("id")
    if status_id == STATUS_SUCCESS:
        return True
    if status_id in (STATUS_FAILURE, STATUS_PARTIAL_FAILURE):
        return False
    return None


def build_rows(launches: list[dict]) -> list[dict]:
    rows = []
    for launch in launches:
        rocket_config = (launch.get("rocket") or {}).get("configuration") or {}
        pad = launch.get("pad") or {}
        rows.append(
            {
                "launch_id": launch.get("id"),
                "rocket_type": rocket_config.get("name"),
                "launchpad_latitude": pad.get("latitude"),
                "launchpad_longitude": pad.get("longitude"),
                "launch_timestamp_utc": launch.get("net"),
                "mission_success": mission_success(launch),
            }
        )
    return rows


def main() -> None:
    launches = add_gcat_payload_mass(pd.DataFrame(build_rows(fetch_launches())))
    # Keep the column order the downstream scripts expect
    launches.insert(2, "payload_mass_kg", launches.pop("payload_mass_kg"))
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    launches.to_csv(OUTPUT_PATH, index=False)
    print(f"Wrote {len(launches)} rows to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
