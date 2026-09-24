#!/usr/bin/env python3
"""
Turnkey Database Builder for Irish Vehicle Sales & Registrations (Bundled with irish-car-sales-data skill).
Builds an optimized, futureproof SQLite analytical database combining CSO Ireland and SIMI Motorstats.

Usage:
    python3 .agents/skills/irish-car-sales-data/scripts/build_database.py [--db-path data/irish_car_sales.db] [--cso-dir data/cso] [--simi-dir data/simi] [--auto-pull]
"""

import sys
import argparse
import sqlite3
import os
import shutil
import pandas as pd
from datetime import datetime

def parse_month_string(m_str):
    """Parses 'YYYY MonthName' (e.g. '2015 January') to date string '2015-01-01' and month_num 1."""
    if not isinstance(m_str, str):
        return None, None
    try:
        dt = datetime.strptime(m_str.strip(), "%Y %B")
        return dt.strftime("%Y-%m-01"), dt.month
    except Exception:
        return None, None

def build_database(db_path='data/irish_car_sales.db', cso_dir='data/cso', simi_dir='data/simi'):
    os.makedirs(os.path.dirname(db_path) or '.', exist_ok=True)
    
    print(f"Connecting to database: {db_path}")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Enable WAL mode for high performance
    cursor.execute("PRAGMA journal_mode = WAL;")
    cursor.execute("PRAGMA synchronous = NORMAL;")

    # =========================================================================
    # 1. LOAD CSO TABLES
    # =========================================================================
    print("\n--- Ingesting CSO Ireland Datasets ---")

    # 1.1 TEM01: Vehicles Licensed by Taxation Class
    f_tem01 = os.path.join(cso_dir, 'cso_tem01_vehicles_licensed_by_taxation_class_monthly.csv')
    if os.path.exists(f_tem01):
        print(f"Loading TEM01: {f_tem01}...")
        df01 = pd.read_csv(f_tem01)
        dates_and_months = [parse_month_string(m) for m in df01['Month']]
        df01['date_val'] = [d[0] for d in dates_and_months]
        df01['month_num'] = [d[1] for d in dates_and_months]
        df01['year'] = df01['TLIST(M1)'].astype(str).str[:4].astype(int)
        df01['units'] = pd.to_numeric(df01['VALUE'], errors='coerce').fillna(0).astype(int)
        df01['taxation_class'] = df01['Taxation Class'].astype(str).str.strip()
        df01['month_code'] = df01['TLIST(M1)'].astype(int)

        clean01 = df01[['month_code', 'date_val', 'year', 'month_num', 'taxation_class', 'units']]
        clean01.to_sql('cso_taxation_class_monthly', conn, if_exists='replace', index=False)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tem01_date ON cso_taxation_class_monthly(year, month_num);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tem01_class ON cso_taxation_class_monthly(taxation_class);")
        print(f"  -> Ingested {len(clean01):,} rows into cso_taxation_class_monthly")

    # 1.2 TEM12: New Vehicles by Fuel Type
    f_tem12 = os.path.join(cso_dir, 'cso_tem12_new_vehicles_by_fuel_type_monthly.csv')
    if os.path.exists(f_tem12):
        print(f"Loading TEM12: {f_tem12}...")
        df12 = pd.read_csv(f_tem12)
        dates_and_months = [parse_month_string(m) for m in df12['Month']]
        df12['date_val'] = [d[0] for d in dates_and_months]
        df12['month_num'] = [d[1] for d in dates_and_months]
        df12['year'] = df12['TLIST(M1)'].astype(str).str[:4].astype(int)
        df12['units'] = pd.to_numeric(df12['VALUE'], errors='coerce').fillna(0).astype(int)
        df12['vehicle_class'] = df12['Type of Vehicle Registration'].astype(str).str.strip()
        df12['fuel_type'] = df12['Type of Fuel'].astype(str).str.strip()
        df12['month_code'] = df12['TLIST(M1)'].astype(int)

        clean12 = df12[['month_code', 'date_val', 'year', 'month_num', 'vehicle_class', 'fuel_type', 'units']]
        clean12.to_sql('cso_fuel_monthly', conn, if_exists='replace', index=False)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tem12_date ON cso_fuel_monthly(year, month_num);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tem12_fuel ON cso_fuel_monthly(fuel_type);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tem12_class ON cso_fuel_monthly(vehicle_class);")
        print(f"  -> Ingested {len(clean12):,} rows into cso_fuel_monthly")

    # 1.3 TEM20: New Private Cars by Make & Model
    f_tem20 = os.path.join(cso_dir, 'cso_tem20_new_private_cars_by_make_model_monthly.csv')
    if os.path.exists(f_tem20):
        print(f"Loading TEM20: {f_tem20}...")
        df20 = pd.read_csv(f_tem20)
        dates_and_months = [parse_month_string(m) for m in df20['Month']]
        df20['date_val'] = [d[0] for d in dates_and_months]
        df20['month_num'] = [d[1] for d in dates_and_months]
        df20['year'] = df20['TLIST(M1)'].astype(str).str[:4].astype(int)
        df20['units'] = pd.to_numeric(df20['VALUE'], errors='coerce').fillna(0).astype(int)
        df20['month_code'] = df20['TLIST(M1)'].astype(int)
        df20['full_name'] = df20['Make and Model'].astype(str).str.strip()
        
        def split_make_model(s):
            parts = s.split(' ', 1)
            if len(parts) == 2:
                return parts[0], parts[1]
            return s, ''
            
        splits = [split_make_model(s) for s in df20['full_name']]
        df20['make'] = [s[0].upper() for s in splits]
        df20['model'] = [s[1] for s in splits]

        clean20 = df20[['month_code', 'date_val', 'year', 'month_num', 'make', 'model', 'full_name', 'units']]
        clean20.to_sql('cso_make_model_monthly', conn, if_exists='replace', index=False)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tem20_date ON cso_make_model_monthly(year, month_num);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tem20_make ON cso_make_model_monthly(make);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tem20_model ON cso_make_model_monthly(model);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tem20_fullname ON cso_make_model_monthly(full_name);")
        print(f"  -> Ingested {len(clean20):,} rows into cso_make_model_monthly")

    # 1.4 TEM27: County by Fuel Type
    f_tem27 = os.path.join(cso_dir, 'cso_tem27_new_and_secondhand_cars_by_county_fuel_monthly.csv')
    if os.path.exists(f_tem27):
        print(f"Loading TEM27: {f_tem27}...")
        df27 = pd.read_csv(f_tem27)
        dates_and_months = [parse_month_string(m) for m in df27['Month']]
        df27['date_val'] = [d[0] for d in dates_and_months]
        df27['month_num'] = [d[1] for d in dates_and_months]
        df27['year'] = df27['TLIST(M1)'].astype(str).str[:4].astype(int)
        df27['units'] = pd.to_numeric(df27['VALUE'], errors='coerce').fillna(0).astype(int)
        df27['month_code'] = df27['TLIST(M1)'].astype(int)
        df27['reg_type'] = df27['Statistic Label'].astype(str).str.strip()
        df27['licensing_authority'] = df27['Licensing Authority'].astype(str).str.strip()
        df27['fuel_type'] = df27['Type of Fuel'].astype(str).str.strip()

        clean27 = df27[['month_code', 'date_val', 'year', 'month_num', 'reg_type', 'licensing_authority', 'fuel_type', 'units']]
        clean27.to_sql('cso_county_fuel_monthly', conn, if_exists='replace', index=False)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tem27_date ON cso_county_fuel_monthly(year, month_num);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tem27_auth ON cso_county_fuel_monthly(licensing_authority);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tem27_fuel ON cso_county_fuel_monthly(fuel_type);")
        print(f"  -> Ingested {len(clean27):,} rows into cso_county_fuel_monthly")

    # =========================================================================
    # 2. LOAD SIMI TABLES
    # =========================================================================
    print("\n--- Ingesting SIMI Motorstats Datasets ---")

    simi_files = {
        'passenger_by_make.csv': 'simi_passenger_makes',
        'passenger_by_model.csv': 'simi_passenger_models',
        'passenger_by_fuel_engine.csv': 'simi_passenger_fuels',
        'passenger_by_county.csv': 'simi_passenger_counties',
        'passenger_by_transmission.csv': 'simi_passenger_transmissions',
        'passenger_by_body_type.csv': 'simi_passenger_body_types',
        'passenger_by_segment.csv': 'simi_passenger_segments',
        'passenger_by_colour.csv': 'simi_passenger_colours',
        'passenger_monthly.csv': 'simi_passenger_monthly',
        'passenger_ytd_totals.csv': 'simi_passenger_ytd_totals',
        'lcv_by_make.csv': 'simi_lcv_makes',
        'lcv_ytd_totals.csv': 'simi_lcv_ytd_totals',
        'hcv_by_make.csv': 'simi_hcv_makes',
        'hcv_ytd_totals.csv': 'simi_hcv_ytd_totals',
        'bus_by_make.csv': 'simi_bus_makes',
        'bus_ytd_totals.csv': 'simi_bus_ytd_totals'
    }

    for fname, table_name in simi_files.items():
        fpath = os.path.join(simi_dir, fname)
        if os.path.exists(fpath):
            df = pd.read_csv(fpath)
            for col in df.columns:
                if 'units' in col or 'rank' in col or 'month_num' in col:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)
                elif 'pct' in col or 'share' in col or 'change' in col:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
                elif 'year' in col:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)
            
            df.to_sql(table_name, conn, if_exists='replace', index=False)
            print(f"  -> Ingested {len(df):,} rows into {table_name}")

    # =========================================================================
    # 3. CREATE FUTUREPROOF ANALYTICAL VIEWS
    # =========================================================================
    print("\n--- Creating Analytical SQL Views ---")

    # View 1: Annual Powertrain Breakdown (CSO) - Works across any year range
    cursor.execute("""
    CREATE VIEW IF NOT EXISTS v_powertrain_annual AS
    SELECT 
        year,
        SUM(CASE WHEN fuel_type = 'All fuel types' THEN units ELSE 0 END) AS total_cars,
        SUM(CASE WHEN fuel_type = 'Electric' THEN units ELSE 0 END) AS electric,
        ROUND(CAST(SUM(CASE WHEN fuel_type = 'Electric' THEN units ELSE 0 END) AS FLOAT) * 100.0 / 
              NULLIF(SUM(CASE WHEN fuel_type = 'All fuel types' THEN units ELSE 0 END), 0), 2) AS electric_share_pct,
        SUM(CASE WHEN fuel_type = 'Diesel' THEN units ELSE 0 END) AS diesel,
        ROUND(CAST(SUM(CASE WHEN fuel_type = 'Diesel' THEN units ELSE 0 END) AS FLOAT) * 100.0 / 
              NULLIF(SUM(CASE WHEN fuel_type = 'All fuel types' THEN units ELSE 0 END), 0), 2) AS diesel_share_pct,
        SUM(CASE WHEN fuel_type = 'Petrol' THEN units ELSE 0 END) AS petrol,
        ROUND(CAST(SUM(CASE WHEN fuel_type = 'Petrol' THEN units ELSE 0 END) AS FLOAT) * 100.0 / 
              NULLIF(SUM(CASE WHEN fuel_type = 'All fuel types' THEN units ELSE 0 END), 0), 2) AS petrol_share_pct,
        SUM(CASE WHEN fuel_type IN ('Petrol and electric hybrid', 'Diesel and electric hybrid') THEN units ELSE 0 END) AS hybrid_hev,
        ROUND(CAST(SUM(CASE WHEN fuel_type IN ('Petrol and electric hybrid', 'Diesel and electric hybrid') THEN units ELSE 0 END) AS FLOAT) * 100.0 / 
              NULLIF(SUM(CASE WHEN fuel_type = 'All fuel types' THEN units ELSE 0 END), 0), 2) AS hybrid_share_pct,
        SUM(CASE WHEN fuel_type = 'Petrol or Diesel plug-in hybrid electric' THEN units ELSE 0 END) AS phev,
        ROUND(CAST(SUM(CASE WHEN fuel_type = 'Petrol or Diesel plug-in hybrid electric' THEN units ELSE 0 END) AS FLOAT) * 100.0 / 
              NULLIF(SUM(CASE WHEN fuel_type = 'All fuel types' THEN units ELSE 0 END), 0), 2) AS phev_share_pct
    FROM cso_fuel_monthly
    WHERE vehicle_class = 'New Private Cars'
    GROUP BY year
    ORDER BY year ASC;
    """)

    # View 2: Monthly EV vs Diesel Crossover (CSO)
    cursor.execute("""
    CREATE VIEW IF NOT EXISTS v_ev_vs_diesel_crossover AS
    SELECT 
        month_code,
        date_val,
        year,
        month_num,
        SUM(CASE WHEN fuel_type = 'Electric' THEN units ELSE 0 END) AS electric_units,
        SUM(CASE WHEN fuel_type = 'Diesel' THEN units ELSE 0 END) AS diesel_units,
        ROUND(CAST(SUM(CASE WHEN fuel_type = 'Electric' THEN units ELSE 0 END) AS FLOAT) / 
              NULLIF(SUM(CASE WHEN fuel_type = 'Diesel' THEN units ELSE 0 END), 0), 2) AS ev_to_diesel_ratio
    FROM cso_fuel_monthly
    WHERE vehicle_class = 'New Private Cars'
    GROUP BY month_code, date_val, year, month_num
    ORDER BY month_code ASC;
    """)

    # View 3: Dynamic Latest County EV Penetration (CSO) - Invariant to year!
    cursor.execute("""
    CREATE VIEW IF NOT EXISTS v_county_ev_ranking_latest AS
    WITH max_yr AS (
        SELECT MAX(year) AS target_year FROM cso_county_fuel_monthly WHERE reg_type = 'New Private Cars'
    ),
    national_ev AS (
        SELECT SUM(units) AS total_ev 
        FROM cso_county_fuel_monthly 
        WHERE year = (SELECT target_year FROM max_yr)
          AND reg_type = 'New Private Cars' 
          AND fuel_type = 'Electric' 
          AND licensing_authority != 'All licensing authorities'
    )
    SELECT 
        c.licensing_authority,
        (SELECT target_year FROM max_yr) AS year,
        SUM(CASE WHEN c.fuel_type = 'Electric' THEN c.units ELSE 0 END) AS ev_units,
        SUM(CASE WHEN c.fuel_type = 'All fuel types' THEN c.units ELSE 0 END) AS total_units,
        ROUND(CAST(SUM(CASE WHEN c.fuel_type = 'Electric' THEN c.units ELSE 0 END) AS FLOAT) * 100.0 /
              NULLIF(SUM(CASE WHEN c.fuel_type = 'All fuel types' THEN c.units ELSE 0 END), 0), 2) AS ev_penetration_pct,
        ROUND(CAST(SUM(CASE WHEN c.fuel_type = 'Electric' THEN c.units ELSE 0 END) AS FLOAT) * 100.0 /
              NULLIF((SELECT total_ev FROM national_ev), 0), 2) AS share_of_national_ev_pct
    FROM cso_county_fuel_monthly c
    WHERE c.year = (SELECT target_year FROM max_yr)
      AND c.reg_type = 'New Private Cars' 
      AND c.licensing_authority != 'All licensing authorities'
    GROUP BY c.licensing_authority
    ORDER BY ev_penetration_pct DESC;
    """)

    # View 3b: Backward compatibility alias for 2026 view
    cursor.execute("""
    CREATE VIEW IF NOT EXISTS v_county_ev_ranking_2026 AS
    SELECT 
        licensing_authority,
        ev_units AS ev_units_2026,
        total_units AS total_units_2026,
        ev_penetration_pct,
        share_of_national_ev_pct
    FROM v_county_ev_ranking_latest;
    """)

    # View 4: Historical Model Trajectory (CSO)
    cursor.execute("""
    CREATE VIEW IF NOT EXISTS v_model_historical_trajectory AS
    SELECT 
        full_name,
        make,
        model,
        year,
        SUM(units) AS annual_units
    FROM cso_make_model_monthly
    GROUP BY full_name, make, model, year
    ORDER BY full_name, year;
    """)

    conn.commit()
    conn.close()

    db_size_mb = os.path.getsize(db_path) / (1024 * 1024)
    print(f"\n[SUCCESS] Local database built successfully at {db_path} ({db_size_mb:.2f} MB)")
    return db_path

def auto_pull_and_build(db_path='data/irish_car_sales.db'):
    """Pulls fresh data directly from live APIs and builds database."""
    base_dir = os.path.dirname(db_path) or '.'
    tmp_cso = os.path.join(base_dir, '.tmp_cso')
    tmp_simi = os.path.join(base_dir, '.tmp_simi')
    os.makedirs(tmp_cso, exist_ok=True)
    os.makedirs(tmp_simi, exist_ok=True)
    
    try:
        from pull_simi import download_all_simi
        from pull_cso import download_all_cso
    except ImportError:
        sys.path.insert(0, os.path.dirname(__file__))
        from pull_simi import download_all_simi
        from pull_cso import download_all_cso
        
    print("\n[AutoPull] Fetching SIMI datasets...")
    download_all_simi(output_dir=tmp_simi)
    
    print("\n[AutoPull] Fetching CSO time-series cubes...")
    download_all_cso(output_dir=tmp_cso)
    
    print("\n[AutoPull] Building SQLite database...")
    build_database(db_path=db_path, cso_dir=tmp_cso, simi_dir=tmp_simi)
    
    shutil.rmtree(tmp_cso, ignore_errors=True)
    shutil.rmtree(tmp_simi, ignore_errors=True)
    print(f"\n[AutoPull] Cleaned up temporary files. Database {db_path} is ready.")
    return db_path

def main():
    parser = argparse.ArgumentParser(description="Build unified SQLite analytical database for Irish car sales.")
    parser.add_argument("--db-path", default="data/irish_car_sales.db", help="Target SQLite file path")
    parser.add_argument("--cso-dir", default="data/cso", help="CSO CSV directory")
    parser.add_argument("--simi-dir", default="data/simi", help="SIMI CSV directory")
    parser.add_argument("--auto-pull", action="store_true", help="Automatically pull data from APIs if directories do not exist")
    args = parser.parse_args()

    if args.auto_pull or (not os.path.exists(args.cso_dir) and not os.path.exists(args.simi_dir)):
        auto_pull_and_build(db_path=args.db_path)
    else:
        build_database(db_path=args.db_path, cso_dir=args.cso_dir, simi_dir=args.simi_dir)

if __name__ == '__main__':
    main()
