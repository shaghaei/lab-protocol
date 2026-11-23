"""Passwords and the session cookie, using only the standard library.

Passwords are stored as salted PBKDF2-SHA256 hashes. The session cookie holds
which courses this browser may open and in which role ("class" or "teacher");
it is signed with HMAC so it cannot be edited by hand.
"""
import base64
import hashlib
import hmac
import json
import os
import secrets
from pathlib import Path

ITERATIONS = 200_000
COOKIE = "lab_session"
MIN_PASSWORD = 6
KEY_PATH = Path(__file__).resolve().parent.parent / "data" / "secret.key"


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERATIONS)
    return f"pbkdf2${ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, iterations, salt, digest = stored.split("$")
    except ValueError:
        return False
    test = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(iterations))
    return hmac.compare_digest(test.hex(), digest)


def secret_key() -> bytes:
    env = os.environ.get("LAB_SECRET")
    if env:
        return env.encode()
    KEY_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not KEY_PATH.exists():
        KEY_PATH.write_text(secrets.token_hex(32))
    return KEY_PATH.read_text().strip().encode()


def sign(data: dict) -> str:
    payload = base64.urlsafe_b64encode(json.dumps(data, sort_keys=True).encode()).decode()
    mac = hmac.new(secret_key(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{mac}"


def unsign(token: str | None) -> dict:
    if not token or "." not in token:
        return {}
    payload, mac = token.rsplit(".", 1)
    expected = hmac.new(secret_key(), payload.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(mac, expected):
        return {}
    try:
        data = json.loads(base64.urlsafe_b64decode(payload.encode()))
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def access(request) -> dict:
    """{course_code: role} for this browser."""
    return unsign(request.cookies.get(COOKIE))


def role_in(request, code: str) -> str | None:
    return access(request).get(code)


def grant(response, request, code: str, role: str) -> None:
    data = access(request)
    if data.get(code) != "teacher":          # never downgrade a teacher
        data[code] = role
    response.set_cookie(COOKIE, sign(data), httponly=True, samesite="lax", max_age=60 * 60 * 24 * 30)


def revoke(response, request, code: str) -> None:
    data = access(request)
    data.pop(code, None)
    response.set_cookie(COOKIE, sign(data), httponly=True, samesite="lax", max_age=60 * 60 * 24 * 30)
