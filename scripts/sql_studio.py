#!/usr/bin/env python3
"""
Irish Car Sales & Vehicle Registrations SQL Studio Server (Skill Bundled)
------------------------------------------------------------------------
A lightweight, zero-dependency local HTTP server and SQL execution engine
connecting to 'data/irish_car_sales.db'.
"""

import sys
import os
import json
import time
import socket
import sqlite3
import argparse
import webbrowser
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse

# Ensure repository root is on sys.path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if not os.path.exists(os.path.join(REPO_ROOT, "data")):
    # If running inside skill standalone directory
    REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

try:
    from scripts.ensure_data import ensure_database
except ImportError:
    def ensure_database(path):
        return path

DEFAULT_DB_PATH = os.path.join(REPO_ROOT, "data", "irish_car_sales.db")
HTML_PATH = os.path.join(REPO_ROOT, "sql_studio.html")


def get_db_connection(db_path=DEFAULT_DB_PATH):
    """Establish connection to SQLite database in WAL mode."""
    if not os.path.exists(db_path):
        ensure_database(db_path)
    
    conn = sqlite3.connect(f"file:{os.path.abspath(db_path)}?mode=ro", uri=True, timeout=10.0)
    conn.row_factory = sqlite3.Row
    return conn


def introspect_schema(db_path=DEFAULT_DB_PATH):
    """Retrieve full database schema including tables, views, columns, and row counts."""
    conn = sqlite3.connect(db_path, timeout=10.0)
    cur = conn.cursor()
    
    schema = {
        "tables": [],
        "views": [],
        "total_tables": 0,
        "total_views": 0,
        "database_size_bytes": os.path.getsize(db_path) if os.path.exists(db_path) else 0,
        "database_path": os.path.relpath(db_path, REPO_ROOT),
    }

    cur.execute("""
        SELECT type, name, sql 
        FROM sqlite_master 
        WHERE type IN ('table', 'view') AND name NOT LIKE 'sqlite_%' AND name != '_build_info'
        ORDER BY type, name
    """)
    objects = cur.fetchall()

    for obj_type, obj_name, ddl in objects:
        try:
            cur.execute(f'PRAGMA table_info("{obj_name}")')
            cols_info = cur.fetchall()
            columns = [
                {
                    "cid": col[0],
                    "name": col[1],
                    "type": col[2] or "TEXT",
                    "notnull": bool(col[3]),
                    "dflt_value": col[4],
                    "pk": bool(col[5])
                }
                for col in cols_info
            ]
        except Exception:
            columns = []

        row_count = None
        try:
            cur.execute(f'SELECT count(*) FROM "{obj_name}"')
            row_count = cur.fetchone()[0]
        except Exception:
            row_count = 0

        category = "Other"
        if obj_name.startswith("v_"):
            category = "Curated Analytical Views"
        elif obj_name.startswith("simi_passenger_"):
            category = "SIMI Passenger"
        elif obj_name.startswith("simi_lcv_") or obj_name.startswith("simi_hcv_") or obj_name.startswith("simi_bus_"):
            category = "SIMI Commercial Fleets"
        elif obj_name.startswith("cso_"):
            category = "CSO Historical Cubes"

        item = {
            "name": obj_name,
            "type": obj_type.upper(),
            "category": category,
            "columns": columns,
            "row_count": row_count,
            "column_count": len(columns),
            "ddl": ddl or ""
        }

        if obj_type == "table":
            schema["tables"].append(item)
        else:
            schema["views"].append(item)

    schema["total_tables"] = len(schema["tables"])
    schema["total_views"] = len(schema["views"])
    conn.close()
    return schema


def execute_sql(query, db_path=DEFAULT_DB_PATH, max_rows=5000):
    """Execute SQL query safely and return columns, rows, and execution time."""
    if not query or not query.strip():
        return {"success": False, "error": "Query is empty."}

    cleaned = query.strip()
    disallowed_keywords = ["DROP ", "DELETE ", "UPDATE ", "INSERT ", "ALTER ", "TRUNCATE ", "ATTACH ", "DETACH "]
    upper_query = cleaned.upper()
    for kw in disallowed_keywords:
        if upper_query.startswith(kw) or f"; {kw}" in upper_query:
            return {
                "success": False,
                "error": f"Write operation '{kw.strip()}' disallowed. Studio operates in read-only mode."
            }

    start_time = time.perf_counter()
    conn = None
    try:
        conn = get_db_connection(db_path)
        cur = conn.cursor()
        cur.execute(cleaned)
        
        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)

        if cur.description is None:
            return {
                "success": True,
                "columns": [],
                "rows": [],
                "row_count": 0,
                "elapsed_ms": elapsed_ms,
                "truncated": False
            }

        columns = [d[0] for d in cur.description]
        rows_raw = cur.fetchmany(max_rows + 1)
        truncated = len(rows_raw) > max_rows
        rows_to_return = rows_raw[:max_rows]
        rows = [list(row) for row in rows_to_return]

        return {
            "success": True,
            "columns": columns,
            "rows": rows,
            "row_count": len(rows),
            "elapsed_ms": elapsed_ms,
            "truncated": truncated,
            "max_rows": max_rows
        }
    except sqlite3.Error as err:
        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
        return {
            "success": False,
            "error": str(err),
            "elapsed_ms": elapsed_ms
        }
    except Exception as ex:
        return {"success": False, "error": f"Unexpected execution error: {str(ex)}"}
    finally:
        if conn:
            conn.close()


class SQLStudioHandler(SimpleHTTPRequestHandler):
    """Custom HTTP handler serving sql_studio.html and providing /api endpoints."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=REPO_ROOT, **kwargs)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path in ("/", "/index.html", "/sql_studio", "/sql_studio.html"):
            self.serve_studio_html()
            return
        elif path == "/api/status":
            self.handle_api_status()
            return
        elif path == "/api/schema":
            self.handle_api_schema()
            return

        super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/query":
            self.handle_api_query()
            return
        
        self.send_response(404)
        self.end_headers()

    def serve_studio_html(self):
        """Serve the sql_studio.html file."""
        if not os.path.exists(HTML_PATH):
            self.send_error(404, "sql_studio.html not found.")
            return

        with open(HTML_PATH, "rb") as f:
            content = f.read()

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.end_headers()
        self.wfile.write(content)

    def handle_api_status(self):
        """Return server and database health status."""
        db_path = DEFAULT_DB_PATH
        exists = os.path.exists(db_path)
        size_mb = round(os.path.getsize(db_path) / (1024 * 1024), 2) if exists else 0

        data = {
            "status": "online",
            "database_exists": exists,
            "database_path": os.path.relpath(db_path, REPO_ROOT),
            "database_size_mb": size_mb,
            "timestamp": time.time(),
            "server_version": "1.0.0"
        }
        self.send_json(data)

    def handle_api_schema(self):
        """Return full introspection of tables, views, columns, and rows."""
        try:
            schema = introspect_schema(DEFAULT_DB_PATH)
            self.send_json({"success": True, "schema": schema})
        except Exception as e:
            self.send_json({"success": False, "error": str(e)}, status=500)

    def handle_api_query(self):
        """Execute query submitted via POST body."""
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode("utf-8")
            payload = json.loads(body)
            query = payload.get("query", "")
            max_rows = payload.get("max_rows", 5000)

            result = execute_sql(query, DEFAULT_DB_PATH, max_rows=max_rows)
            self.send_json(result)
        except json.JSONDecodeError:
            self.send_json({"success": False, "error": "Invalid JSON payload."}, status=400)
        except Exception as ex:
            self.send_json({"success": False, "error": f"Server processing error: {str(ex)}"}, status=500)

    def send_json(self, data, status=200):
        """Helper to send JSON response with CORS headers."""
        encoded = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(encoded)

    def do_OPTIONS(self):
        """Handle pre-flight CORS requests."""
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def log_message(self, format, *args):
        """Silent logging for cleaner terminal output unless error."""
        if args and str(args[1]).startswith(("4", "5")):
            super().log_message(format, *args)


def find_free_port(start_port=8080, max_attempts=50):
    """Find an available port starting from start_port."""
    for port in range(start_port, start_port + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    return start_port


def main():
    parser = argparse.ArgumentParser(description="Irish Car Sales SQL Studio Server")
    parser.add_argument("--port", type=int, default=8080, help="Port to serve on (default: 8080 or next free)")
    parser.add_argument("--host", default="127.0.0.1", help="Host address (default: 127.0.0.1)")
    parser.add_argument("--no-browser", action="store_true", help="Do not automatically open browser")
    args = parser.parse_args()

    ensure_database(DEFAULT_DB_PATH)

    port = find_free_port(args.port)
    server_address = (args.host, port)
    httpd = HTTPServer(server_address, SQLStudioHandler)

    url = f"http://{args.host}:{port}/"
    print("\n" + "=" * 65)
    print(" 🚗 IRISH CAR SALES SQL STUDIO & SCHEMA EXPLORER")
    print("=" * 65)
    print(f" • Local Web Studio:   {url}")
    print(f" • Database:           {os.path.relpath(DEFAULT_DB_PATH, REPO_ROOT)} (SQLite 3 WAL)")
    print(f" • REST API Query:     {url}api/query")
    print(f" • REST API Schema:    {url}api/schema")
    print("=" * 65)
    print(" Press Ctrl+C to stop the studio server.\n")

    if not args.no_browser:
        webbrowser.open(url)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[Studio] Shutting down SQL Studio server. Goodbye!")
        httpd.server_close()


if __name__ == "__main__":
    main()
