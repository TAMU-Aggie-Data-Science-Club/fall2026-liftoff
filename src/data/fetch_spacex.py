"""Fetch past SpaceX launches from the Launch Library 2 API and save a local CSV."""

from pathlib import Path

import pandas as pd
import requests

API_URL = "https://ll.thespacedevs.com/2.3.0/launches/previous/"
SPACEX_AGENCY_ID = 121
REPO_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_PATH = REPO_ROOT / "data" / "raw" / "spacex_launches.csv"

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


def payload_mass_kg(launch: dict) -> float | None:
    payload_flights = (launch.get("rocket") or {}).get("payloads") or []
    if not payload_flights:
        return None
    total = 0.0
    for flight in payload_flights:
        mass = (flight.get("payload") or {}).get("mass")
        if mass is None:
            return None
        total += mass * (flight.get("amount") or 1)
    return total


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
                "payload_mass_kg": payload_mass_kg(launch),
                "launchpad_latitude": pad.get("latitude"),
                "launchpad_longitude": pad.get("longitude"),
                "launch_timestamp_utc": launch.get("net"),
                "mission_success": mission_success(launch),
            }
        )
    return rows


def main() -> None:
    rows = build_rows(fetch_launches())
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(OUTPUT_PATH, index=False)
    print(f"Wrote {len(rows)} rows to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
