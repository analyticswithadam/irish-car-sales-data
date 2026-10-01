#!/usr/bin/env python3
"""
Interactive & CLI Query Utility for the Irish Vehicle Sales Database (Bundled with irish-car-sales-data skill).

Uses only the standard library (no pandas import), so a query returns in well under 100 ms.

Examples:
    # Run a simple query
    python3 .agents/skills/irish-car-sales-data/scripts/query_db.py "SELECT * FROM v_powertrain_annual ORDER BY year DESC"

    # Export to JSON
    python3 .agents/skills/irish-car-sales-data/scripts/query_db.py "SELECT * FROM v_county_ev_ranking_latest LIMIT 5" --format json

    # List all tables and views
    python3 .agents/skills/irish-car-sales-data/scripts/query_db.py --tables
"""

import sys
import os
import csv
import json
import argparse
import sqlite3

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ensure_data import ensure_database

def _fmt(v):
    if v is None:
        return ''
    if isinstance(v, float):
        return f"{v:,.2f}".rstrip('0').rstrip('.') if abs(v) >= 1000 else f"{v:g}"
    return str(v)

def print_table(cols, rows):
    if not rows:
        print("(0 rows returned)")
        return
    cells = [[_fmt(v) for v in r] for r in rows]
    numeric = [all(isinstance(r[i], (int, float)) or r[i] is None for r in rows) for i in range(len(cols))]
    widths = [max(len(c), *(len(r[i]) for r in cells)) for i, c in enumerate(cols)]
    line = lambda vals: '  '.join(v.rjust(w) if n else v.ljust(w) for v, w, n in zip(vals, widths, numeric)).rstrip()
    print(line(cols))
    print('  '.join('-' * w for w in widths))
    for r in cells:
        print(line(r))
    print(f"\n({len(rows)} rows)")

def query_database(sql, db_path='data/irish_car_sales.db', output_format='table'):
    ensure_database(db_path, verbose=False)
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        cur = conn.execute(sql)
        cols = [d[0] for d in cur.description or []]
        rows = cur.fetchall()
    except sqlite3.Error as e:
        print(f"SQL Error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        conn.close()

    if output_format == 'json':
        print(json.dumps([dict(zip(cols, r)) for r in rows], indent=2))
    elif output_format == 'csv':
        w = csv.writer(sys.stdout)
        w.writerow(cols)
        w.writerows(rows)
    else:
        print_table(cols, rows)

def list_tables_and_views(db_path='data/irish_car_sales.db'):
    ensure_database(db_path, verbose=False)
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    rows = conn.execute("SELECT type, name FROM sqlite_master WHERE type IN ('table', 'view') "
                        "AND name NOT LIKE 'sqlite_%' ORDER BY type, name;").fetchall()
    info = conn.execute("SELECT key, value FROM _build_info ORDER BY key").fetchall()
    conn.close()

    print(f"\nObjects in {db_path}:")
    print("---------------------------------------------")
    for obj_type, name in rows:
        print(f"[{obj_type.upper():5}] {name}")
    print("\nBuild info:")
    for k, v in info:
        print(f"  {k}: {v}")

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
