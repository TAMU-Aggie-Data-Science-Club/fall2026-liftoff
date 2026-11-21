"""Weather-go forecast (%) from Launch Library 2 schedule notes (DATA.md §7.10).

LL2's notes carry the 45th Weather Squadron's forecast as free text, for example
"Updated launch weather, 55% GO", "Weather 80%" or "Updating Weather POG to 40%".
A forecast under 50% GO went with delays about 4x as often (38% vs 10% of launches).
It is only posted a day or two before the target. The delay models use it as the
optional input low_weather_go (train_model.py), blank when no forecast is out yet.

Notes come from data/raw/spacex_launch_updates.csv (launch_id, created_on, comment),
written by fetch_spacex.py. That file holds launches that have already flown; live use for
an upcoming launch needs that launch's notes, which nothing fetches yet.
"""

import re

import pandas as pd

# A note counts as a forecast only if it talks about weather.
WEATHER_NOTE = re.compile(r"weather|\bPOG\b|%\s*GO", re.IGNORECASE)
# The first percentage in it, not part of a URL ("Falcon%209") or a word.
PERCENT = re.compile(r"(?<![\w/%])(\d{1,3})\s*%(?![0-9A-Fa-f]{2})")


def parse_weather_go(comment: str) -> float | None:
    """Weather-go percentage in one note, or None if it gives none.

    When a note gives two values ("90% at start of window (75% at end)"), the first is used.
    """
    if not isinstance(comment, str) or not WEATHER_NOTE.search(comment):
        return None
    match = PERCENT.search(comment)
    if not match:
        return None
    value = float(match.group(1))
    return value if value <= 100 else None


def latest_weather_go(
    updates: pd.DataFrame,
    launch_id: str,
    as_of: pd.Timestamp,
    since: pd.Timestamp | None = None,
) -> float | None:
    """The most recent weather-go % posted for a launch at or before `as_of`, or None.

    Pass the time the prediction is made as `as_of` (UTC). Using a later time reads forecasts
    that were posted after a delay was known, which leaks the outcome (DATA.md §7.10).
    `since`, if given, ignores forecasts posted before it: in training it is the baseline
    note's time, since an older forecast was for an earlier target date.
    """
    notes = updates[updates["launch_id"] == launch_id]
    created = pd.to_datetime(notes["created_on"], utc=True)
    keep = created <= pd.Timestamp(as_of)
    if since is not None:
        keep &= created >= pd.Timestamp(since)
    notes = notes[keep].assign(created=created)
    for comment in notes.sort_values("created", ascending=False)["comment"]:
        value = parse_weather_go(comment)
        if value is not None:
            return value
    return None
