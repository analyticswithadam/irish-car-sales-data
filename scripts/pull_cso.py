#!/usr/bin/env python3
"""
Pull official vehicle registration datasets from Central Statistics Office (CSO) Ireland PxStat API.
Tables included:
- TEM01: Vehicles Licensed for the First Time by Taxation Class (1996 - present)
- TEM12: New Vehicles Licensed for the First Time by Fuel Type & Class (2015 - present)
- TEM20: New Private Cars Licensed for the First Time by Make and Model (2014 - present)
- TEM27: New and Secondhand Private Cars by County/Authority and Fuel Type (2021 - present)

All tables download in parallel with gzip transfer encoding (~1s total on a normal connection).

Usage:
    python3 scripts/pull_cso.py [--output data/cso] [--tables TEM20 TEM27]
"""

import urllib.request
from http_util import open_url
import gzip
import json
import os
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

# HTTPS goes through http_util.open_url: certificates are verified, with a guarded fallback.

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
    'Accept-Encoding': 'gzip',
}

CSV_URL = "https://ws.cso.ie/public/api.restful/PxStat.Data.Cube_API.ReadDataset/{code}/CSV/1.0/en"

CSO_TABLES = [
    {
        'code': 'TEM01',
        'name': 'cso_tem01_vehicles_licensed_by_taxation_class_monthly.csv',
        'desc': 'Vehicles Licensed for the First Time by Month and Taxation Class (1996 - present)'
    },
    {
        'code': 'TEM12',
        'name': 'cso_tem12_new_vehicles_by_fuel_type_monthly.csv',
        'desc': 'New Vehicles Licensed for the First Time by Month, Taxation Class, and Fuel Type (2015 - present)'
    },
    {
        'code': 'TEM20',
        'name': 'cso_tem20_new_private_cars_by_make_model_monthly.csv',
        'desc': 'New Private Cars Licensed for the First Time by Month and Make & Model (2014 - present)'
    },
    {
        'code': 'TEM27',
        'name': 'cso_tem27_new_and_secondhand_cars_by_county_fuel_monthly.csv',
        'desc': 'New and Secondhand Private Cars by Month, Licensing Authority, and Fuel Type (2021 - present)'
    }
]

def fetch_bytes(url, timeout=60):
    req = urllib.request.Request(url, headers=HEADERS)
    with open_url(req, timeout=timeout) as resp:
        body = resp.read()
        if resp.headers.get('Content-Encoding') == 'gzip':
            body = gzip.decompress(body)
    return body

def download_cso_table(table_info, output_dir='data/cso'):
    code = table_info['code']
    target_path = os.path.join(output_dir, table_info['name'])

    body = fetch_bytes(CSV_URL.format(code=code))
    with open(target_path, 'wb') as out_f:
        out_f.write(body)

    # Coverage comes from the CSV itself (column 3 is the TLIST month code, e.g. "202608"),
    # so no second request for JSON-stat metadata is needed.
    periods = [line.split(b'","', 3)[2] for line in body.splitlines()[1:] if line]
    metadata = {
        'code': code,
        'label': table_info['desc'],
        'earliest_period': min(periods).decode() if periods else None,
        'latest_period': max(periods).decode() if periods else None,
        'downloaded_at': datetime.now().isoformat(timespec='seconds'),
    }
    with open(os.path.join(output_dir, f"{code}_metadata.json"), 'w') as f:
        json.dump(metadata, f, indent=2)

    print(f"  [CSO] {code}: {len(body) / 1e6:.1f} MB, {metadata['earliest_period']}–{metadata['latest_period']}")
    return target_path

def download_all_cso(output_dir='data/cso', codes=None):
    """Programmatic entry point: pulls the requested CSO tables in parallel."""
    os.makedirs(output_dir, exist_ok=True)
    tables = [t for t in CSO_TABLES if codes is None or t['code'] in codes]
    with ThreadPoolExecutor(max_workers=len(tables) or 1) as pool:
        list(pool.map(lambda t: download_cso_table(t, output_dir), tables))
    return output_dir

def main():
    parser = argparse.ArgumentParser(description="Pull official CSO Ireland vehicle statistics.")
    parser.add_argument("--output", default="data/cso", help="Output directory to save CSVs (default: data/cso)")
    parser.add_argument("--tables", nargs="+", default=[t['code'] for t in CSO_TABLES], help="Table codes to download")
    args = parser.parse_args()
    download_all_cso(output_dir=args.output, codes=args.tables)

if __name__ == '__main__':
    main()
