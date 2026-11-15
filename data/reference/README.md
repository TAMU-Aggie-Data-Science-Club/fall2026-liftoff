# Reference benchmark data

Target flight profiles for testing the trajectory simulator.

| Mission | Date | Orbit | NORAD ID | Telemetry | TLE |
|---|---|---|---|---|---|
| SpaceX CRS-12 | 2017-08-14 | ISS LEO | 42904 | telemetry/crs12/ | tle/crs12.tle (local only) |
| Iridium NEXT 1 | 2017-01-14 | ~625 km polar LEO | 41917 | telemetry/iridium_next_1/ | tle/iridium_next_1.tle (local only) |
| Crew Dragon Demo-1 | 2019-03-02 | ISS LEO | 44063 | telemetry/dm1/ | tle/dm1.tle (local only) |

## Telemetry files

- `*_raw.csv` / `dm-1.csv`: columns `time` [s], `velocity` [m/s], `altitude` [km].
  **Altitude is in km**, so convert to m before comparing with the simulator.
- `*.json`: the same data in the original source format.
- `events.json`: times [s] of flight events (max-Q, MECO, etc.). `null` = not available.
- Source: github.com/shahar603/Telemetry-Data (The Unlicense), read from SpaceX
  webcasts. Velocity is Earth-relative; the simulator ignores Earth's rotation.
- Regenerate with: `python src/physics/fetch_reference.py`

## TLE files

- First TLE recorded after each launch, from space-track.org (free account).
- Not committed: the Space-Track user agreement restricts redistribution.
- Download (while logged in), replacing `<ID>` with the NORAD ID above:
  `https://www.space-track.org/basicspacedata/query/class/gp_history/NORAD_CAT_ID/<ID>/orderby/EPOCH%20asc/limit/1/format/3le`
- TLEs describe the orbit reached, not the ascent path.
