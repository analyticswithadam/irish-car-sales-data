#!/usr/bin/env python3
"""
Pull official vehicle registration datasets from Central Statistics Office (CSO) Ireland PxStat API.
Tables included:
- TEM01: Vehicles Licensed for the First Time by Taxation Class (1996 - present)
- TEM12: New Vehicles Licensed for the First Time by Fuel Type & Class (2015 - present)
- TEM20: New Private Cars Licensed for the First Time by Make and Model (2014 - present)
- TEM27: New and Secondhand Private Cars by County/Authority and Fuel Type (2021 - present)
"""

import urllib.request
import ssl
import json
import os
import sys
import argparse
from datetime import datetime

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
}

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

def download_cso_table(table_info, output_dir='data/cso'):
    code = table_info['code']
    filename = table_info['name']
    target_path = os.path.join(output_dir, filename)
    meta_path = os.path.join(output_dir, f"{code}_metadata.json")
    
    # 1. Fetch metadata via JSON-stat
    meta_url = f"https://ws.cso.ie/public/api.restful/PxStat.Data.Cube_API.ReadDataset/{code}/JSON-stat/2.0/en"
    print(f"\nFetching metadata for CSO Table {code} ({table_info['desc']})...")
    req_meta = urllib.request.Request(meta_url, headers=HEADERS)
    with urllib.request.urlopen(req_meta, context=ctx) as resp:
        meta_json = json.loads(resp.read().decode('utf-8'))
        
    updated = meta_json.get('updated')
    label = meta_json.get('label')
    time_dim = meta_json.get('dimension', {}).get('TLIST(M1)', {}) or meta_json.get('dimension', {}).get('TLIST(A1)', {}) or {}
    time_cats = list(time_dim.get('category', {}).get('label', {}).values())
    latest_period = time_cats[-1] if time_cats else 'Unknown'
    earliest_period = time_cats[0] if time_cats else 'Unknown'
    
    print(f"  Title: {label}")
    print(f"  Last Updated: {updated}")
    print(f"  Coverage: {earliest_period} to {latest_period}")
    
    metadata = {
        'code': code,
        'label': label,
        'updated': updated,
        'earliest_period': earliest_period,
        'latest_period': latest_period,
        'dimensions': list(meta_json.get('dimension', {}).keys()),
        'downloaded_at': datetime.now().isoformat()
    }
    with open(meta_path, 'w') as f:
        json.dump(metadata, f, indent=2)
        
    # 2. Download CSV directly
    csv_url = f"https://ws.cso.ie/public/api.restful/PxStat.Data.Cube_API.ReadDataset/{code}/CSV/1.0/en"
    print(f"  Downloading full CSV from {csv_url} ...")
    req_csv = urllib.request.Request(csv_url, headers=HEADERS)
    with urllib.request.urlopen(req_csv, context=ctx) as resp:
        with open(target_path, 'wb') as out_f:
            while chunk := resp.read(1024 * 1024): # 1MB chunks
                out_f.write(chunk)
                
    file_size_mb = os.path.getsize(target_path) / (1024 * 1024)
    print(f"  Saved {target_path} ({file_size_mb:.2f} MB)")
    return target_path

def download_all_cso(output_dir='data/cso'):
    """Programmatic entry point to pull all core CSO tables."""
    os.makedirs(output_dir, exist_ok=True)
    for t in CSO_TABLES:
        download_cso_table(t, output_dir=output_dir)
    print(f"\n[CSO] Finished downloading all requested datasets to {output_dir}")
    return output_dir

def main():
    parser = argparse.ArgumentParser(description="Pull official CSO Ireland vehicle statistics.")
    parser.add_argument("--output", default="data/cso", help="Output directory to save CSVs (default: data/cso)")
    parser.add_argument("--tables", nargs="+", default=["TEM01", "TEM12", "TEM20", "TEM27"], help="Table codes to download")
    args = parser.parse_args()

    os.makedirs(args.output, exist_ok=True)
    selected = [t for t in CSO_TABLES if t['code'] in args.tables]
    for t in selected:
        download_cso_table(t, output_dir=args.output)

if __name__ == '__main__':
    main()
