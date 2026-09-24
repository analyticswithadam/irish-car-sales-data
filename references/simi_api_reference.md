# SIMI Motorstats API Reference & Extraction Guide

The Society of the Irish Motor Industry (SIMI) publishes official real-time vehicle registration statistics via its public portal at [stats.simi.ie](https://stats.simi.ie/). SIMI receives daily feeds from the National Vehicle and Driver File (NVDF) operated by the Department of Transport and Driver and Vehicle Computer Services Division in Shannon, Co. Clare.

---

## 1. Architecture: Laravel + Inertia.js Protocol

The portal is a Single Page Application (SPA) driven by Laravel and Inertia.js. Rather than serving conventional REST JSON endpoints, SIMI embeds initial state in the HTML document and delivers full datasets as **Inertia Deferred Props**.

```
Browser / Client                 stats.simi.ie
      |                                |
      |--- 1. GET / ------------------>|  (HTML containing <div id="app" data-page="...">)
      |<-- HTML with data-page --------|
      |                                |
      | (Parse version, component,     |
      |  deferredProps keys)           |
      |                                |
      |--- 2. GET / ------------------>|  Headers:
      |    (X-Inertia: true,           |    X-Inertia-Version: <hash>
      |     X-Inertia-Partial-Data)    |    X-Inertia-Partial-Component: Public/Passenger
      |<-- Inertia JSON Response ------|    X-Inertia-Partial-Data: carsByMake,carsByModel,...
      |                                |
```

### 1.1 Step-by-Step Extraction Flow

1. **Initial GET Request**:
   Issue an HTTP GET request to the target category URL:
   * **Passenger Cars**: `https://stats.simi.ie/`
   * **Light Commercials (LCV / Vans)**: `https://stats.simi.ie/lcv`
   * **Heavy Commercials (HCV / Trucks)**: `https://stats.simi.ie/hcv`
   * **Buses & Coaches**: `https://stats.simi.ie/bus`

2. **Parse the `data-page` HTML Attribute**:
   Extract the JSON string from `<div id="app" data-page="...">`:
   ```python
   import re, html, json

   m = re.search(r'data-page=\"([^\"]+)\"', html_content)
   page_data = json.loads(html.unescape(m.group(1)))
   ```

3. **Extract Session Metadata**:
   * `version`: Unique build asset hash (e.g., `"4e6f9828fa69a84a6b..."`).
   * `component`: Inertia view name (`"Public/Passenger"`, `"Public/Lcv"`, etc.).
   * `deferredProps`: Dictionary whose keys represent the available analytical datasets.

4. **Inertia Partial XHR Request**:
   Send a secondary GET request to the same URL, including all deferred keys in `X-Inertia-Partial-Data`:
   ```python
   headers = {
       'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
       'X-Inertia': 'true',
       'X-Inertia-Version': page_data['version'],
       'X-Inertia-Partial-Component': page_data['component'],
       'X-Inertia-Partial-Data': ','.join(page_data['deferredProps'].keys()),
       'Accept': 'text/html, application/xhtml+xml',
       'X-Requested-With': 'XMLHttpRequest'
   }
   ```

5. **Response Payload**:
   The response returns HTTP 200 with `Content-Type: application/json`. Full datasets reside in the `props` dictionary.

> [!IMPORTANT]
> **Inertia Version Mismatches (HTTP 409 Conflict)**
> If the `X-Inertia-Version` header does not match the server's current asset bundle hash, Laravel will return an `HTTP 409 Conflict` with an `X-Inertia-Location` header. When this occurs, discard cached headers and re-fetch the initial HTML to obtain the updated version hash.

---

## 2. Deferred Prop Tables & SQLite Mapping

All 16 datasets retrieved across Passenger, LCV, HCV, and Bus are normalized into SQLite tables in `data/irish_car_sales.db`:

| Category | Inertia Deferred Key | SQLite Table Name | Primary Dimensions | Key Futureproof Fields Ingested |
| :--- | :--- | :--- | :--- | :--- |
| **Passenger** | `carsByMake` | `simi_passenger_makes` | Make (Brand) | `make`, `year_latest`, `units_latest`, `market_share_pct_latest`, `change_pct_latest`, `units_prev` |
| **Passenger** | `carsByModel` | `simi_passenger_models` | Make, Model | `make`, `model`, `rank_latest`, `units_latest`, `market_share_pct_latest`, `change_pct_latest` |
| **Passenger** | `carsByEngineType` | `simi_passenger_fuels` | Engine / Fuel Type | `engine_type`, `year_latest`, `units_latest`, `market_share_pct_latest`, `change_pct_latest` |
| **Passenger** | `carsByCounty` | `simi_passenger_counties` | 26 Republic Counties | `county`, `year_latest`, `units_latest`, `market_share_pct_latest`, `change_pct_latest` |
| **Passenger** | `carsByTransmission` | `simi_passenger_transmissions` | Automatic / Manual | `transmission`, `units_latest`, `market_share_pct_latest`, `change_pct_latest` |
| **Passenger** | `carsByBodyType` | `simi_passenger_body_types` | Body Style | `body_type` (Hatchback, SUV, Saloon, Estate, MPV), `units_latest`, `market_share_pct_latest` |
| **Passenger** | `carsBySegment` | `simi_passenger_segments` | Market Segment | `segment` (Small Hatchback, Small SUV, Medium SUV, Saloon), `units_latest` |
| **Passenger** | `carsByColour` | `simi_passenger_colours` | Exterior Paint Colour | `colour` (Grey, Black, White, Blue, Red), `units_latest`, `market_share_pct_latest` |
| **Passenger** | `totalRegistrationsTable`| `simi_passenger_monthly` | Month (Jan–Dec) | `month`, `month_num`, `units_latest`, `change_pct_latest`, `units_prev` |
| **Passenger** | `totalRegistrationsTable`| `simi_passenger_ytd_totals` | Calendar Year | `year`, `ytd_units`, `change_pct`, `is_latest` |
| **LCV** | `carsByMake` | `simi_lcv_makes` | Commercial Van Make | `make`, `units_latest`, `change_pct_latest`, `market_share_pct_latest` |
| **LCV** | `totalRegistrationsTable`| `simi_lcv_ytd_totals` | Calendar Year | `year`, `ytd_units`, `change_pct`, `is_latest` |
| **HCV** | `carsByMake` | `simi_hcv_makes` | Heavy Truck Make | `make`, `units_latest`, `change_pct_latest`, `market_share_pct_latest` |
| **HCV** | `totalRegistrationsTable`| `simi_hcv_ytd_totals` | Calendar Year | `year`, `ytd_units`, `change_pct`, `is_latest` |
| **Bus** | `carsByMake` | `simi_bus_makes` | Bus & Coach Make | `make`, `units_latest`, `change_pct_latest`, `market_share_pct_latest` |
| **Bus** | `totalRegistrationsTable`| `simi_bus_ytd_totals` | Calendar Year | `year`, `ytd_units`, `change_pct`, `is_latest` |

*(Note: Dynamic annual columns `units_YYYY`, `change_pct_YYYY`, `market_share_pct_YYYY` are also preserved in all tables for historical backwards compatibility).*

---

## 3. JSON Data Schemas & Parsing Rules

### 3.1 Standard Breakdown Schema (`carsByMake`, `carsByCounty`, `carsByEngineType`)
```json
{
  "years": [2026, 2025, 2024],
  "datasets": [
    {
      "label": "TOYOTA",
      "units": [
        {"count": 16913, "change": 5.98},
        {"count": 15958, "change": 3.42},
        {"count": 15430, "change": null}
      ],
      "shares": [13.87, 13.75, 13.75]
    }
  ]
}
```
* Parsing rule: Extract the item for `years[0]` (2026), `years[1]` (2025), and `years[2]` (2024).

### 3.2 Models Breakdown Schema (`carsByModel`)
In `carsByModel`, the item uses a nested dictionary `labels` rather than a scalar string `label`:
```json
{
  "years": [2026, 2025, 2024],
  "datasets": [
    {
      "labels": {
        "make": "TOYOTA",
        "model": "YARIS CROSS"
      },
      "units": [{"count": 3711, "change": 7.63}, ...],
      "shares": [3.04, ...]
    }
  ]
}
```

### 3.3 Monthly Totals Schema (`totalRegistrationsTable`)
```json
{
  "years": [2026, 2025, 2024],
  "labels": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
  "datasets": [
    {
      "label": 2026,
      "data": [
        {"count": 33145, "change": 5.21},
        {"count": 17820, "change": -1.35}
      ]
    }
  ],
  "totals": [
    {"count": 121932, "change": 0.82},
    {"count": 120945, "change": -0.65}
  ]
}
```

---

## 4. Turnkey Script Execution

The standalone script `.agents/skills/irish-car-sales-data/scripts/pull_simi.py` executes the complete Inertia extraction pipeline:

```bash
# Pull all categories (Passenger, LCV, HCV, Bus) into data/simi:
python3 .agents/skills/irish-car-sales-data/scripts/pull_simi.py --output data/simi --category all

# Pull only passenger cars:
python3 .agents/skills/irish-car-sales-data/scripts/pull_simi.py --output data/simi --category passenger
```

---

## 5. Cross-Reference Index
* For historical multi-decade time series and cubes: [cso_table_catalog.md](file:///Users/adamg/Documents/Agents/Data%20Analysis/Mysterio/.agents/skills/irish-car-sales-data/references/cso_table_catalog.md)
* For EV powertrain rules and OEM models: [ev_analysis_guide.md](file:///Users/adamg/Documents/Agents/Data%20Analysis/Mysterio/.agents/skills/irish-car-sales-data/references/ev_analysis_guide.md)
* For database schema and CLI query recipes: [SKILL.md](file:///Users/adamg/Documents/Agents/Data%20Analysis/Mysterio/.agents/skills/irish-car-sales-data/SKILL.md)
