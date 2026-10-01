#!/usr/bin/env python3
"""
Turnkey Data Verifier and Builder for Irish Car Sales Intelligence (Bundled with irish-car-sales-data skill).

Ensures the SQLite database 'data/irish_car_sales.db' exists, matches the current schema version,
and is ready for analysis. If the database is missing, outdated, or an update is requested,
it pulls official data from SIMI and CSO Ireland and rebuilds it (~3 seconds).

The check itself uses only the standard library, so it costs a few milliseconds.
"""

import os
import sys
import argparse
import sqlite3

# Keep in step with build_database.SCHEMA_VERSION (duplicated so the fast path never imports pandas).
SCHEMA_VERSION = 2

def database_status(db_path):
    """Returns (ok, reason). ok is True when the database is present, current and populated."""
    if not os.path.exists(db_path):
        return False, "not found"
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        try:
            row = conn.execute("SELECT value FROM _build_info WHERE key = 'schema_version'").fetchone()
            version = int(row[0]) if row else 0
            rows = conn.execute("SELECT count(*) FROM cso_fuel_monthly").fetchone()[0]
        finally:
            conn.close()
    except sqlite3.Error as e:
        return False, f"unreadable or pre-v{SCHEMA_VERSION} schema ({e})"
    if version < SCHEMA_VERSION:
        return False, f"schema v{version} is older than v{SCHEMA_VERSION}"
    if rows <= 1000:
        return False, "cso_fuel_monthly is nearly empty"
    return True, f"schema v{version}, {rows:,} rows in cso_fuel_monthly"

def ensure_database(db_path='data/irish_car_sales.db', force_update=False, verbose=True):
    """
    Ensures that the target SQLite database exists, is current and is populated.
    If not, or if force_update is True, it pulls live data from SIMI and CSO and rebuilds it.
    """
    ok, reason = database_status(db_path)
    if ok and not force_update:
        if verbose:
            print(f"[Database] {db_path} ready ({reason}).")
        return db_path

    if verbose:
        why = "update requested" if ok else reason
        print(f"[AutoBuild] Rebuilding {db_path} ({why}) from live SIMI & CSO data...")

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
    return db_path

def main():
    parser = argparse.ArgumentParser(description="Ensure Irish vehicle sales database is present and up-to-date.")
    parser.add_argument("--db-path", default="data/irish_car_sales.db", help="Path to SQLite database")
    parser.add_argument("--update", action="store_true", help="Force refresh from live APIs even if database exists")
    parser.add_argument("--verify-only", action="store_true", help="Only verify database integrity without downloading")
    args = parser.parse_args()

    if args.verify_only:
        ok, reason = database_status(args.db_path)
        print(f"[Verify] {args.db_path}: {'OK' if ok else 'NEEDS REBUILD'} ({reason})")
        sys.exit(0 if ok else 1)

    ensure_database(db_path=args.db_path, force_update=args.update, verbose=True)

if __name__ == '__main__':
    main()
