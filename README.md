# Irish Car Sales & Vehicle Registrations Intelligence Skill

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![SQLite](https://img.shields.io/badge/SQLite-WAL%20Mode-003B57?logo=sqlite)](https://www.sqlite.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

An agentic skill, data pipeline, and analytical SQLite database covering official vehicle registration and car sales statistics for the Republic of Ireland.

Built for AI coding assistants, autonomous agents, data scientists, and automotive analysts.

---

## Highlights

* **Official NVDF Ground Truth**: Ingests data from the **Central Statistics Office (CSO) Ireland** (30+ years of monthly cubes) and the **Society of the Irish Motor Industry (SIMI)** (live monthly registrations).
* **Self-Bootstrapping Engine**: If the local database is missing, calling any script automatically pulls official live APIs and builds the indexed SQLite database in ~10 seconds.
* **Time-Invariant & Futureproof**: Relational schemas use invariant fields (`year_latest`, `units_latest`, `market_share_pct_latest`, `change_pct_latest`, `year_prev`) and dynamic views (`v_county_ev_ranking_latest`) that never break across new calendar years.
* **Comprehensive Powertrain Coverage**: Tracks the 12-year shift from Diesel dominance to Pure Battery Electric (BEV), Plug-In Hybrids (PHEV), and Self-Charging Hybrids (HEV).
* **Zero External DB Dependencies**: Powered by standard library SQLite 3 with Write-Ahead Logging (WAL) and sub-millisecond query execution.

---

## Repository Structure

```text
.
├── SKILL.md                     # Agent skill instruction manifesto & quickstart
├── README.md                    # Project overview & developer guide
├── .gitignore                   # Ignores local databases & cache files
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
    └── analyze_ev_story.py      # Dynamic KPI & metric extraction engine
```

---

## Quickstart

### 1. Ensure the Database is Ready (Auto-Build)
```bash
# Verify or auto-pull & build data/irish_car_sales.db
python3 scripts/ensure_data.py

# Force update to the latest figures from live APIs
python3 scripts/ensure_data.py --update
```

### 2. Querying via CLI
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

### 3. Programmatic Python Usage
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

---

## Core Analytical Views

| View Name | Primary Source | Description |
| :--- | :--- | :--- |
| `v_powertrain_annual` | CSO `TEM12` | 2015–Present volumes & shares for BEV, Diesel, Petrol, Hybrids (HEV), and PHEVs. |
| `v_ev_vs_diesel_crossover`| CSO `TEM12` | Monthly time series of Electric vs Diesel units and `ev_to_diesel_ratio`. |
| `v_county_ev_ranking_latest`| CSO `TEM27` | Dynamically resolves the latest year. Returns `licensing_authority`, `year`, `ev_units`, `total_units`, `ev_penetration_pct`, `share_of_national_ev_pct`. |
| `v_model_historical_trajectory`| CSO `TEM20` | Multi-year model-level sales volumes across 330+ distinct makes and models. |

---

## Installation in Agentic IDEs

To install this skill into an **Antigravity** or agentic coding workspace:
1. Clone this repository into your workspace customizations folder:
   ```bash
   git clone https://github.com/analyticswithadam/irish-car-sales-data.git .agents/skills/irish-car-sales-data
   ```
2. The agent will automatically discover `SKILL.md` and utilize the tools, scripts, and analytical database.

---

## License

MIT License. Official statistics copyright Central Statistics Office Ireland & Society of the Irish Motor Industry.
