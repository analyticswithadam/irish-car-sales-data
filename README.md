# Irish Car Sales & Vehicle Registrations Intelligence Skill

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![SQLite](https://img.shields.io/badge/SQLite-WAL%20Mode-003B57?logo=sqlite)](https://www.sqlite.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

An agentic skill, data pipeline, and analytical SQLite database covering official vehicle registration and car sales statistics for the Republic of Ireland.

Built for AI coding assistants, autonomous agents, data scientists, and automotive analysts.

---

## Highlights

* **Official NVDF Ground Truth**: Ingests data from the **Central Statistics Office (CSO) Ireland** (30+ years of monthly cubes) and the **Society of the Irish Motor Industry (SIMI)** (live monthly registrations).
* **Self-Bootstrapping Engine**: If the local database is missing, calling any script automatically pulls official live APIs and builds the indexed SQLite database in ~1–3 seconds. Databases built by older versions upgrade themselves.
* **Time-Invariant & Futureproof**: Relational schemas use invariant fields (`year_latest`, `units_latest`, `market_share_pct_latest`, `change_pct_latest`, `year_prev`) and dynamic views (`v_county_ev_ranking_latest`) that never break across new calendar years.
* **Comprehensive Powertrain Coverage**: Tracks the 12-year shift from Diesel dominance to Pure Battery Electric (BEV), Plug-In Hybrids (PHEV), and Self-Charging Hybrids (HEV).
* **Zero External DB Dependencies**: Powered by standard library SQLite 3 with Write-Ahead Logging (WAL). The query CLI avoids pandas, so a query returns in about 30 ms.

---

## Repository Structure

```text
.
├── SKILL.md                     # Agent skill instruction manifesto & quickstart
├── README.md                    # Project overview & developer guide
├── .gitignore                   # Ignores local databases & cache files
├── requirements.txt             # Python dependencies (pandas)
├── sql_studio.html              # SQL Studio web page (served by scripts/sql_studio.py)
├── references/                  # In-depth architectural & domain references
│   ├── cso_table_catalog.md     # CSO PxStat REST APIs, schemas & cell-limit rules
│   ├── simi_api_reference.md    # Laravel Inertia deferred props extraction protocol
│   └── ev_analysis_guide.md     # Powertrain taxonomy, OEM model rules & incentives
└── scripts/                     # Standalone Python scripts & utilities
    ├── ensure_data.py           # Auto-verifier & bootstrapper (pulls & builds on demand)
    ├── query_db.py              # CLI SQL query utility (table, CSV, JSON formats)
    ├── build_database.py        # Automated ETL pipeline with indexes & views
    ├── pull_simi.py             # Laravel Inertia crawler for SIMI Motorstats
    ├── pull_cso.py              # Direct streaming client for CSO PxStat cubes
    ├── http_util.py             # Shared HTTPS helper (certificate checks with a guarded fallback)
    ├── analyze_ev_story.py      # Dynamic KPI & metric extraction engine
    ├── build_make_comparison.py # Interactive two-make race chart (e.g. --makes TESLA BYD)
    └── sql_studio.py            # Local SQL Studio server (read-only web SQL workbench)
```

---

## Quickstart

### 1. Install the Dependency
Building the database needs pandas (querying it does not):
```bash
pip install -r requirements.txt
```

### 2. Ensure the Database is Ready (Auto-Build)
```bash
# Verify or auto-pull & build data/irish_car_sales.db
python3 scripts/ensure_data.py

# Force update to the latest figures from live APIs
python3 scripts/ensure_data.py --update
```

### 3. Querying via CLI
```bash
# List all tables and views
python3 scripts/query_db.py --tables

# Annual powertrain market shares (all years dynamically)
python3 scripts/query_db.py "SELECT year, total_cars, electric, electric_share_pct, diesel, diesel_share_pct FROM v_powertrain_annual ORDER BY year DESC"

# Top 5 Commuter Belt EV penetration counties (latest reporting year)
python3 scripts/query_db.py "SELECT licensing_authority, year, ev_units, total_units, ev_penetration_pct FROM v_county_ev_ranking_latest LIMIT 5"

# Top 10 car brands YTD (using invariant units_latest)
python3 scripts/query_db.py "SELECT make, year_latest, units_latest, market_share_pct_latest FROM simi_passenger_makes ORDER BY units_latest DESC LIMIT 10"

# Export query results as JSON
python3 scripts/query_db.py "SELECT transmission, units_latest, market_share_pct_latest FROM simi_passenger_transmissions" --format json
```

### 4. SQL Studio (Web Workbench)
```bash
# Start the local server and open the studio in your browser
python3 scripts/sql_studio.py

# Options: --port 8090, --db-path data/irish_car_sales.db, --no-browser
```
The studio has a table and view explorer, 20 ready-made query recipes, a results grid with CSV/JSON export, and a chart view. It is read-only: write statements are blocked. Open it through the server, not by double-clicking `sql_studio.html`, because queries need the server. It uses the same `data/irish_car_sales.db` as the other scripts, relative to the folder you run it from.

### 5. Programmatic Python Usage
```python
import sqlite3
import pandas as pd
from scripts.ensure_data import ensure_database

# Automatically verifies or builds database if missing
db_path = ensure_database("data/irish_car_sales.db")
conn = sqlite3.connect(db_path)

# Query dynamic latest county adoption
df_county = pd.read_sql_query("SELECT * FROM v_county_ev_ranking_latest", conn)
print(df_county.head())

conn.close()
```

> [!NOTE]
> When importing from the repository root, ensure `scripts/__init__.py` exists so `scripts` is resolved as a Python package.

---

### HTTPS Certificates
The downloaders verify HTTPS certificates. If verification fails (a network proxy that intercepts HTTPS, or a python.org install on macOS that hasn't run `Install Certificates.command`), they retry without verification and print a warning, since both sources are public statistics. Set `IRISH_CAR_SALES_STRICT_SSL=1` to stop instead, or `IRISH_CAR_SALES_INSECURE_SSL=1` to skip verification from the start.

---

## Core Analytical Views

| View Name | Primary Source | Description |
| :--- | :--- | :--- |
| `v_powertrain_annual` | CSO `TEM12` | 2015–Present volumes & shares for BEV, Diesel, Petrol, Hybrids (HEV), and PHEVs. |
| `v_ev_vs_diesel_crossover`| CSO `TEM12` | Monthly time series of Electric vs Diesel units and `ev_to_diesel_ratio`. |
| `v_county_ev_ranking_latest`| CSO `TEM27` | Dynamically resolves the latest year. Returns `licensing_authority`, `year`, `ev_units`, `total_units`, `ev_penetration_pct`, `share_of_national_ev_pct`. |
| `v_model_historical_trajectory`| CSO `TEM20` | Multi-year model-level sales volumes for 330 models across 40 makes. |
| `v_make_annual` | CSO `TEM20` | Annual units and market share per make, with `months_reported` to flag partial years. |
| `v_county_ev_ranking_2026` | CSO `TEM27` | Legacy alias of `v_county_ev_ranking_latest` with `_2026` column names. Kept for older queries; use the `_latest` view instead. |

---

## Installing the Skill

To use this skill with an agentic coding tool:
1. Clone this repository into your project's skills folder. The command below uses `.agents/skills/`; if your tool reads skills from a different folder (Claude Code uses `.claude/skills/`), clone it there instead:
   ```bash
   git clone https://github.com/analyticswithadam/irish-car-sales-data.git .agents/skills/irish-car-sales-data
   ```
2. The agent discovers `SKILL.md` and uses its scripts and database. The first query builds the database automatically.

---

## Data Sources and Terms

* **Central Statistics Office (CSO) Ireland**: Official vehicle licensing data is retrieved via the open CSO PxStat REST API under the Creative Commons Attribution 4.0 International (CC BY 4.0) license.
* **Society of the Irish Motor Industry (SIMI)**: Live motor statistics and brand/model rankings are sourced from the public SIMI Motorstats portal (`stats.simi.ie`). Users should check and review SIMI's terms and conditions before republication or commercial reuse.

---

## License

MIT License. Official statistics copyright Central Statistics Office Ireland & Society of the Irish Motor Industry.
