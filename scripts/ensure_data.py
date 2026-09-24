#!/usr/bin/env python3
"""
Turnkey Data Verifier and Builder for Irish Car Sales Intelligence (Bundled with irish-car-sales-data skill).

Ensures the SQLite database 'data/irish_car_sales.db' exists, is valid,
and is ready for analysis. If the database is missing or an update is requested,
it automatically pulls official data from SIMI and CSO Ireland, normalizes it,
and builds the SQLite database.
"""

import os
import sys
import argparse
import sqlite3

def ensure_database(db_path='data/irish_car_sales.db', force_update=False, verbose=True):
    """
    Ensures that the target SQLite database exists and is populated.
    If not present or force_update is True, it triggers a live pull from SIMI and CSO
    and rebuilds the database from scratch.
    """
    if os.path.exists(db_path) and not force_update:
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name IN ('cso_fuel_monthly', 'simi_passenger_makes');")
            count = cursor.fetchone()[0]
            if count >= 2:
                cursor.execute("SELECT count(*) FROM cso_fuel_monthly;")
                rows = cursor.fetchone()[0]
                conn.close()
                if rows > 1000:
                    if verbose:
                        print(f"[Database] Found verified database at {db_path} ({rows:,} records in cso_fuel_monthly). Ready.")
                    return db_path
        except Exception as e:
            if verbose:
                print(f"[Database] Integrity check failed ({e}). Rebuilding database...")

    if verbose:
        print(f"\n=======================================================")
        print(f"[AutoBuild] Database '{db_path}' not present or update requested.")
        print(f"[AutoBuild] Automatically fetching official datasets from SIMI & CSO...")
        print(f"=======================================================\n")
        
    script_dir = os.path.dirname(os.path.abspath(__file__))
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)
        
    try:
        from build_database import auto_pull_and_build
        auto_pull_and_build(db_path=db_path)
    except Exception as e:
        print(f"[AutoBuild] Error building database: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
        
    if verbose:
        print(f"[AutoBuild] Database successfully verified and ready at {db_path}.")
    return db_path

def main():
    parser = argparse.ArgumentParser(description="Ensure Irish vehicle sales database is present and up-to-date.")
    parser.add_argument("--db-path", default="data/irish_car_sales.db", help="Path to SQLite database")
    parser.add_argument("--update", action="store_true", help="Force refresh from live APIs even if database exists")
    parser.add_argument("--verify-only", action="store_true", help="Only verify database integrity without downloading")
    args = parser.parse_args()

    if args.verify_only:
        if not os.path.exists(args.db_path):
            print(f"[Verify] Database file {args.db_path} does not exist.")
            sys.exit(1)
        conn = sqlite3.connect(args.db_path)
        c = conn.cursor()
        c.execute("SELECT count(*) FROM sqlite_master WHERE type IN ('table', 'view');")
        objs = c.fetchone()[0]
        conn.close()
        print(f"[Verify] Database exists with {objs} tables/views.")
        return

    ensure_database(db_path=args.db_path, force_update=args.update, verbose=True)

if __name__ == '__main__':
    main()
