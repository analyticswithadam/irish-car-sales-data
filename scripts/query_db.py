#!/usr/bin/env python3
"""
Interactive & CLI Query Utility for the Irish Vehicle Sales Database (Bundled with irish-car-sales-data skill).

Examples:
    # Run a simple query
    python3 .agents/skills/irish-car-sales-data/scripts/query_db.py "SELECT * FROM v_powertrain_annual ORDER BY year DESC"

    # Export to JSON
    python3 .agents/skills/irish-car-sales-data/scripts/query_db.py "SELECT * FROM v_county_ev_ranking_latest LIMIT 5" --format json

    # List all tables and views
    python3 .agents/skills/irish-car-sales-data/scripts/query_db.py --tables
"""

import sys
import argparse
import sqlite3
import json
import os
import pandas as pd

def ensure_db_ready(db_path):
    if not os.path.exists(db_path):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        if script_dir not in sys.path:
            sys.path.insert(0, script_dir)
        try:
            from ensure_data import ensure_database
            ensure_database(db_path=db_path, verbose=True)
        except Exception as e:
            print(f"Error auto-building database: {e}", file=sys.stderr)

def query_database(sql, db_path='data/irish_car_sales.db', output_format='table'):
    ensure_db_ready(db_path)
    conn = sqlite3.connect(db_path)
    try:
        df = pd.read_sql_query(sql, conn)
        if output_format == 'json':
            print(df.to_json(orient='records', indent=2))
        elif output_format == 'csv':
            print(df.to_csv(index=False))
        else:
            pd.set_option('display.max_columns', 15)
            pd.set_option('display.width', 1000)
            if df.empty:
                print("(0 rows returned)")
            else:
                print(df.to_string(index=False))
                print(f"\n({len(df)} rows)")
    except Exception as e:
        print(f"SQL Error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        conn.close()

def list_tables_and_views(db_path='data/irish_car_sales.db'):
    ensure_db_ready(db_path)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT type, name FROM sqlite_master WHERE type IN ('table', 'view') AND name NOT LIKE 'sqlite_%' ORDER BY type, name;")
    rows = cursor.fetchall()
    conn.close()
    
    print(f"\nObjects in {db_path}:")
    print("---------------------------------------------")
    for obj_type, name in rows:
        print(f"[{obj_type.upper():5}] {name}")

def main():
    parser = argparse.ArgumentParser(description="Query the Irish Vehicle Sales SQLite Database.")
    parser.add_argument("query", nargs="?", help="SQL query to execute")
    parser.add_argument("--db-path", default="data/irish_car_sales.db", help="Path to database file")
    parser.add_argument("--format", choices=["table", "json", "csv"], default="table", help="Output format")
    parser.add_argument("--tables", action="store_true", help="List all tables and views")
    args = parser.parse_args()

    if args.tables:
        list_tables_and_views(args.db_path)
        return

    if not args.query:
        parser.print_help()
        sys.exit(0)

    query_database(args.query, db_path=args.db_path, output_format=args.format)

if __name__ == '__main__':
    main()
