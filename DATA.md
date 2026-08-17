# Data

This file explains **Corvus's** suggested data sources — where they come from, how to get them, and how to think about using them.

> **`DATA.md` is tracked in git. The `data/` folder is not.** Clone the repo, then populate `data/` locally.

## Suggested sources (starting point)

| Source | Origin / URL | Access method | License | Sensitivity | Notes |
|--------|--------------|---------------|---------|-------------|-------|
| SpaceX API v4 | https://github.com/r-spacex/SpaceX-API | Free public REST API, no key | Apache 2.0 | None | Launches, rockets, launchpads, cores, payloads |
| NASA Open Data Portal | https://data.nasa.gov/ | REST API + bulk download | Public | None | Historical program data (Shuttle, Apollo, ELV launches) |
| Launch Library 2 | https://thespacedevs.com/llapi | REST API, free tier | Attribution | None | Cross-program upcoming + historical launches |
| OpenWeatherMap history | https://openweathermap.org/api/history | REST API, paid for deep history — free tier for recent | Per-tier | None | Weather at launch site + time. Cache aggressively. |
| Wikipedia launch tables | https://en.wikipedia.org/wiki/List_of_Falcon_9_and_Falcon_Heavy_launches | HTML scrape (or Wikidata) | CC-BY-SA | None | Fallback / cross-check for outcome labels |

## How to think about using each source

- **Ground truth.** "Success" definitions differ across sources (partial success, in-flight anomaly resolved, etc.). Pick one canonical definition and document it.
- **Class imbalance.** Modern launch success rates are very high — expect an imbalanced target and pick a metric that survives it (log-loss, PR-AUC, not accuracy).
- **Weather at launch time.** Cross-referencing weather to launch timestamps is where most of the messy join work lives. Cache each lookup to `data/raw/weather/`.
- **License.** SpaceX and NASA data are permissive; Launch Library requires attribution; Wikipedia is CC-BY-SA — if you republish tables, honor the license.

Choosing and vetting a source is a **judgment call** — surface it to a PM rather than deciding a major data direction alone.

## Local layout convention

```
data/
├── raw/          # API dumps as fetched — never edit by hand
├── interim/      # joined launch + weather + outcome tables
└── processed/    # model-ready feature tables and trajectory inputs
```

Because `data/` isn't in git, the **pipeline that fetches and builds these folders** is what must be committed and reproducible — not the data itself.
