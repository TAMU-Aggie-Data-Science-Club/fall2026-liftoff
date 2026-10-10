# Liftoff - Deliverables & Timeline

> **How to read this file.** This is the PMs' best current estimate of what Liftoff needs to ship and roughly when. It is a **living plan, not a contract**. The authoritative picture lives in **GitHub Issues and the Project board**.

## Project goal

Liftoff builds a mission-control-style dashboard that predicts rocket launch success and delays from historical launch data, weather, rocket type, and site information. It also visualizes rocket trajectories using physics-based equations, comparing expected flight paths against real launch behavior.

A prediction model for launch outcome (success / delay) given pre-launch features.

A trajectory visualizer grounded in real physics (ballistic → simple gravity turn), so predictions and paths sit side-by-side in one dashboard.

## Subteams and responsibilities

We will have three subteams of 2-3 members. Members can express preferences, suggest approaches, and discuss changing roles with the PMs.

| Subteam | Semester responsibilities |
| --- | --- |
| Data Engineering & ML | Ingestion pipelines for SpaceX and NASA APIs, feature engineering, XGBoost training for classification and delay regression, cross-validation, and error analysis. |
| Physics & Trajectory Modeling | Differential equations setup using scipy.integrate.solve_ivp, 2D ballistic and gravity-turn flight simulation, trajectory coordinate exports, and numerical sanity checks against telemetry |
| Dashboard & Integration | Streamlit application layout, Plotly visual components, mission-control styling, user parameter controls, and end-to-end integration of ML model predictions with physics plots. |

Each subteam will divide work into individual or paired tasks and choose a working coordinator to communicate progress and blockers.

Coordinators also contribute to the work. They are not expected to complete the entire team's assignment.

### PM responsibilities

Amulya and a second PM will:
- Assign and clarify deliverables.
- Coordinate dependencies between subteams.
- Help members resolve blockers.
- Review integration pull requests before merging into main.
- Track attendance and individual contributions.
- Maintain the project plan and submit weekly PM reports.

## Meetings and communication

Regular project syncs are TBD after the first team meeting (Tuesday, October 13th at 5:15)

They will take place virtually in the Project Sync voice channel on the Liftoff Discord

## Initial datasets

We will begin with:

r/SpaceX REST API - provides structured data on modern commercial spaceflight, allowing us to train models to predict launch success and delay hours

NASA Space Shuttle Mission Data (NASA Open Data) - expands the dataset to predict launches outside of SpaceX flights, allows the user to benchmark modern flights against historical data

Open-Meteo Historical Weather API - forms the key feature pipeline for the XGBoost ML models, allowing the risk readout to update dynamically when a user adjusts weather variables

LLNL / CelesTrak Satellite Catalog (Space-Track TLEs) - provides actual positional coordinates recorded from real flights, acts as the baseline benchmark for the trajectory visualizer

## Week 1 — Quick assignment

**Due Sunday, October 11, 2026, at noon Central.**

Read through the responsibilities of each subteam and DM a.bisaria on Discord with your resume and a brief paragraph explaining why you would be fit for the role and why you are interested in it. This will allow us to finalize subteams and begin working on the project on Tuesday when we have the first meeting.

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
