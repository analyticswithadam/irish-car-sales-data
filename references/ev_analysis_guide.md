# Electric Vehicle (EV) Analysis & Intelligence Guide

This guide details methodologies, data classification rules, policy frameworks, and SQL analytical patterns for analyzing the electric vehicle market, battery electrification trends, and powertrain transitions in Ireland.

---

## 1. Powertrain Taxonomy & Market Definitions

In Irish automotive statistics, vehicles are categorized across five primary powertrain groups:

| Powertrain Category | SIMI Fuel Code | CSO Fuel Code (`TEM12`, `TEM27`) | 2026 Market Share | Analytical Definition & Inclusions |
| :--- | :--- | :--- | :--- | :--- |
| **Pure BEV** | `Electric` | `Electric` | **26.30%** | Pure Battery Electric Vehicle (100% electric, zero tailpipe emissions). |
| **PHEV** | `Petrol/Plug-In Electric Hybrid`, `Diesel/Plug-In Electric Hybrid` | `Petrol or Diesel plug-in hybrid electric` | **14.85%** | Plug-in Hybrid Electric Vehicle with external charging socket and internal combustion engine backup. |
| **HEV (Self-Charging)** | `Petrol Electric (Hybrid)`, `Diesel Electric (Hybrid)` | `Petrol and electric hybrid`, `Diesel and electric hybrid` | **25.78%** | Self-charging mild/full hybrid without external plug-in socket (kinetic brake regeneration). |
| **ICE (Petrol)** | `Petrol` | `Petrol` | **20.09%** | Pure internal combustion engine running on unleaded petrol. |
| **ICE (Diesel)** | `Diesel` | `Diesel` | **12.56%** | Pure internal combustion compression-ignition diesel engine. |

### Analytical Aggregation Rules:
* **"Pure EV" (or "BEV")**: Refers exclusively to **BEV** (32,072 units / **26.30% share** in 2026 YTD).
* **"Total Plug-in"**: BEV + PHEV (50,179 units / **41.15% share**). Over 4 in every 10 new cars registered have an external charge port.
* **"Total Electrified"**: BEV + PHEV + HEV (**66.93% share**). Two out of every three new cars sold in Ireland feature an electric traction motor.
* **The "EV vs. Diesel Crossover"**: In 2025/2026, pure BEVs decisively overtook Diesel in Irish registrations, reversing a 20-year diesel dominance initiated by the 2008 CO2-based motor tax reform.

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
  * **Volkswagen**: `ID.3`, `ID.4` (#1 EV in Ireland), `ID.5`, `ID.7`, `ID BUZZ PC`
  * **Škoda**: `ENYAQ`, `ELROQ`
  * **CUPRA**: `BORN`, `TAVASCAN`
  * **Audi**: `Q4 E-TRON`, `Q6 E-TRON`, `Q8 E-TRON`, `E-TRON GT`
  * **Porsche**: `TAYCAN`, `MACAN ELECTRIC`
* **Hyundai Motor Group**:
  * **Kia**: `EV2`, `EV3` (2025/2026 sales surge), `EV4`, `EV5`, `EV6`, `EV9`
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
  * **Volvo**: `EX30` (Top 5 EV), `EX40`, `EC40`, `EX90`
  * **Renault**: `ZOE` (Historical pioneer), `MEGANE E-TECH`, `SCENIC E-TECH`, `5 E-TECH`
  * **Nissan**: `LEAF` (First mass-market EV in Ireland), `ARIYA`
  * **Ford**: `EXPLORER`, `CAPRI`, `MUSTANG MACH-E`
  * **MG**: `MG4` (High-volume budget benchmark), `CYBERSTER`, `ZS EV`, `MG5`

---

## 3. Spatial Dynamics: The Commuter Belt Phenomenon

When evaluating geographic EV adoption using CSO `TEM27`:
* **Raw Volume vs. Market Penetration**:
  * Dublin accounts for the highest raw volume (~35.5% of all national EVs, with 10,858 units), but ranks **10th in market penetration (26.60%)**.
  * Urban apartment density, on-street terraced housing, and shared parking limit overnight home charging availability in Dublin City.
* **Commuter Belt Hotspots (2026 Rankings)**:
  1. **Wicklow**: **39.66%** EV share (National Leader)
  2. **Kildare**: **35.13%** EV share
  3. **Meath**: **34.75%** EV share
  4. **Westmeath**: **30.29%** EV share
  5. **Louth**: **29.55%** EV share
* **Rural Border & Western Counties**:
  * Counties like Donegal (14.2%), Monaghan (15.1%), Leitrim (16.8%), and Mayo (17.4%) exhibit significantly lower penetration due to longer inter-urban distances, perceived charging desert fears, and high diesel preference for agricultural/towing utility.

### Three Structural Drivers of Commuter Belt Adoption:
1. **Driveway Ownership & Cheap Overnight Tariffs**: Over 85% of commuter-county dwellings are detached or semi-detached homes with private off-street driveways. This enables dedicated Level 2 wallbox installation and utilization of Night-Rate and "EV Boost" electricity tariffs (€0.07–€0.10/kWh), costing as little as €5 to €8 for a full 400+ km charge.
2. **Motorway Commute Arbitrage**: Daily commuters traveling 70–120 km on the M7, M4, or M11 clock 25,000–35,000 km annually. Fuel arbitrage saves between €2,500 and €4,000 per year compared to diesel/petrol, completely amortizing vehicle price premiums within 2.5 years.
3. **Corporate Fleet Schemes & BIK Exemption**: High concentration of corporate, tech, financial, and pharmaceutical professionals utilizing Ireland's Benefit-in-Kind (BIK) preferential tax regime.

---

## 4. Irish EV Policy & Incentive Evolution

The Irish EV market trajectory has been heavily dictated by governmental fiscal and tax incentives:

| Incentive Instrument | Peak Era (2019–2023) | Current Status (2024–2026) | Market Consequence |
| :--- | :--- | :--- | :--- |
| **SEAI Purchase Grant** | €5,000 direct purchase grant on private BEVs | Reduced to €3,500 for vehicles priced €14,000–€60,000 | The July 2023 / Jan 2024 grant cuts triggered a temporary -23.5% YoY sales contraction in 2024 ("subsidy hangover"). |
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
* For official CSO tables and schema reference: [cso_table_catalog.md](file:///Users/adamg/Documents/Agents/Data%20Analysis/Mysterio/.agents/skills/irish-car-sales-data/references/cso_table_catalog.md)
* For SIMI real-time Inertia extraction guide: [simi_api_reference.md](file:///Users/adamg/Documents/Agents/Data%20Analysis/Mysterio/.agents/skills/irish-car-sales-data/references/simi_api_reference.md)
* For database schema and turnkey rebuild pipelines: [SKILL.md](file:///Users/adamg/Documents/Agents/Data%20Analysis/Mysterio/.agents/skills/irish-car-sales-data/SKILL.md)
