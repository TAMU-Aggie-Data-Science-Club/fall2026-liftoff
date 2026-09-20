# Deliverables & Timeline

> **How to read this file.** This is the PMs' best current estimate of what Liftoff needs to ship and roughly when. It is a **living plan, not a contract**. The authoritative picture lives in **GitHub Issues and the Project board**.

## Milestones (suggested)

| # | Deliverable | Description | Owner (role) | Target |
|---|-------------|-------------|--------------|--------|
| 1 | Project scoping | Pick programs to cover (SpaceX + one historical). Define "success" canonically. Define what a "delay" means. | PM | Week 1 |
| 2 | Data ingestion | Reproducible fetchers for SpaceX API + NASA Open Data + weather. Documented in [`DATA.md`](DATA.md). | Members | Weeks 1–2 |
| 3 | EDA | Distribution of outcomes, delays, launch cadence over time, payload mass distributions. | Members | Week 2 |
| 4 | Feature engineering | Rocket family, payload mass, site, weather at launch time, days since previous launch of the same core. | Members | Weeks 3–4 |
| 5 | Outcome + delay models | XGBoost classifier for success; XGBoost regressor for delay hours. Time-based CV. | Members | Weeks 4–5 |
| 6 | Trajectory physics module | 2D ballistic → simple gravity turn, ODE-integrated. Compare against reported apogee/downrange for at least three real launches. | Members | Weeks 5–6 |
| 7 | Streamlit dashboard | Launch explorer, per-launch prediction breakdown, trajectory plot with predicted vs. actual overlays. | Members + PM | Weeks 6–7 |
| 8 | Handoff & retro | Reproducibility check, short writeup, lessons learned. | PM | Week 8 |

## Timeline (rough)

```
Week:   1     2     3     4     5     6     7     8
        |-----|-----|-----|-----|-----|-----|-----|
Scope   ██
Ingest        ████
EDA                 ██
Features                  ████
Models                          ████
Physics                              ████
Dashboard                                  ████
Retro                                              ██
```

## Working agreements

- **Each deliverable maps to one or more GitHub Issues.** The board is the source of truth; this file is the summary.
- **Dates are estimates.** When reality diverges, update the issue and this file if the shift is material.
- **"Done" is defined per issue** via acceptance criteria — not by a date passing.
- **Reprioritize openly.** If a deliverable changes, a PM notes why in the issue so the decision is auditable.
