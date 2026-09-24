#!/usr/bin/env python3
"""
EV Story Analysis & Metric Extraction Script (Bundled with irish-car-sales-data skill).
Queries SQLite database 'data/irish_car_sales.db' to generate 'data/ev_story_metrics.json'.
Completely futureproof: dynamically determines reporting years and computes all KPIs directly from data.
"""

import sys
import argparse
import json
import os
import sqlite3
import pandas as pd

def run_analysis(db_path='data/irish_car_sales.db', output_file='data/ev_story_metrics.json'):
    print(f"[Analysis] Checking database: {db_path}...")
    script_dir = os.path.dirname(os.path.abspath(__file__))
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)
        
    try:
        from ensure_data import ensure_database
        ensure_database(db_path=db_path, verbose=True)
    except Exception as e:
        print(f"[Analysis] Note: ensure_database check: {e}")
        
    conn = sqlite3.connect(db_path)
    
    # 1. Annual Powertrains from analytical view
    df_annual = pd.read_sql_query("SELECT * FROM v_powertrain_annual ORDER BY year ASC", conn)
    if df_annual.empty:
        conn.close()
        raise ValueError("v_powertrain_annual returned 0 rows.")
        
    latest_year = int(df_annual['year'].max())
    prev_year = latest_year - 1
    prior_year = latest_year - 2

    annual_powertrains = []
    for _, row in df_annual.iterrows():
        annual_powertrains.append({
            "year": int(row['year']),
            "total_cars": int(row['total_cars']),
            "electric": int(row['electric']),
            "electric_share": float(row['electric_share_pct']),
            "diesel": int(row['diesel']),
            "diesel_share": float(row['diesel_share_pct']),
            "petrol": int(row['petrol']),
            "petrol_share": float(row['petrol_share_pct']),
            "hybrid": int(row['hybrid_hev']),
            "hybrid_share": float(row['hybrid_share_pct']),
            "phev": int(row['phev']),
            "phev_share": float(row['phev_share_pct']),
            "total_electrified": int(row['electric'] + row['hybrid_hev'] + row['phev']),
            "total_electrified_share": round(float(row['electric_share_pct'] + row['hybrid_share_pct'] + row['phev_share_pct']), 2)
        })

    # 2. County EV ranking from futureproof analytical view
    df_county = pd.read_sql_query("SELECT * FROM v_county_ev_ranking_latest ORDER BY ev_penetration_pct DESC", conn)
    county_metrics = []
    for _, row in df_county.iterrows():
        c_item = {
            "county": row['licensing_authority'],
            "year": int(row['year']),
            "ev_units": int(row['ev_units']),
            "total_units": int(row['total_units']),
            "ev_penetration_pct": float(row['ev_penetration_pct']),
            "share_of_national_ev": float(row['share_of_national_ev_pct']),
            f"ev_units_{latest_year}": int(row['ev_units']),
            f"total_units_{latest_year}": int(row['total_units'])
        }
        county_metrics.append(c_item)

    # 3. SIMI Powertrains & Top Models
    df_simi_fuel = pd.read_sql_query("SELECT * FROM simi_passenger_fuels", conn)
    simi_fuel_list = df_simi_fuel.to_dict(orient='records')
    df_models = pd.read_sql_query("SELECT * FROM simi_passenger_models", conn)
    conn.close()

    pure_ev_makes = {'TESLA', 'POLESTAR', 'XPENG', 'SMART', 'LUCID', 'NIO'}
    known_bevs = {
        ('VOLKSWAGEN', 'ID.4'), ('VOLKSWAGEN', 'ID.3'), ('VOLKSWAGEN', 'ID.7'), 
        ('VOLKSWAGEN', 'ID.5'), ('VOLKSWAGEN', 'ID BUZZ PC'),
        ('SKODA', 'ENYAQ'), ('SKODA', 'ELROQ'),
        ('KIA', 'EV3'), ('KIA', 'EV5'), ('KIA', 'EV6'), ('KIA', 'EV4'), ('KIA', 'EV2'), ('KIA', 'EV9'),
        ('HYUNDAI', 'IONIQ 5'), ('HYUNDAI', 'IONIQ 6'), ('HYUNDAI', 'IONIQ 9'), ('HYUNDAI', 'INSTER'),
        ('BYD', 'ATTO 3'), ('BYD', 'DOLPHIN'), ('BYD', 'DOLPHIN SURF'), ('BYD', 'SEAL'), 
        ('BYD', 'SEALION 7'), ('BYD', 'SEALION 5'),
        ('CUPRA', 'BORN'), ('CUPRA', 'TAVASCAN'),
        ('NISSAN', 'LEAF'), ('NISSAN', 'ARIYA'),
        ('RENAULT', 'ZOE'), ('RENAULT', 'MEGANE E-TECH'), ('RENAULT', 'SCENIC E-TECH'), ('RENAULT', '5'),
        ('FORD', 'EXPLORER'), ('FORD', 'CAPRI'), ('FORD', 'MUSTANG MACH-E'),
        ('AUDI', 'Q4 E-TRON'), ('AUDI', 'Q8 E-TRON'), ('AUDI', 'E-TRON GT'), ('AUDI', 'Q6 E-TRON'),
        ('BMW', 'IX1'), ('BMW', 'IX3'), ('BMW', 'I4'), ('BMW', 'IX'), ('BMW', 'I5'), ('BMW', 'I7'), ('BMW', 'I3'),
        ('MERCEDES-BENZ', 'EQA'), ('MERCEDES-BENZ', 'EQB'), ('MERCEDES-BENZ', 'EQC'), 
        ('MERCEDES-BENZ', 'EQE'), ('MERCEDES-BENZ', 'EQS'),
        ('VOLVO', 'EX30'), ('VOLVO', 'EX40'), ('VOLVO', 'EC40'), ('VOLVO', 'EX90'),
        ('MG', 'MG4'), ('MG', 'CYBERSTER'), ('MG', 'ZS EV'), ('MG', 'MG5')
    }

    ev_models_list = []
    for _, row in df_models.iterrows():
        m = str(row['make']).strip()
        mo = str(row['model']).strip()
        
        u_lat = int(row['units_latest']) if 'units_latest' in row and pd.notnull(row['units_latest']) else int(row.get(f'units_{latest_year}', 0) or 0)
        u_prev = int(row['units_prev']) if 'units_prev' in row and pd.notnull(row['units_prev']) else int(row.get(f'units_{prev_year}', 0) or 0)
        u_prior = int(row['units_prior']) if 'units_prior' in row and pd.notnull(row['units_prior']) else int(row.get(f'units_{prior_year}', 0) or 0)
        
        chg = float(row['change_pct_latest']) if 'change_pct_latest' in row and pd.notnull(row['change_pct_latest']) else float(row.get(f'change_pct_{latest_year}', 0) or 0.0)
        sh = float(row['market_share_pct_latest']) if 'market_share_pct_latest' in row and pd.notnull(row['market_share_pct_latest']) else float(row.get(f'market_share_pct_{latest_year}', 0) or 0.0)
        
        is_bev = (m in pure_ev_makes) or ((m, mo) in known_bevs)
        if is_bev:
            ev_models_list.append({
                "make": m,
                "model": mo,
                "full_name": f"{m} {mo}",
                "units_latest": u_lat,
                "units_prev": u_prev,
                "units_prior": u_prior,
                "change_pct_latest": chg,
                "market_share_pct_latest": sh,
                f"units_{latest_year}": u_lat,
                f"units_{prev_year}": u_prev,
                f"units_{prior_year}": u_prior,
                f"change_pct_{latest_year}": chg,
                f"market_share_pct_{latest_year}": sh
            })
    ev_models_list.sort(key=lambda x: x['units_latest'], reverse=True)

    # 4. Brand & Group aggregates
    brand_ev_agg = {}
    for item in ev_models_list:
        mk = item['make']
        if mk not in brand_ev_agg:
            brand_ev_agg[mk] = {'make': mk, 'units_latest': 0, 'units_prev': 0, 'units_prior': 0}
        brand_ev_agg[mk]['units_latest'] += item['units_latest']
        brand_ev_agg[mk]['units_prev'] += item['units_prev']
        brand_ev_agg[mk]['units_prior'] += item['units_prior']

    brand_ev_list = list(brand_ev_agg.values())
    brand_ev_list.sort(key=lambda x: x['units_latest'], reverse=True)
    for b in brand_ev_list:
        b['growth_pct'] = round(((b['units_latest'] - b['units_prev']) / b['units_prev'] * 100.0), 1) if b['units_prev'] > 0 else 100.0
        b[f'units_{latest_year}'] = b['units_latest']
        b[f'units_{prev_year}'] = b['units_prev']
        b[f'growth_{latest_year}'] = b['growth_pct']

    auto_groups = [
        {
            "group": "Volkswagen Group",
            "brands": ["Volkswagen", "Skoda", "Cupra", "Audi", "Porsche"],
            "units_latest": sum(b['units_latest'] for b in brand_ev_list if b['make'] in ['VOLKSWAGEN', 'SKODA', 'CUPRA', 'AUDI', 'PORSCHE']),
            "key_models": "ID.4, Enyaq, Elroq, ID.3, Tavascan, Born, Q4 e-tron"
        },
        {
            "group": "Hyundai Motor Group",
            "brands": ["Kia", "Hyundai"],
            "units_latest": sum(b['units_latest'] for b in brand_ev_list if b['make'] in ['KIA', 'HYUNDAI']),
            "key_models": "EV3, Inster, EV5, Ioniq 5, EV6, Ioniq 6, EV4"
        },
        {
            "group": "BYD",
            "brands": ["BYD"],
            "units_latest": sum(b['units_latest'] for b in brand_ev_list if b['make'] == 'BYD'),
            "key_models": "Sealion 7, Dolphin Surf, Seal, Atto 3 (plus Seal U DM-i)"
        },
        {
            "group": "Tesla",
            "brands": ["Tesla"],
            "units_latest": sum(b['units_latest'] for b in brand_ev_list if b['make'] == 'TESLA'),
            "key_models": "Model Y, Model 3"
        },
        {
            "group": "BMW Group",
            "brands": ["BMW", "MINI"],
            "units_latest": sum(b['units_latest'] for b in brand_ev_list if b['make'] in ['BMW', 'MINI']),
            "key_models": "iX3, iX1, i4, Cooper SE"
        }
    ]
    for g in auto_groups:
        g[f'units_{latest_year}'] = g['units_latest']
    auto_groups.sort(key=lambda x: x['units_latest'], reverse=True)

    # 5. Dynamic Summary KPIs directly computed from data
    row_lat = df_annual[df_annual['year'] == latest_year].iloc[0]
    row_prev = df_annual[df_annual['year'] == prev_year].iloc[0] if (df_annual['year'] == prev_year).any() else None
    row_prior = df_annual[df_annual['year'] == prior_year].iloc[0] if (df_annual['year'] == prior_year).any() else None

    ev_u_latest = int(row_lat['electric'])
    ev_sh_latest = float(row_lat['electric_share_pct'])
    ev_u_prev = int(row_prev['electric']) if row_prev is not None else 0
    ev_u_prior = int(row_prior['electric']) if row_prior is not None else 0
    ev_growth = round(((ev_u_latest - ev_u_prev) / ev_u_prev * 100), 2) if ev_u_prev > 0 else 0.0

    phev_u_latest = int(row_lat['phev'])
    phev_sh_latest = float(row_lat['phev_share_pct'])
    tot_plug_u = ev_u_latest + phev_u_latest
    tot_plug_sh = round(ev_sh_latest + phev_sh_latest, 2)

    diesel_u_latest = int(row_lat['diesel'])
    diesel_sh_latest = float(row_lat['diesel_share_pct'])
    diesel_u_prev = int(row_prev['diesel']) if row_prev is not None else 0
    diesel_decline = round(((diesel_u_latest - diesel_u_prev) / diesel_u_prev * 100), 2) if diesel_u_prev > 0 else 0.0

    petrol_u_latest = int(row_lat['petrol'])
    petrol_sh_latest = float(row_lat['petrol_share_pct'])
    ev_vs_diesel_ratio = round(ev_u_latest / diesel_u_latest, 2) if diesel_u_latest > 0 else None

    top_m = ev_models_list[0] if ev_models_list else {}
    top_vol_c = df_county.sort_values(by='ev_units', ascending=False).iloc[0] if not df_county.empty else {}
    top_pen_c = df_county.sort_values(by='ev_penetration_pct', ascending=False).iloc[0] if not df_county.empty else {}

    summary_kpis = {
        "reporting_year": latest_year,
        "prev_year": prev_year,
        "ev_units_latest": ev_u_latest,
        "ev_market_share_pct": ev_sh_latest,
        "ev_growth_pct": ev_growth,
        "ev_units_prev": ev_u_prev,
        "ev_units_prior": ev_u_prior,
        "phev_units_latest": phev_u_latest,
        "phev_market_share_pct": phev_sh_latest,
        "total_plug_in_units": tot_plug_u,
        "total_plug_in_share_pct": tot_plug_sh,
        "diesel_units_latest": diesel_u_latest,
        "diesel_market_share_pct": diesel_sh_latest,
        "diesel_decline_pct": diesel_decline,
        "petrol_units_latest": petrol_u_latest,
        "petrol_market_share_pct": petrol_sh_latest,
        "ev_vs_diesel_ratio": ev_vs_diesel_ratio,
        "top_model": top_m.get('full_name', ''),
        "top_model_units": top_m.get('units_latest', 0),
        "top_county_volume": f"{top_vol_c.get('licensing_authority', '')} ({int(top_vol_c.get('ev_units', 0)):,})",
        "top_county_penetration": f"{top_pen_c.get('licensing_authority', '')} ({float(top_pen_c.get('ev_penetration_pct', 0)):.1f}%)",
        # Backward compatibility aliases
        f"ev_units_{latest_year}": ev_u_latest,
        f"ev_growth_pct_{latest_year}": ev_growth,
        f"ev_units_{prev_year}": ev_u_prev,
        f"ev_units_{prior_year}": ev_u_prior,
        f"phev_units_{latest_year}": phev_u_latest,
        f"total_plug_in_units_{latest_year}": tot_plug_u,
        f"diesel_units_{latest_year}": diesel_u_latest,
        f"petrol_units_{latest_year}": petrol_u_latest
    }

    output_data = {
        "summary_kpis": summary_kpis,
        "annual_powertrains": annual_powertrains,
        "top_ev_models_latest": ev_models_list[:25],
        "top_ev_brands_latest": brand_ev_list[:15],
        "auto_groups_latest": auto_groups,
        "county_ev_adoption": county_metrics,
        "simi_passenger_fuels": simi_fuel_list,
        # Backward compatibility aliases
        f"top_ev_models_{latest_year}": ev_models_list[:25],
        f"top_ev_brands_{latest_year}": brand_ev_list[:15],
        f"auto_groups_{latest_year}": auto_groups
    }

    os.makedirs(os.path.dirname(output_file) or '.', exist_ok=True)
    with open(output_file, 'w') as f:
        json.dump(output_data, f, indent=2)
        
    print(f"[Analysis] Successfully wrote structured metrics from SQLite to {output_file}")
    return output_data

def main():
    parser = argparse.ArgumentParser(description="Extract structured EV metrics from SQLite database.")
    parser.add_argument("--db-path", default="data/irish_car_sales.db", help="Path to SQLite database")
    parser.add_argument("--output", default="data/ev_story_metrics.json", help="Output JSON path")
    args = parser.parse_args()

    run_analysis(db_path=args.db_path, output_file=args.output)

if __name__ == '__main__':
    main()
