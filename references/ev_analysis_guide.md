# Electric Vehicle (EV) Analysis & Intelligence Guide

This guide details methodologies, data classification rules, policy frameworks, and SQL analytical patterns for analyzing the electric vehicle market, battery electrification trends, and powertrain transitions in Ireland.

> [!CRITICAL]
> **Query Rule**: Never state a market figure from this file. Always query the database for current values and cite the table or view used.

---

## 1. Powertrain Taxonomy & Market Definitions

In Irish automotive statistics, vehicles are categorized across five primary powertrain groups:

| Powertrain Category | SIMI Fuel Code | CSO Fuel Code (`TEM12`, `TEM27`) | Analytical Definition & Inclusions |
| :--- | :--- | :--- | :--- |
| **Pure BEV** | `Electric` | `Electric` | Pure Battery Electric Vehicle (100% electric, zero tailpipe emissions). |
| **PHEV** | `Petrol/Plug-In Electric Hybrid`, `Diesel/Plug-In Electric Hybrid` | `Petrol or Diesel plug-in hybrid electric` | Plug-in Hybrid Electric Vehicle with external charging socket and internal combustion engine backup. |
| **HEV (Self-Charging)** | `Petrol Electric (Hybrid)`, `Diesel Electric (Hybrid)` | `Petrol and electric hybrid`, `Diesel and electric hybrid` | Self-charging mild/full hybrid without external plug-in socket (kinetic brake regeneration). |
| **ICE (Petrol)** | `Petrol` | `Petrol` | Pure internal combustion engine running on unleaded petrol. |
| **ICE (Diesel)** | `Diesel` | `Diesel` | Pure internal combustion compression-ignition diesel engine. |

### Analytical Aggregation Rules:
* **"Pure EV" (or "BEV")**: Refers exclusively to **BEV** (`Electric`).
* **"Total Plug-in"**: Combined BEV + PHEV (all vehicles equipped with an external charging port).
* **"Total Electrified"**: Combined BEV + PHEV + HEV (all vehicles featuring an electric traction motor).
* **The "EV vs. Diesel Crossover"**: The inflection point where pure BEV registrations surpass Diesel registrations.

---

## 2. Model-Level Pure BEV Identification Rules

Neither SIMI nor CSO tables include an explicit powertrain column in model-level rankings. Apply these definitive rules when isolating pure BEVs:

### 2.1 100% Pure BEV Brands
Every registration from these manufacturers is guaranteed 100% pure BEV:
* `TESLA` (Model 3, Model Y, Model S, Model X)
* `POLESTAR` (Polestar 2, 3, 4)
* `XPENG` (G6, G9)
* `SMART` (#1, #3)
* `LUCID`, `NIO`, `FISKER`, `RIVIAN`

### 2.2 Dedicated Ground-Up BEV Models (By OEM)
* **Volkswagen Group**:
  * **Volkswagen**: `ID.3`, `ID.4`, `ID.5`, `ID.7`, `ID BUZZ PC`
  * **Škoda**: `ENYAQ`, `ELROQ`
  * **CUPRA**: `BORN`, `TAVASCAN`
  * **Audi**: `Q4 E-TRON`, `Q6 E-TRON`, `Q8 E-TRON`, `E-TRON GT`
  * **Porsche**: `TAYCAN`, `MACAN ELECTRIC`
* **Hyundai Motor Group**:
  * **Kia**: `EV2`, `EV3`, `EV4`, `EV5`, `EV6`, `EV9`
  * **Hyundai**: `IONIQ`, `IONIQ 5`, `IONIQ 6`, `IONIQ 9`, `INSTER` (Sub-€25k entry EV)
* **BYD (Build Your Dreams)**:
  * Pure BEVs: `ATTO 3`, `DOLPHIN`, `DOLPHIN SURF`, `SEAL`, `SEALION 7`, `SEALION 5`
  * *Important Note on `SEAL U`*: The `SEAL U` is sold in Ireland as both a pure BEV and a `DM-i` Super Hybrid (PHEV).
* **BMW Group**:
  * Dedicated BEV: `I3`, `IX`
  * Electric variants of shared architectures: `I4`, `I5`, `I7`, `IX1`, `IX2`, `IX3`, MINI `COOPER SE`, `ACEMAN`
* **Mercedes-Benz**:
  * `EQA`, `EQB`, `EQC`, `EQE`, `EQS`, `EQE SUV`, `EQS SUV`
* **Stellantis**:
  * `PEUGEOT E-208`, `PEUGEOT E-2008`, `PEUGEOT E-3008`, `FIAT 500E`, `JEEP AVENGER EV`, `OPEL CORSA-E`, `OPEL MOKKA-E`
* **Other Major Nameplates**:
  * **Volvo**: `EX30`, `EX40`, `EC40`, `EX90`
  * **Renault**: `ZOE`, `MEGANE E-TECH`, `SCENIC E-TECH`, `5 E-TECH`
  * **Nissan**: `LEAF`, `ARIYA`
  * **Ford**: `EXPLORER`, `CAPRI`, `MUSTANG MACH-E`
  * **MG**: `MG4`, `CYBERSTER`, `ZS EV`, `MG5`

---

## 3. Spatial Dynamics & Geographic Patterns

When evaluating geographic EV adoption using CSO `TEM27` and dynamic view `v_county_ev_ranking_latest`:
* **Raw Volume vs. Market Penetration**:
  * Absolute registrations reflect population size (e.g. Dublin accounting for the largest total vehicle count).
  * Adoption rate (`ev_penetration_pct`) measures the proportion of new vehicle registrations that are pure BEV within each licensing authority.
  * Always query `v_county_ev_ranking_latest` to retrieve current penetration rankings across all 26 licensing authorities.

### Hypotheses to Test
When analyzing EV adoption and geographic trends, investigate these questions against the data rather than assuming fixed conclusions:
* **Commuter Belt vs. Urban Core**: Do commuter counties surrounding Dublin (such as Wicklow, Kildare, and Meath) exhibit higher EV penetration rates than Dublin City? Does housing stock (off-street driveway availability enabling home wallbox installation vs high-density apartments and terraced housing) correlate with penetration differences?
* **Mileage and Operating Cost Arbitrage**: Do long-distance daily commuters on major motorway corridors (e.g. M7, M4, M11) have stronger economic incentives to transition to electric vehicles due to operating cost savings compared to internal combustion engines?
* **Incentive Utilization**: How do corporate and fleet schemes under Benefit-in-Kind (BIK) tax relief influence EV registration concentrations in commuter employment hubs?
* **Rural and Regional Adoption**: Do rural, western, or border counties exhibit lower EV penetration rates, and can this be attributed to charging infrastructure density, trip lengths, or vehicle utility requirements (e.g. agricultural/commercial towing)?

---

## 4. Irish EV Policy & Incentive Evolution

The Irish EV market trajectory has been heavily dictated by governmental fiscal and tax incentives:

| Incentive Instrument | Peak Era (2019–2023) | Current Status (2024–2026) | Market Consequence |
| :--- | :--- | :--- | :--- |
| **SEAI Purchase Grant** | €5,000 direct purchase grant on private BEVs | Reduced to €3,500 for vehicles priced €14,000–€60,000 | Grant cuts coincided with a sales contraction in 2024 ("subsidy hangover"). Query the database to measure the exact YoY impact. |
| **VRT Relief** | Up to €5,000 vehicle registration tax relief | Tapered relief up to €40,000 OMSP; steps to €0 at €50,000 | Created a severe "cliff edge" where EVs over €50,000 incur full VRT rates, forcing OEMs to reprice premium models below €50k. |
| **Benefit-in-Kind (BIK)** | 0% BIK exemption on company cars up to €50,000 | €35,000 relief band with phased annual tapering | Maintained massive commercial fleet driver demand for company electric cars. |
| **Home Charger Grant** | €600 SEAI grant towards home wallbox installation | €300 SEAI grant | Seeded Ireland's pervasive private home-charging infrastructure. |
| **Annual Motor Tax** | €120 flat annual rate (Band A0) | €120 flat annual rate (Band A0) | Generates €200–€500 in annual recurring savings vs equivalent petrol/diesel vehicles. |

---

## 5. SQL Analytical Query Recipes

These queries execute against `data/irish_car_sales.db`:

```sql
-- 1. 12-Year Powertrain Market Share Shift (CSO TEM12)
SELECT year,
       total_cars,
       electric AS ev_units,
       electric_share_pct AS ev_share,
       diesel AS diesel_units,
       diesel_share_pct AS diesel_share,
       petrol_share_pct AS petrol_share,
       hybrid_share_pct AS hybrid_share,
       phev_share_pct AS phev_share
FROM v_powertrain_annual
ORDER BY year DESC;

-- 2. Monthly EV vs Diesel Death-Cross (The Crossover Analysis)
SELECT month_code,
       date_val,
       electric_units,
       diesel_units,
       ev_to_diesel_ratio,
       CASE WHEN electric_units > diesel_units THEN 'EV Dominant' ELSE 'Diesel Dominant' END AS market_regime
FROM v_ev_vs_diesel_crossover
WHERE year >= 2024
ORDER BY month_code ASC;

-- 3. Top 15 Best-Selling Pure EV Models of All-Time (Cumulative 2014-2026)
SELECT full_name,
       make,
       model,
       SUM(annual_units) AS cumulative_units
FROM v_model_historical_trajectory
WHERE full_name IN (
    'Volkswagen ID.4', 'Tesla Model 3', 'Tesla Model Y', 'Nissan Leaf',
    'Skoda Enyaq', 'Volkswagen ID.3', 'Kia EV6', 'Kia EV3', 'Hyundai Ioniq 5',
    'BYD Atto 3', 'BYD Seal', 'MG 4', 'Volvo EX30', 'BMW i4', 'Renault Zoe'
)
GROUP BY full_name, make, model
ORDER BY cumulative_units DESC;

-- 4. Geographic EV Penetration Index (Latest Reporting Year Dynamically)
SELECT licensing_authority,
       year,
       ev_units,
       total_units,
       ev_penetration_pct,
       share_of_national_ev_pct
FROM v_county_ev_ranking_latest
ORDER BY ev_penetration_pct DESC;
```

---

## 6. Cross-Reference Index
* For official CSO tables and schema reference: [cso_table_catalog.md](cso_table_catalog.md)
* For SIMI real-time Inertia extraction guide: [simi_api_reference.md](simi_api_reference.md)
* For database schema and turnkey rebuild pipelines: [SKILL.md](../SKILL.md)
