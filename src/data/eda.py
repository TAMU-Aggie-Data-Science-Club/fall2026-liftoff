"""EDA on launch delays: which features relate to a delay, and which add nothing.

Reads the feature table (data/processed/ml_features.csv) and the delay labels from
src/models/train_model.py, so the labels match the model exactly. Prints:

1. Delay rate by rocket, pad, year and target month.
2. Each candidate numeric feature, delayed vs on time (medians, correlation, single-feature AUC).
3. Features that add no information: empty, constant, duplicate, near-duplicate pairs,
   and columns that only identify the launch pad.

Candidate features built here (EDA only, not model inputs yet):
- Schedule features, known at the baseline (the note posted >= 7 days before launch):
  target hour (UTC) and month, days from the previous SpaceX launch to the target,
  the same for the same pad, and how many times the target had moved before the baseline.
- Weather at the baseline target time ("target_*"), fetched from the same Open-Meteo
  archive as fetch_weather.py and cached in data/interim/eda_target_weather.csv
  (delete that file to re-fetch). This is observed weather, not a forecast.

Nothing is written except that cache.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src" / "models"))
sys.path.insert(0, str(REPO_ROOT / "src" / "data"))

from train_model import baseline_notes, load_launches, schedule_notes  # noqa: E402

TARGET_WEATHER_CACHE = REPO_ROOT / "data" / "interim" / "eda_target_weather.csv"
TARGET = "is_delayed"
WEATHER = ["temperature_2m", "wind_speed_10m", "precipitation", "cloud_cover"]
# launch_time, latitude and longitude repeat launch_timestamp_utc and the launchpad_* columns.
DUPLICATE_COLUMNS = ["launch_time", "latitude", "longitude"]
NEAR_DUPLICATE_R = 0.9
# A column whose spread within a pad is under this share of its overall spread only identifies the pad.
PAD_PROXY_RATIO = 0.1


def pad_key(df: pd.DataFrame) -> pd.Series:
    return df["launchpad_latitude"].round(3).astype(str) + ", " + df["launchpad_longitude"].round(3).astype(str)


def add_schedule_features(launches: pd.DataFrame, labelled: pd.DataFrame) -> pd.DataFrame:
    """Features known at the baseline note, for each labelled launch."""
    base = baseline_notes(launches)
    df = labelled.join(base.rename(columns={"target": "baseline_target", "created_on": "baseline_posted"}),
                       on="launch_id")
    # A note with a day but no time is stored as midnight after that day; use noon of the day instead.
    no_time = df["baseline_target"].dt.strftime("%H:%M:%S") == "00:00:00"
    df["target_time"] = df["baseline_target"].where(~no_time, df["baseline_target"] - pd.Timedelta(hours=12))
    df["target_hour_utc"] = df["target_time"].dt.hour.where(~no_time)
    df["target_month"] = df["target_time"].dt.month

    # Days from the most recent launch before the baseline was posted to the target time.
    all_launches = launches.assign(pad=pad_key(launches)).sort_values("launch_timestamp_utc")
    all_launches["utc"] = all_launches["launch_timestamp_utc"].dt.tz_convert(None)
    times = all_launches["utc"].to_numpy()
    df["pad"] = pad_key(df)

    def days_since(row, pool_times):
        i = np.searchsorted(pool_times, row["baseline_posted"].to_datetime64()) - 1
        return np.nan if i < 0 else (row["target_time"].to_datetime64() - pool_times[i]) / np.timedelta64(1, "D")

    df["days_since_prev_spacex"] = df.apply(lambda r: days_since(r, times), axis=1)
    pad_times = {p: g["utc"].to_numpy() for p, g in all_launches.groupby("pad")}
    df["days_since_prev_pad"] = df.apply(lambda r: days_since(r, pad_times[r["pad"]]), axis=1)

    # How many times the announced target changed before the baseline was posted.
    notes = schedule_notes()
    notes = notes[notes["launch_id"].isin(df["launch_id"])]
    notes = notes.join(df.set_index("launch_id")["baseline_posted"], on="launch_id")
    notes = notes[notes["created_on"] <= notes["baseline_posted"]]
    changed = notes.groupby("launch_id")["target"].transform(lambda t: t.ne(t.shift()))
    df["target_moves_before_baseline"] = (
        df["launch_id"].map(changed.groupby(notes["launch_id"]).sum() - 1).fillna(0)
    )
    return df


def add_target_weather(df: pd.DataFrame) -> pd.DataFrame:
    """Weather at the pad at the baseline target time, cached so the EDA only fetches once."""
    from fetch_weather import fetch_weather  # imported here: only needed for missing rows

    cache = pd.read_csv(TARGET_WEATHER_CACHE) if TARGET_WEATHER_CACHE.exists() else pd.DataFrame(
        columns=["launch_id", "target_time"])
    key = df["launch_id"] + "|" + df["target_time"].astype(str)
    have = set(cache["launch_id"] + "|" + cache["target_time"].astype(str))
    todo = df[~key.isin(have)]
    if len(todo):
        print(f"Fetching weather at the target time for {len(todo)} launches (cached afterwards)...")
        rows = []
        for _, r in todo.iterrows():
            try:
                w = fetch_weather(r["launchpad_latitude"], r["launchpad_longitude"], r["target_time"].to_pydatetime())
            except Exception as error:  # keep going; a gap is reported as missing
                print(f"  failed for {r['launch_id']}: {error}")
                continue
            rows.append({"launch_id": r["launch_id"], "target_time": str(r["target_time"]),
                         **{f"target_{v}": w.get(v) for v in WEATHER}})
        cache = pd.concat([cache, pd.DataFrame(rows)], ignore_index=True)
        TARGET_WEATHER_CACHE.parent.mkdir(parents=True, exist_ok=True)
        cache.to_csv(TARGET_WEATHER_CACHE, index=False)
    cache["target_time"] = cache["target_time"].astype(str)
    df = df.assign(_key=key)
    cache = cache.assign(_key=cache["launch_id"] + "|" + cache["target_time"])
    cols = [f"target_{v}" for v in WEATHER]
    return df.merge(cache[["_key", *cols]].drop_duplicates("_key"), on="_key", how="left").drop(columns="_key")


def rate_table(df: pd.DataFrame, by) -> pd.DataFrame:
    out = df.groupby(by)[TARGET].agg(launches="size", delayed="sum", delay_rate="mean")
    out["delayed"] = out["delayed"].astype(int)
    out["delay_rate"] = out["delay_rate"].round(2)
    return out


def feature_table(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Per feature: n, delays, medians on time vs delayed, Pearson r with the label, single-feature AUC.

    AUC = chance a random delayed launch has a higher value than a random on-time one;
    0.5 is no signal, and |AUC - 0.5| is shown as 'signal' whichever way it points.
    """
    y = df[TARGET].astype(int)
    rows = []
    for c in columns:
        x = pd.to_numeric(df[c], errors="coerce")
        ok = x.notna()
        two = y[ok].nunique() == 2 and x[ok].nunique() > 1
        auc = roc_auc_score(y[ok], x[ok]) if two else np.nan
        rows.append({
            "feature": c, "n": int(ok.sum()), "delays": int(y[ok].sum()),
            "median_on_time": x[ok & (y == 0)].median(), "median_delayed": x[ok & (y == 1)].median(),
            "pearson_r": x[ok].corr(y[ok]) if two else np.nan,
            "auc": auc, "signal": abs(auc - 0.5) if two else np.nan,
        })
    return pd.DataFrame(rows).set_index("feature").sort_values("signal", ascending=False).round(3)


def redundancy(df: pd.DataFrame, numeric: list[str]) -> None:
    empty = [c for c in numeric if df[c].notna().sum() == 0]
    constant = [c for c in numeric if df[c].notna().sum() > 0 and df[c].nunique() <= 1]
    print(f"Empty columns: {empty or 'none'}")
    print(f"Constant columns: {constant or 'none'}")
    dupes = [c for c in DUPLICATE_COLUMNS if c in df]
    print(f"Duplicate columns (copies of launch time / pad coordinates): {dupes or 'none'}")

    usable = [c for c in numeric if c not in empty + constant]
    corr = df[usable].apply(pd.to_numeric, errors="coerce").corr()
    pairs = [(a, b, corr.loc[a, b]) for i, a in enumerate(usable) for b in usable[i + 1:]
             if abs(corr.loc[a, b]) >= NEAR_DUPLICATE_R]
    print(f"\nNear-duplicate pairs (|r| >= {NEAR_DUPLICATE_R}):")
    for a, b, r in sorted(pairs, key=lambda p: -abs(p[2])):
        print(f"  {a} ~ {b}: r = {r:.3f}")
    if not pairs:
        print("  none")

    pads = pad_key(df)
    proxies = []
    for c in usable:
        x = pd.to_numeric(df[c], errors="coerce")
        overall = x.std()
        within = x.groupby(pads).std().mean()
        if overall and overall > 0 and within / overall < PAD_PROXY_RATIO:
            proxies.append(f"{c} (within-pad spread {within / overall:.0%} of overall)")
    print(f"\nPad proxies (value is set by the pad, so it adds nothing beyond the pad): {proxies or 'none'}")


def main() -> None:
    launches = load_launches()
    labelled = launches.dropna(subset=[TARGET]).copy()
    labelled[TARGET] = labelled[TARGET].astype(int)
    print(f"== {len(launches)} launches, {len(labelled)} with a delay label "
          f"({labelled[TARGET].sum()} delayed, {labelled[TARGET].mean():.0%}) ==\n")

    df = add_schedule_features(launches, labelled)
    df = add_target_weather(df)
    df["pad"] = pad_key(df)
    df["year"] = df["launch_timestamp_utc"].dt.year

    print("\n== Delay rate by rocket ==")
    print(rate_table(df, "rocket_type").sort_values("launches", ascending=False).to_string())
    print("\n== Delay rate by pad (lat, lon) ==")
    print(rate_table(df, "pad").sort_values("launches", ascending=False).to_string())
    print("\n== Delay rate by year ==")
    print(rate_table(df, "year").to_string())
    print("\n== Delay rate by target month ==")
    print(rate_table(df, "target_month").to_string())

    launch_time_weather = WEATHER + ["upper_wind_max_kmh", "upper_wind_max_alt_km",
                                     "upper_wind_speed_10km_kmh", "upper_wind_speed_12km_kmh"]
    candidates = {
        "Current model inputs and launch-time weather (only known at liftoff)":
            launch_time_weather + ["payload_mass_kg"],
        "Schedule features (known at the baseline)":
            ["target_hour_utc", "target_month", "days_since_prev_spacex", "days_since_prev_pad",
             "target_moves_before_baseline"],
        "Weather at the baseline target time":
            [f"target_{v}" for v in WEATHER],
    }
    for title, cols in candidates.items():
        print(f"\n== {title}: delayed vs on time ==")
        print(feature_table(df, [c for c in cols if c in df]).to_string())

    print("\n== Features that add no information ==")
    numeric = [c for c in df.select_dtypes("number").columns if c not in (TARGET, "mission_success", "year")]
    redundancy(df, numeric)


if __name__ == "__main__":
    main()
