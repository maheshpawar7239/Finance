#!/usr/bin/env python3
"""
Finance Dashboard Backend
Run: python3 main.py
Default port: 8000
"""

import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

from database import init_db, seed_data
from server import json_response, error, Router
import handlers


# ---------------------------------------------------------------------------
# Route table
# ---------------------------------------------------------------------------

router = Router()

# Auth
router.add("POST", "/auth/login",                    handlers.login)

# Users
router.add("GET",    "/users",                       handlers.list_users)
router.add("POST",   "/users",                       handlers.create_user)
router.add("GET",    "/users/me",                    handlers.get_me)
router.add("GET",    "/users/{user_id}",             handlers.get_user)
router.add("PATCH",  "/users/{user_id}",             handlers.update_user)
router.add("DELETE", "/users/{user_id}",             handlers.deactivate_user)

# Financial Records
router.add("GET",    "/records",                     handlers.list_records)
router.add("POST",   "/records",                     handlers.create_record)
router.add("GET",    "/records/{record_id}",         handlers.get_record)
router.add("PATCH",  "/records/{record_id}",         handlers.update_record)
router.add("DELETE", "/records/{record_id}",         handlers.delete_record)

# Dashboard
router.add("GET", "/dashboard/summary",              handlers.dashboard_summary)
router.add("GET", "/dashboard/by-category",          handlers.dashboard_by_category)
router.add("GET", "/dashboard/trends",               handlers.dashboard_trends)
router.add("GET", "/dashboard/recent",               handlers.dashboard_recent)
router.add("GET", "/dashboard/income-vs-expense",    handlers.dashboard_income_vs_expense)


# ---------------------------------------------------------------------------
# HTTP request handler
# ---------------------------------------------------------------------------

class RequestHandler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        print(f"  {self.command} {self.path} -> {args[1]}")

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PATCH, DELETE, OPTIONS")
        self.end_headers()

    def do_GET(self):
        self._dispatch("GET")

    def do_POST(self):
        self._dispatch("POST")

    def do_PATCH(self):
        self._dispatch("PATCH")

    def do_DELETE(self):
        self._dispatch("DELETE")

    def _dispatch(self, method):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        query = parse_qs(parsed.query)

        if path == "/":
            return json_response(self, 200, {
                "status": "ok",
                "message": "Finance Dashboard Backend is running",
                "docs": "See README.md for API reference",
            })

        matched = router.dispatch(self, method, path, query, {})
        if not matched:
            error(self, 404, f"No route found for {method} {path}")


# ---------------------------------------------------------------------------
# Start
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import os
    port = int(os.getenv("PORT", 8000))

    print("=" * 50)
    print("  Finance Dashboard Backend")
    print("=" * 50)
    print(f"  Initialising database...")
    init_db()
    seed_data()
    print(f"  Server starting on http://localhost:{port}")
    print(f"  Press Ctrl+C to stop")
    print("=" * 50)

    server = HTTPServer(("", port), RequestHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Server stopped.")
