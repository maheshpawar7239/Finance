import json
import traceback
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

from auth import decode_token, AuthError


def json_response(handler, status: int, data):
    body = json.dumps(data, indent=2).encode()
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
    handler.send_header("Access-Control-Allow-Methods", "GET, POST, PATCH, DELETE, OPTIONS")
    handler.end_headers()
    handler.wfile.write(body)


def error(handler, status: int, message: str):
    json_response(handler, status, {"error": message})


def parse_body(handler) -> dict:
    length = int(handler.headers.get("Content-Length", 0))
    if length == 0:
        return {}
    raw = handler.rfile.read(length)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def get_current_user(handler) -> dict | None:
    auth_header = handler.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    token = auth_header[7:]
    try:
        return decode_token(token)
    except AuthError:
        return None


def require_auth(handler, *roles):
    """Returns (user, None) on success, or (None, error_sent=True) on failure."""
    user = get_current_user(handler)
    if not user:
        error(handler, 401, "Authentication required. Provide a valid Bearer token.")
        return None, True
    if roles and user.get("role") not in roles:
        error(handler, 403, f"Access denied. Required role(s): {', '.join(roles)}")
        return None, True
    return user, False


class Router:
    def __init__(self):
        self.routes = []

    def add(self, method, pattern, handler_fn):
        self.routes.append((method, pattern, handler_fn))

    def dispatch(self, handler, method, path, query, path_params):
        for route_method, pattern, fn in self.routes:
            if route_method != method:
                continue
            params = self._match(pattern, path)
            if params is not None:
                combined = {**path_params, **params}
                try:
                    fn(handler, combined, query)
                except Exception as e:
                    traceback.print_exc()
                    error(handler, 500, "Internal server error")
                return True
        return False

    def _match(self, pattern: str, path: str) -> dict | None:
        pattern_parts = pattern.strip("/").split("/")
        path_parts = path.strip("/").split("/")
        if len(pattern_parts) != len(path_parts):
            return None
        params = {}
        for pp, vp in zip(pattern_parts, path_parts):
            if pp.startswith("{") and pp.endswith("}"):
                params[pp[1:-1]] = vp
            elif pp != vp:
                return None
        return params
