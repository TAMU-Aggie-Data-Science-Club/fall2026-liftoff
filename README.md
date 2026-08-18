# Liftoff â€” Beginner

*ADSC Catalyst Project Â· Fall 2026*

## Overview

Liftoff builds a mission-control-style dashboard that predicts rocket launch success and delays from historical launch data, weather, rocket type, and site information. It also visualizes rocket trajectories using physics-based equations, comparing expected flight paths against real launch behavior.

## Objective

Ship two things that work together:

1. A **prediction model** for launch outcome (success / delay) given pre-launch features.
2. A **trajectory visualizer** grounded in real physics (ballistic â†’ simple gravity turn), so predictions and paths sit side-by-side in one dashboard.

## Suggested tech stack

- **Data processing:** Python, Pandas, NumPy
- **Modeling / ML:** XGBoost (classification for success, regression for delay hours)
- **Physics:** NumPy-based ODE integration for trajectory (`scipy.integrate.solve_ivp`)
- **Visualization:** Plotly, Matplotlib, Streamlit
- **Data sources:** SpaceX API, NASA Open Data, public launch data

See [`DATA.md`](DATA.md) for concrete data sources and how to access them.

## What team members will gain

- A dashboard that replicates the feel of real mission-control analysis
- Predictive modeling for launch success and delays on real data
- The rare and marketable skill of combining physics with data science

## Suggested scope (v1)

Cover **two programs**: SpaceX (rich API, modern) plus one historical NASA program (e.g., Space Shuttle) from NASA Open Data.

Build:

1. Ingestion for launches, rockets, and sites,
2. Feature engineering (rocket family, payload mass, launch site, weather at launch time),
3. XGBoost model for success + a second model for delay hours,
4. Physics module: 2D ballistic + simple gravity-turn model, ODE-integrated, plotted against actual trajectory where telemetry is available,
5. Streamlit dashboard tying model + trajectory + historical explorer.

**Out of scope for v1:** real-time telemetry ingest, atmospheric drag beyond first-order, orbit-insertion accuracy, orbital mechanics after burnout.

See [`DELIVERABLES.md`](DELIVERABLES.md) for the suggested deliverable breakdown and rough timeline.

## Repository map

| File / folder | Purpose |
|---|---|
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | **Start here.** How the team runs the project on GitHub â€” PM vs. member roles, the issue â†’ PR â†’ `main` flow, branching, worktrees, reviews. |
| [`DELIVERABLES.md`](DELIVERABLES.md) | Suggested deliverables and rough timeline. A living plan, not a contract. |
| [`DATA.md`](DATA.md) | Suggested data sources, how to access them, and the source register. |
| [`data/`](data/) | Local working folder for datasets. **Git-ignored** â€” data is never committed. |
| [`AGENTS.md`](AGENTS.md) | Machine-facing workflow rules for AI coding agents. |
| [`CODEOWNERS`](CODEOWNERS) | **Team roster + review policy.** PMs, members, and the code-owner rule for PRs into `main`. |


## Team

The current PMs and members for this project are listed in [`CODEOWNERS`](CODEOWNERS). PMs listed there are the code owners for PRs into `main`.
## Notes for PMs

This README, [`DELIVERABLES.md`](DELIVERABLES.md), and [`DATA.md`](DATA.md) are **suggestions**, not commitments. Rewrite them as the team scopes the real project.

## Notes for members

Read [`CONTRIBUTING.md`](CONTRIBUTING.md) before touching code. Then pick up an issue from the board.
