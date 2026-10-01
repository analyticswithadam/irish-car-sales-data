#!/usr/bin/env python3
"""
Turnkey Database Builder for Irish Vehicle Sales & Registrations (Bundled with irish-car-sales-data skill).
Builds an optimized, futureproof SQLite analytical database combining CSO Ireland and SIMI Motorstats.

The database is written to a temporary file and swapped into place in one step, so a failed or
interrupted build never leaves a half-built database behind. `_build_info` records the schema
version; ensure_data.py rebuilds any database older than SCHEMA_VERSION.

Usage:
    python3 .agents/skills/irish-car-sales-data/scripts/build_database.py [--db-path data/irish_car_sales.db] [--cso-dir data/cso] [--simi-dir data/simi] [--auto-pull]
"""

import sys
import argparse
import sqlite3
import os
import json
import shutil
import tempfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import pandas as pd

# v2: TEM20 stores sales only (rank in its own column), "All models" moved to
#     cso_new_private_cars_monthly, makes resolved from CSO make codes, v_make_annual added.
SCHEMA_VERSION = 2

# CSO TEM20 make codes (first 3 chars of the model code) -> canonical make.
# Resolving by code keeps multi-word and inconsistently spelled makes together
# ("Mercedes Benz A Class" and "Mercedes-Benz GLB", "MG MG4" and "MG5 SW", "Countryman Cooper" and "Mini").
TEM20_MAKES = {
    'ALF': 'Alfa Romeo', 'AUD': 'Audi', 'BMW': 'BMW', 'BYD': 'BYD', 'CIT': 'Citroen',
    'CRP': 'Cupra', 'DAC': 'Dacia', 'FIA': 'Fiat', 'FOR': 'Ford', 'HON': 'Honda',
    'HYU': 'Hyundai', 'JAG': 'Jaguar', 'JEE': 'Jeep', 'KIA': 'Kia', 'LAR': 'Land Rover',
    'LEP': 'Leapmotor', 'LEX': 'Lexus', 'MAZ': 'Mazda', 'MER': 'Mercedes-Benz', 'MGA': 'MG',
    'MIN': 'Mini', 'MIT': 'Mitsubishi', 'NIS': 'Nissan', 'OPE': 'Opel', 'PEU': 'Peugeot',
    'POR': 'Porsche', 'PSR': 'Polestar', 'REN': 'Renault', 'SEA': 'Seat', 'SKO': 'Skoda',
    'SMA': 'Smart', 'SSA': 'SsangYong', 'SUB': 'Subaru', 'SUZ': 'Suzuki', 'TES': 'Tesla',
    'TOY': 'Toyota', 'VOL': 'Volkswagen', 'VOO': 'Volvo', 'XNG': 'Xpeng',
}
# Spellings CSO uses in model names, beyond the canonical make, to strip from the model part.
TEM20_NAME_PREFIXES = {'Land Rover': ['Landrover'], 'Mercedes-Benz': ['Mercedes Benz']}

def read_cso_csv(path, columns):
    """Reads a PxStat CSV and adds month_code, date_val, year, month_num and units columns."""
    df = pd.read_csv(path, usecols=['STATISTIC', 'TLIST(M1)', 'VALUE', *columns],
                     dtype={c: 'string' for c in ['STATISTIC', *columns]}, encoding='utf-8-sig')
    code = df['TLIST(M1)'].astype(int)
    df['month_code'] = code
    df['year'] = code // 100
    df['month_num'] = code % 100
    df['date_val'] = df['year'].astype(str) + '-' + df['month_num'].astype(str).str.zfill(2) + '-01'
    df['units'] = pd.to_numeric(df['VALUE'], errors='coerce').fillna(0).astype(int)
    for c in columns:
        df[c] = df[c].str.strip()
    return df

def split_tem20_name(code, full_name):
    """Returns (MAKE, model) for a TEM20 'Make and Model' label using its make code."""
    make = TEM20_MAKES.get(code[:3])
    if make is None:  # a make CSO added after this map was written: fall back to the first word
        parts = full_name.split(' ', 1)
        return parts[0].upper(), (parts[1] if len(parts) == 2 else full_name)
    for prefix in [make, *TEM20_NAME_PREFIXES.get(make, [])]:
        if full_name.lower().startswith(prefix.lower() + ' '):
            return make.upper(), full_name[len(prefix) + 1:].strip()
    return make.upper(), full_name

def load_tem20(path, conn):
    """TEM20 carries two statistics per model and month: C01 = units, C02 = that month's rank.
    Units and rank become columns of one row; the 'All models' total goes to its own table so
    SUM(units) over cso_make_model_monthly equals the market total."""
    df = read_cso_csv(path, ['C03398V04090', 'Make and Model'])
    df = df.rename(columns={'C03398V04090': 'model_code', 'Make and Model': 'full_name'})
    stat = df['STATISTIC'].str[-3:]
    keys = ['model_code', 'month_code']
    units = df[stat == 'C01']
    rank = df.loc[stat == 'C02', keys + ['units']].rename(columns={'units': 'rank'})
    df = units.merge(rank, on=keys, how='left')

    is_total = df['full_name'] == 'All models'
    total = df.loc[is_total, ['month_code', 'date_val', 'year', 'month_num', 'units']]
    total.to_sql('cso_new_private_cars_monthly', conn, if_exists='replace', index=False)

    df = df[~is_total].copy()
    names = df[['model_code', 'full_name']].drop_duplicates()
    split = {(c, n): split_tem20_name(c, n) for c, n in names.itertuples(index=False)}
    pairs = [split[(c, n)] for c, n in zip(df['model_code'], df['full_name'])]
    df['make'] = [p[0] for p in pairs]
    df['model'] = [p[1] for p in pairs]
    other = df['full_name'] == 'Other'
    df.loc[other, 'make'] = 'OTHER'
    df.loc[other, 'model'] = 'Other'

    df['rank'] = df['rank'].astype('Int64')
    clean = df[['month_code', 'date_val', 'year', 'month_num', 'make', 'model', 'full_name', 'model_code', 'units', 'rank']]
    clean.to_sql('cso_make_model_monthly', conn, if_exists='replace', index=False)
    return len(clean), int(total['units'].sum()), int(clean['units'].sum())

def build_database(db_path='data/irish_car_sales.db', cso_dir='data/cso', simi_dir='data/simi'):
    os.makedirs(os.path.dirname(db_path) or '.', exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(suffix='.db.tmp', dir=os.path.dirname(db_path) or '.')
    os.close(fd)
    conn = sqlite3.connect(tmp_path)
    cursor = conn.cursor()
    # Bulk-load settings: the file is discarded on failure, so durability during the build is irrelevant.
    cursor.execute("PRAGMA journal_mode = OFF;")
    cursor.execute("PRAGMA synchronous = OFF;")

    try:
        _load_all(conn, cursor, cso_dir, simi_dir, previous_db=db_path)
        conn.commit()
        conn.close()
    except BaseException:
        conn.close()
        os.remove(tmp_path)
        raise

    # Swap in atomically and drop the previous database's WAL files, which belong to the old file.
    os.replace(tmp_path, db_path)
    for suffix in ('-wal', '-shm'):
        if os.path.exists(db_path + suffix):
            os.remove(db_path + suffix)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.close()

    print(f"[Build] {db_path} ready ({os.path.getsize(db_path) / 1e6:.1f} MB, schema v{SCHEMA_VERSION})")
    return db_path

def _load_all(conn, cursor, cso_dir, simi_dir, previous_db=None):
    info = {'schema_version': SCHEMA_VERSION, 'built_at': datetime.now().isoformat(timespec='seconds')}

    # =========================================================================
    # 1. LOAD CSO TABLES
    # =========================================================================
    # 1.1 TEM01: Vehicles Licensed by Taxation Class
    f_tem01 = os.path.join(cso_dir, 'cso_tem01_vehicles_licensed_by_taxation_class_monthly.csv')
    if os.path.exists(f_tem01):
        df01 = read_cso_csv(f_tem01, ['Taxation Class']).rename(columns={'Taxation Class': 'taxation_class'})
        clean01 = df01[['month_code', 'date_val', 'year', 'month_num', 'taxation_class', 'units']]
        clean01.to_sql('cso_taxation_class_monthly', conn, if_exists='replace', index=False)
        cursor.execute("CREATE INDEX idx_tem01_date ON cso_taxation_class_monthly(year, month_num);")
        cursor.execute("CREATE INDEX idx_tem01_class ON cso_taxation_class_monthly(taxation_class);")
        print(f"  -> {len(clean01):,} rows into cso_taxation_class_monthly")

    # 1.2 TEM12: New Vehicles by Fuel Type
    f_tem12 = os.path.join(cso_dir, 'cso_tem12_new_vehicles_by_fuel_type_monthly.csv')
    if os.path.exists(f_tem12):
        df12 = read_cso_csv(f_tem12, ['Type of Vehicle Registration', 'Type of Fuel'])
        df12 = df12.rename(columns={'Type of Vehicle Registration': 'vehicle_class', 'Type of Fuel': 'fuel_type'})
        clean12 = df12[['month_code', 'date_val', 'year', 'month_num', 'vehicle_class', 'fuel_type', 'units']]
        clean12.to_sql('cso_fuel_monthly', conn, if_exists='replace', index=False)
        cursor.execute("CREATE INDEX idx_tem12_date ON cso_fuel_monthly(year, month_num);")
        cursor.execute("CREATE INDEX idx_tem12_fuel ON cso_fuel_monthly(fuel_type);")
        cursor.execute("CREATE INDEX idx_tem12_class ON cso_fuel_monthly(vehicle_class);")
        print(f"  -> {len(clean12):,} rows into cso_fuel_monthly")

    # 1.3 TEM20: New Private Cars by Make & Model
    f_tem20 = os.path.join(cso_dir, 'cso_tem20_new_private_cars_by_make_model_monthly.csv')
    if os.path.exists(f_tem20):
        n20, market, summed = load_tem20(f_tem20, conn)
        cursor.execute("CREATE INDEX idx_tem20_date ON cso_make_model_monthly(year, month_num);")
        cursor.execute("CREATE INDEX idx_tem20_make ON cso_make_model_monthly(make, year);")
        cursor.execute("CREATE INDEX idx_tem20_model ON cso_make_model_monthly(model);")
        cursor.execute("CREATE INDEX idx_tem20_fullname ON cso_make_model_monthly(full_name);")
        print(f"  -> {n20:,} rows into cso_make_model_monthly ({summed:,} units; CSO 'All models' total differs by {summed - market:+,})")

    # 1.4 TEM27: County by Fuel Type
    f_tem27 = os.path.join(cso_dir, 'cso_tem27_new_and_secondhand_cars_by_county_fuel_monthly.csv')
    if os.path.exists(f_tem27):
        df27 = read_cso_csv(f_tem27, ['Statistic Label', 'Licensing Authority', 'Type of Fuel'])
        df27 = df27.rename(columns={'Statistic Label': 'reg_type', 'Licensing Authority': 'licensing_authority',
                                    'Type of Fuel': 'fuel_type'})
        clean27 = df27[['month_code', 'date_val', 'year', 'month_num', 'reg_type', 'licensing_authority', 'fuel_type', 'units']]
        clean27.to_sql('cso_county_fuel_monthly', conn, if_exists='replace', index=False)
        cursor.execute("CREATE INDEX idx_tem27_date ON cso_county_fuel_monthly(year, month_num);")
        cursor.execute("CREATE INDEX idx_tem27_auth ON cso_county_fuel_monthly(licensing_authority);")
        cursor.execute("CREATE INDEX idx_tem27_fuel ON cso_county_fuel_monthly(fuel_type);")
        print(f"  -> {len(clean27):,} rows into cso_county_fuel_monthly")

    for code in ('TEM01', 'TEM12', 'TEM20', 'TEM27'):
        meta = os.path.join(cso_dir, f'{code}_metadata.json')
        if os.path.exists(meta):
            with open(meta) as f:
                info[f'cso_{code}_latest_period'] = json.load(f).get('latest_period')

    # =========================================================================
    # 2. LOAD SIMI TABLES
    # =========================================================================
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

    loaded = 0
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
            loaded += 1
    print(f"  -> {loaded} SIMI tables")

    raw = os.path.join(simi_dir, 'simi_passenger_raw.json')
    if os.path.exists(raw):
        with open(raw) as f:
            info['simi_environment_date'] = json.load(f).get('_meta', {}).get('environmentDate')
    elif loaded == 0 and previous_db and os.path.exists(previous_db):
        info['simi_environment_date'] = _carry_over_simi(conn, previous_db)

    # =========================================================================
    # 3. CREATE FUTUREPROOF ANALYTICAL VIEWS
    # =========================================================================
    # Views are dropped first so a rebuild always picks up the current definitions.
    views = {}

    # View 1: Annual Powertrain Breakdown (CSO) - Works across any year range
    views['v_powertrain_annual'] = """
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
    ORDER BY year ASC"""

    # View 2: Monthly EV vs Diesel Crossover (CSO)
    views['v_ev_vs_diesel_crossover'] = """
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
    ORDER BY month_code ASC"""

    # View 3: Dynamic Latest County EV Penetration (CSO) - Invariant to year!
    views['v_county_ev_ranking_latest'] = """
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
    ORDER BY ev_penetration_pct DESC"""

    # View 3b: Backward compatibility alias for 2026 view
    views['v_county_ev_ranking_2026'] = """
    SELECT
        licensing_authority,
        ev_units AS ev_units_2026,
        total_units AS total_units_2026,
        ev_penetration_pct,
        share_of_national_ev_pct
    FROM v_county_ev_ranking_latest"""

    # View 4: Historical Model Trajectory (CSO)
    views['v_model_historical_trajectory'] = """
    SELECT
        full_name,
        make,
        model,
        year,
        SUM(units) AS annual_units
    FROM cso_make_model_monthly
    GROUP BY full_name, make, model, year
    ORDER BY full_name, year"""

    # View 5: Annual units and market share per make (CSO). months_reported < 12 marks a partial year.
    views['v_make_annual'] = """
    WITH market AS (
        SELECT year, SUM(units) AS market_units, COUNT(*) AS months_reported
        FROM cso_new_private_cars_monthly GROUP BY year
    )
    SELECT
        m.year,
        m.make,
        SUM(m.units) AS units,
        k.market_units,
        ROUND(SUM(m.units) * 100.0 / NULLIF(k.market_units, 0), 2) AS market_share_pct,
        k.months_reported
    FROM cso_make_model_monthly m
    JOIN market k ON k.year = m.year
    GROUP BY m.year, m.make
    ORDER BY m.year, units DESC"""

    for name, sql in views.items():
        cursor.execute(f"DROP VIEW IF EXISTS {name};")
        cursor.execute(f"CREATE VIEW {name} AS {sql};")

    cursor.execute("CREATE TABLE _build_info (key TEXT PRIMARY KEY, value TEXT);")
    cursor.executemany("INSERT INTO _build_info VALUES (?, ?);", [(k, str(v)) for k, v in info.items()])

def _carry_over_simi(conn, previous_db):
    """When SIMI could not be fetched, copies the simi_* tables from the database being replaced
    so a rebuild never loses them. Returns the carried-over SIMI date, if recorded."""
    conn.execute("ATTACH DATABASE ? AS prev", (previous_db,))
    try:
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM prev.sqlite_master WHERE type = 'table' AND name LIKE 'simi\\_%' ESCAPE '\\'")]
        for t in tables:
            conn.execute(f'CREATE TABLE "{t}" AS SELECT * FROM prev."{t}"')
        try:
            date = conn.execute("SELECT value FROM prev._build_info WHERE key = 'simi_environment_date'").fetchone()
            date = date[0] if date else None
        except sqlite3.Error:
            date = None
        conn.commit()
    finally:
        conn.execute("DETACH DATABASE prev")
    print(f"  [warn] SIMI unavailable: kept {len(tables)} SIMI tables from the previous database", file=sys.stderr)
    return date

def auto_pull_and_build(db_path='data/irish_car_sales.db'):
    """Pulls fresh data from the live SIMI and CSO APIs (concurrently) and builds the database."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from pull_simi import download_all_simi
    from pull_cso import download_all_cso

    base_dir = os.path.dirname(db_path) or '.'
    os.makedirs(base_dir, exist_ok=True)
    tmp_root = tempfile.mkdtemp(prefix='.tmp_pull_', dir=base_dir)
    tmp_cso = os.path.join(tmp_root, 'cso')
    tmp_simi = os.path.join(tmp_root, 'simi')
    try:
        print("[AutoPull] Fetching SIMI and CSO datasets in parallel...")
        with ThreadPoolExecutor(max_workers=2) as pool:
            jobs = [pool.submit(download_all_simi, output_dir=tmp_simi),
                    pool.submit(download_all_cso, output_dir=tmp_cso)]
            for job in jobs:
                job.result()
        build_database(db_path=db_path, cso_dir=tmp_cso, simi_dir=tmp_simi)
    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)
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
