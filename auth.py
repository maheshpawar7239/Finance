import base64
import hashlib
import hmac
import json
import time
import os

SECRET = os.getenv("SECRET_KEY", "dev-secret-do-not-use-in-production")


def _b64_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64_decode(s: str) -> bytes:
    padding = 4 - len(s) % 4
    return base64.urlsafe_b64decode(s + "=" * padding)


def create_token(user_id: str, email: str, role: str, expires_in: int = 86400) -> str:
    header = _b64_encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload = _b64_encode(json.dumps({
        "sub": user_id,
        "email": email,
        "role": role,
        "exp": int(time.time()) + expires_in,
    }).encode())
    sig_input = f"{header}.{payload}".encode()
    signature = _b64_encode(hmac.new(SECRET.encode(), sig_input, hashlib.sha256).digest())
    return f"{header}.{payload}.{signature}"


def decode_token(token: str) -> dict:
    try:
        parts = token.split(".")
        if len(parts) != 3:
            raise ValueError("Malformed token")
        header, payload, signature = parts
        sig_input = f"{header}.{payload}".encode()
        expected = _b64_encode(hmac.new(SECRET.encode(), sig_input, hashlib.sha256).digest())
        if not hmac.compare_digest(expected, signature):
            raise ValueError("Invalid signature")
        data = json.loads(_b64_decode(payload))
        if data.get("exp", 0) < int(time.time()):
            raise ValueError("Token expired")
        return data
    except ValueError as e:
        raise AuthError(str(e))


class AuthError(Exception):
    pass
