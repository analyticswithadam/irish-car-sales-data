#!/usr/bin/env python3
"""
Pull latest vehicle registration statistics from SIMI (Society of the Irish Motor Industry).
Extracts passenger cars, light commercial vehicles (LCV), heavy commercial vehicles (HCV), and buses.
Futureproof design: provides both dynamic annual columns (units_YYYY) and normalized invariant columns (units_latest, units_prev).
"""

import urllib.request
from http_util import open_url
import json
import re
import html
import os
import sys
import argparse
import pandas as pd
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

# HTTPS goes through http_util.open_url: certificates are verified, with a guarded fallback.

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

def fetch_simi_category(category=''):
    url = f'https://stats.simi.ie/{category}'
    req = urllib.request.Request(url, headers=HEADERS)
    with open_url(req, timeout=60) as resp:
        content = resp.read().decode('utf-8', errors='ignore')
        
    m = re.search(r'data-page=\"([^\"]+)\"', content)
    if not m:
        raise ValueError(f"Could not find data-page in response for {url}")
        
    page_data = json.loads(html.unescape(m.group(1)))
    version = page_data.get('version')
    component = page_data.get('component')
    if component == 'Public/Updating' or not page_data.get('deferredProps'):
        # SIMI takes the portal offline while it loads each month's figures (usually the 1st).
        raise RuntimeError(f"SIMI portal is not serving data right now (component={component}); try again later")
    deferred_props_map = page_data.get('deferredProps', {})
    deferred = list(deferred_props_map.keys())
    env_date = page_data.get('props', {}).get('environmentDate')
    
    partial_data = ','.join(deferred)
    req2 = urllib.request.Request(
        url,
        headers={
            **HEADERS,
            'X-Inertia': 'true',
            'X-Inertia-Version': version,
            'X-Inertia-Partial-Component': component,
            'X-Inertia-Partial-Data': partial_data,
            'Accept': 'text/html, application/xhtml+xml',
            'X-Requested-With': 'XMLHttpRequest'
        }
    )
    with open_url(req2, timeout=60) as resp2:
        res = json.loads(resp2.read().decode('utf-8'))
        props = res.get('props', {})
        props['_meta'] = {
            'environmentDate': env_date,
            'category': category or 'passenger',
            'fetchedAt': datetime.now().isoformat()
        }
        return props

def parse_generic_breakdown(table_dict, key_name='name'):
    """
    Parses SIMI tables with structure:
    years: [year_latest, year_prev, year_prior]
    datasets: [{'label': 'TOYOTA', 'units': [{'count': 16913, 'change': 5.98}, ...], 'shares': [13.87, ...]}, ...]
    Extracts both dynamic year columns (units_YYYY) and invariant columns (units_latest, units_prev).
    """
    if not table_dict or 'years' not in table_dict or 'datasets' not in table_dict:
        return pd.DataFrame()
        
    years = table_dict['years']
    datasets_raw = table_dict['datasets']
    
    if isinstance(datasets_raw, dict):
        items_list = []
        for sub_key, sub_items in datasets_raw.items():
            if isinstance(sub_items, list):
                for si in sub_items:
                    si_copy = dict(si)
                    si_copy['standard'] = sub_key
                    items_list.append(si_copy)
    elif isinstance(datasets_raw, list):
        items_list = datasets_raw
    else:
        return pd.DataFrame()
        
    rows = []
    for item in items_list:
        row = {}
        if 'standard' in item:
            row['standard'] = item['standard']
            
        if 'labels' in item and isinstance(item['labels'], dict):
            for lk, lv in item['labels'].items():
                if lk != 'logo':
                    row[lk] = lv
        elif 'label' in item:
            row[key_name] = item['label']
            
        if 'range' in item:
            row['co2_range'] = item['range']
            
        units = item.get('units', [])
        shares = item.get('shares', [])
        
        # Invariant latest metadata
        if len(years) > 0:
            row['year_latest'] = years[0]
        if len(years) > 1:
            row['year_prev'] = years[1]
            
        for idx, y in enumerate(years):
            u_info = units[idx] if idx < len(units) else {}
            count_val = u_info.get('count') if isinstance(u_info, dict) else u_info
            change_val = u_info.get('change') if isinstance(u_info, dict) else None
            share_val = shares[idx] if idx < len(shares) else None
            
            # Dynamic year columns
            row[f'units_{y}'] = count_val
            row[f'change_pct_{y}'] = change_val
            row[f'market_share_pct_{y}'] = share_val
            
            # Standardized invariant columns
            if idx == 0:
                row['units_latest'] = count_val
                row['change_pct_latest'] = change_val
                row['market_share_pct_latest'] = share_val
            elif idx == 1:
                row['units_prev'] = count_val
                row['change_pct_prev'] = change_val
                row['market_share_pct_prev'] = share_val
            elif idx == 2:
                row['units_prior'] = count_val
                row['change_pct_prior'] = change_val
                row['market_share_pct_prior'] = share_val
            
        rows.append(row)
        
    df = pd.DataFrame(rows)
    if 'units_latest' in df.columns:
        df['rank_latest'] = df['units_latest'].rank(ascending=False, method='min').fillna(9999).astype(int)
    return df

def parse_monthly_table(table_dict):
    """
    Parses totalRegistrationsTable with structure:
    years: [year_latest, year_prev, ...]
    labels: ['Jan', 'Feb', ...]
    datasets: [{'label': 2026, 'data': [{'count': ..., 'change': ...}, ...]}, ...]
    totals: [{'count': ..., 'change': ...}, ...]
    """
    if not table_dict or 'years' not in table_dict:
        return pd.DataFrame(), pd.DataFrame()
        
    years = table_dict['years']
    months = table_dict.get('labels', [])
    datasets = table_dict.get('datasets', [])
    totals = table_dict.get('totals', [])
    
    year_map = {ds['label']: ds['data'] for ds in datasets if 'label' in ds}
    
    monthly_rows = []
    for m_idx, m_name in enumerate(months):
        row = {'month': m_name, 'month_num': m_idx + 1}
        for idx, y in enumerate(years):
            y_data = year_map.get(y, [])
            item = y_data[m_idx] if m_idx < len(y_data) else {}
            count_val = item.get('count') if isinstance(item, dict) else (item if item is not None else None)
            change_val = item.get('change') if isinstance(item, dict) else None
            
            row[f'units_{y}'] = count_val
            row[f'change_pct_{y}'] = change_val
            
            if idx == 0:
                row['units_latest'] = count_val
                row['change_pct_latest'] = change_val
            elif idx == 1:
                row['units_prev'] = count_val
                row['change_pct_prev'] = change_val
                
        monthly_rows.append(row)
        
    df_monthly = pd.DataFrame(monthly_rows)
    
    total_rows = []
    for idx, y in enumerate(years):
        t_info = totals[idx] if idx < len(totals) else {}
        total_rows.append({
            'year': y,
            'ytd_units': t_info.get('count'),
            'change_pct': t_info.get('change'),
            'is_latest': 1 if idx == 0 else 0
        })
    df_totals = pd.DataFrame(total_rows)
    
    return df_monthly, df_totals

TABLE_MAPPINGS = [
    ('carsByMake', 'by_make', 'make'),
    ('carsByModel', 'by_model', 'model'),
    ('carsByEngineType', 'by_fuel_engine', 'engine_type'),
    ('carsByTransmission', 'by_transmission', 'transmission'),
    ('carsByBodyType', 'by_body_type', 'body_type'),
    ('carsByCounty', 'by_county', 'county'),
    ('carsBySegment', 'by_segment', 'segment'),
    ('carsByColour', 'by_colour', 'colour'),
    ('carsByCo2Band', 'by_co2_band', 'co2_band'),
    ('carsByWeight', 'by_weight', 'weight'),
]

SIMI_CATEGORIES = [('', 'passenger'), ('lcv', 'lcv'), ('hcv', 'hcv'), ('bus', 'bus')]

def download_simi_category(url_cat, name, output_dir):
    """Fetches one SIMI category and writes its raw JSON plus one CSV per breakdown."""
    try:
        props = fetch_simi_category(url_cat)
        with open(f"{output_dir}/simi_{name}_raw.json", "w") as f:
            json.dump(props, f)

        saved = []
        total_table = props.get('totalRegistrationsTable') or props.get('totalRegistrations')
        if total_table:
            df_monthly, df_totals = parse_monthly_table(total_table)
            df_monthly.to_csv(f"{output_dir}/{name}_monthly.csv", index=False)
            df_totals.to_csv(f"{output_dir}/{name}_ytd_totals.csv", index=False)
            saved += ['monthly', 'ytd_totals']

        for prop_key, suffix, col_name in TABLE_MAPPINGS:
            if props.get(prop_key):
                df = parse_generic_breakdown(props[prop_key], key_name=col_name)
                if not df.empty:
                    df.to_csv(f"{output_dir}/{name}_{suffix}.csv", index=False)
                    saved.append(suffix)
        print(f"  [SIMI] {name}: {len(saved)} tables ({props['_meta']['environmentDate']})")
        return props['_meta']
    except Exception as e:
        print(f"  [SIMI] Error processing category {name}: {e}", file=sys.stderr)
        return None

def download_all_simi(output_dir='data/simi'):
    """Programmatic entry point: pulls all SIMI categories in parallel."""
    os.makedirs(output_dir, exist_ok=True)
    with ThreadPoolExecutor(max_workers=len(SIMI_CATEGORIES)) as pool:
        list(pool.map(lambda c: download_simi_category(c[0], c[1], output_dir), SIMI_CATEGORIES))
    return output_dir

def main():
    parser = argparse.ArgumentParser(description="Pull latest SIMI Motorstats vehicle registrations.")
    parser.add_argument("--output", default="data/simi", help="Output directory to save CSVs (default: data/simi)")
    parser.add_argument("--category", choices=["passenger", "lcv", "hcv", "bus", "all"], default="all", help="Vehicle category to fetch")
    args = parser.parse_args()

    if args.category == "all":
        download_all_simi(output_dir=args.output)
    else:
        cats = {'passenger': '', 'lcv': 'lcv', 'hcv': 'hcv', 'bus': 'bus'}
        os.makedirs(args.output, exist_ok=True)
        download_simi_category(cats[args.category], args.category, args.output)

if __name__ == '__main__':
    main()
