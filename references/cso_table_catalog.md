# CSO Ireland Vehicle Statistics Table Catalog & Schema Reference

The Central Statistics Office (CSO) of Ireland publishes monthly official transport and vehicle licensing data via its PxStat open database ([data.cso.ie](https://data.cso.ie)). Data originates from the National Vehicle and Driver File (NVDF) maintained by the Department of Transport.

---

## 1. REST API Endpoints & Access Methods

CSO PxStat supports direct HTTP access without authentication or API keys.

### 1.1 Full CSV Stream (Recommended for Ingestion)
```text
https://ws.cso.ie/public/api.restful/PxStat.Data.Cube_API.ReadDataset/{TABLE_CODE}/CSV/1.0/en
```
* **Format**: Standard CSV (RFC 4180) with headers.
* **Encoding**: UTF-8.
* **Compression**: Server supports `gzip` / `deflate` encoding.
* **HTTP Methods**: `GET` (for standard cubes) or `POST` (for filtered cubes).

### 1.2 JSON-stat 2.0 API (Metadata & Dimensions)
```text
https://ws.cso.ie/public/api.restful/PxStat.Data.Cube_API.ReadDataset/{TABLE_CODE}/JSON-stat/2.0/en
```
Returns complete cube metadata, dimension hierarchies, update timestamps (`updated`), and category labels.

### 1.3 Server-Side Filtered POST Request (Bypassing Cell Limits)
When querying high-dimensional tables (e.g., `TEM24`, `TEM25`), submit a JSON-stat query to avoid the 5-million-cell limit:
```python
import urllib.request
import json

url = "https://ws.cso.ie/public/api.restful/PxStat.Data.Cube_API.ReadDataset/TEM27/JSON-stat/2.0/en"
payload = {
    "query": [
        {"code": "C02172V02618", "selection": {"filter": "item", "values": ["1"]}},  # New Private Cars
        {"code": "TLIST(M1)", "selection": {"filter": "top", "values": ["12"]}}     # Last 12 months
    ],
    "response": {"format": "json-stat"}
}
req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json'})
with urllib.request.urlopen(req) as resp:
    data = json.loads(resp.read().decode('utf-8'))
```

---

## 2. Table Catalog & Database Mapping

All tables are extracted, cleaned, and ingested into the SQLite database at `data/irish_car_sales.db`.

### 1. `TEM01` — Vehicles Licensed for the First Time by Month & Taxation Class
* **Temporal Coverage**: July 1996 to Present (30+ years of continuous monthly observations).
* **Database Table**: `cso_taxation_class_monthly`
* **Purpose**: Macro-economic cycles, fleet composition, and used import tracking.

#### Schema:
| Column | SQLite Type | Nullable | Description / Examples |
| :--- | :--- | :--- | :--- |
| `month_code` | `INTEGER` | No | Numeric month identifier (`202601`, `199607`) |
| `date_val` | `DATE` | No | ISO-8601 month start (`2026-01-01`) |
| `year` | `INTEGER` | No | 4-digit calendar year (`1996`–`2026`) |
| `month_num` | `INTEGER` | No | Month of year (`1` to `12`) |
| `taxation_class` | `TEXT` | No | Vehicle classification (see below) |
| `units` | `INTEGER` | No | Registration volume |

#### Taxation Classes Tracked:
* `Private cars - new`: Brand new passenger cars entering the Irish fleet.
* `Private cars - second hand (imported)`: Used vehicle imports (primarily UK, Northern Ireland, and Japan). Essential for assessing post-Brexit tariff impacts and total fleet churn.
* `Goods vehicles`: Light Commercial Vehicles (vans) and commercial fleet additions.
* `Tractors`: Agricultural machinery registrations.
* `Motorcycles`: Powered two-wheelers.
* `Exempt vehicles`: State vehicles, emergency services, diplomatic vehicles.
* `Small public service vehicles`: Licensed Taxis, Hackneys, and Limousines.
* `Large public service vehicles`: Buses, Coaches, and public transport vehicles.
* `All Vehicles`: Complete aggregate monthly volume.

#### SQL Recipes:
```sql
-- Historical New vs. Used Import Ratio by Year
SELECT year,
       SUM(CASE WHEN taxation_class = 'Private cars - new' THEN units ELSE 0 END) AS new_cars,
       SUM(CASE WHEN taxation_class = 'Private cars - second hand (imported)' THEN units ELSE 0 END) AS imported_used_cars,
       ROUND(CAST(SUM(CASE WHEN taxation_class = 'Private cars - second hand (imported)' THEN units ELSE 0 END) AS FLOAT) * 100.0 /
             NULLIF(SUM(CASE WHEN taxation_class IN ('Private cars - new', 'Private cars - second hand (imported)') THEN units ELSE 0 END), 0), 2) AS import_share_pct
FROM cso_taxation_class_monthly
WHERE year >= 2010
GROUP BY year
ORDER BY year DESC;
```

---

### 2. `TEM12` — New Vehicles by Month, Class & Fuel Type
* **Temporal Coverage**: January 2015 to Present.
* **Database Table**: `cso_fuel_monthly`
* **Purpose**: Primary ground-truth source for tracking the 12-year powertrain revolution (BEV, PHEV, HEV, Diesel, Petrol).

#### Schema:
| Column | SQLite Type | Nullable | Description / Examples |
| :--- | :--- | :--- | :--- |
| `month_code` | `INTEGER` | No | Numeric month identifier (`202601`) |
| `date_val` | `DATE` | No | ISO-8601 month start (`2026-01-01`) |
| `year` | `INTEGER` | No | Calendar year (`2015`–`2026`) |
| `month_num` | `INTEGER` | No | Month (`1`–`12`) |
| `vehicle_class` | `TEXT` | No | `New Private Cars`, `New Goods Vehicles`, `All Vehicles` |
| `fuel_type` | `TEXT` | No | Fuel designation (see below) |
| `units` | `INTEGER` | No | Number of vehicles registered |

#### Fuel Types Tracked:
* `Electric`: Pure Battery Electric Vehicles (BEV) with zero tailpipe emissions.
* `Diesel`: Conventional compression-ignition internal combustion engine.
* `Petrol`: Conventional spark-ignition internal combustion engine.
* `Petrol and electric hybrid`: Self-charging hybrid electric vehicles (HEV).
* `Diesel and electric hybrid`: Self-charging diesel hybrid electric vehicles (HEV).
* `Petrol or Diesel plug-in hybrid electric`: Plug-in hybrid electric vehicles (PHEV).
* `Other fuel types`: CNG, LPG, Hydrogen Fuel Cell, and experimental drivetrains.
* `All fuel types`: Total volume benchmark for calculating percentage market shares.

#### Key Pre-Calculated View: `v_powertrain_annual`
```sql
SELECT year, total_cars, electric, electric_share_pct, diesel, diesel_share_pct, petrol_share_pct, hybrid_share_pct, phev_share_pct
FROM v_powertrain_annual
ORDER BY year DESC;
```

---

### 3. `TEM20` — New Private Cars by Month & Make/Model
* **Temporal Coverage**: January 2014 to Present (>100,000 monthly records across 330+ models).
* **Database Table**: `cso_make_model_monthly`
* **Purpose**: Granular model-level trajectories, OEM market share competition, and specific EV model tracking.

#### Schema:
| Column | SQLite Type | Nullable | Description / Examples |
| :--- | :--- | :--- | :--- |
| `month_code` | `INTEGER` | No | Numeric month identifier (`202601`) |
| `date_val` | `DATE` | No | ISO-8601 month start (`2026-01-01`) |
| `year` | `INTEGER` | No | Calendar year (`2014`–`2026`) |
| `month_num` | `INTEGER` | No | Month (`1`–`12`) |
| `make` | `TEXT` | No | Clean uppercase make (`VOLKSWAGEN`, `TESLA`, `TOYOTA`) |
| `model` | `TEXT` | No | Model designation (`ID.4`, `Model 3`, `Yaris Cross`) |
| `full_name` | `TEXT` | No | Combined title (`Volkswagen ID.4`, `Tesla Model 3`) |
| `units` | `INTEGER` | No | Monthly registrations |

#### SQL Recipes:
```sql
-- Multi-Year Trajectory of Leading Electric Models
SELECT full_name,
       SUM(CASE WHEN year = 2022 THEN units ELSE 0 END) AS units_2022,
       SUM(CASE WHEN year = 2023 THEN units ELSE 0 END) AS units_2023,
       SUM(CASE WHEN year = 2024 THEN units ELSE 0 END) AS units_2024,
       SUM(CASE WHEN year = 2025 THEN units ELSE 0 END) AS units_2025,
       SUM(CASE WHEN year = 2026 THEN units ELSE 0 END) AS units_2026,
       SUM(units) AS total_cumulative
FROM cso_make_model_monthly
WHERE full_name IN ('Volkswagen ID.4', 'Tesla Model Y', 'Tesla Model 3', 'Skoda Enyaq', 'Hyundai Ioniq 5', 'Kia EV6', 'BYD Atto 3', 'BYD Seal')
GROUP BY full_name
ORDER BY total_cumulative DESC;
```

---

### 4. `TEM27` — Private Cars by County, Registration Type & Fuel
* **Temporal Coverage**: January 2021 to Present (~44,000 monthly records).
* **Database Table**: `cso_county_fuel_monthly`
* **Purpose**: Spatial analysis, commuter belt dynamics, urban vs rural adoption disparities.

#### Schema:
| Column | SQLite Type | Nullable | Description / Examples |
| :--- | :--- | :--- | :--- |
| `month_code` | `INTEGER` | No | Numeric month identifier (`202601`) |
| `date_val` | `DATE` | No | ISO-8601 month start (`2026-01-01`) |
| `year` | `INTEGER` | No | Calendar year (`2021`–`2026`) |
| `month_num` | `INTEGER` | No | Month (`1`–`12`) |
| `reg_type` | `TEXT` | No | `New Private Cars`, `Secondhand Private Cars`, `All Private Cars` |
| `licensing_authority`| `TEXT` | No | Local authority (27 authorities, plus national aggregate) |
| `fuel_type` | `TEXT` | No | Powertrain classification |
| `units` | `INTEGER` | No | Registrations |

#### Authorities Tracked (27 Local Authorities):
* Dublin Authorities (4): `Dublin City`, `Dún Laoghaire-Rathdown`, `Fingal`, `South Dublin`.
* Commuter Belt Authorities: `Kildare`, `Meath`, `Wicklow`, `Louth`.
* Provincial City & County Authorities: `Cork County`, `Cork City`, `Galway County`, `Galway City`, `Limerick City and County`, `Waterford City and County`.
* Rural Counties: `Carlow`, `Cavan`, `Clare`, `Donegal`, `Kerry`, `Kilkenny`, `Laois`, `Leitrim`, `Longford`, `Mayo`, `Monaghan`, `Offaly`, `Roscommon`, `Sligo`, `Tipperary`, `Westmeath`, `Wexford`.

#### Key Pre-Calculated View: `v_county_ev_ranking_latest`
```sql
-- Dynamically resolves latest reporting year without hardcoded timestamps
SELECT licensing_authority, year, ev_units, total_units, ev_penetration_pct, share_of_national_ev_pct
FROM v_county_ev_ranking_latest
LIMIT 10;
```

---

## 3. High-Dimensional Cell Limit Guardrails

> [!WARNING]
> **Avoid Unbounded Requests to `TEM24` and `TEM25`**
> - `TEM24` (*New Private Cars by Engine cc, Emission Band, County, and Make*) and `TEM25` (*Secondhand Private Cars by Engine cc, Emission Band, County, and Make*) span 5 simultaneous dimensions.
> - A full CSV query contains over **5.2 million matrix cells**, causing the CSO PxStat API gateway to terminate the connection with **`HTTP 403 Forbidden`** or `413 Payload Too Large`.
> - **Best Practices**:
>   - For vehicle make and model time series, use **`TEM20`** (fast, complete, unconstrained).
>   - For county-level fuel adoption, use **`TEM27`**.
>   - For engine cc or CO2 emission bands, pull from **SIMI Motorstats** (`carsByCo2Band`).

---

## 4. Cross-Reference Index
* For live monthly data and transmission/body styles: [simi_api_reference.md](file:///Users/adamg/Documents/Agents/Data%20Analysis/Mysterio/.agents/skills/irish-car-sales-data/references/simi_api_reference.md)
* For EV taxonomy, OEM model rules, and incentives: [ev_analysis_guide.md](file:///Users/adamg/Documents/Agents/Data%20Analysis/Mysterio/.agents/skills/irish-car-sales-data/references/ev_analysis_guide.md)
* For main skill workflows and database architecture: [SKILL.md](file:///Users/adamg/Documents/Agents/Data%20Analysis/Mysterio/.agents/skills/irish-car-sales-data/SKILL.md)
