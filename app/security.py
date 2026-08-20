import hashlib
import hmac
import os
import time

from app.config import settings


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200_000)
    return salt.hex() + "$" + dk.hex()


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        salt_hex, hash_hex = stored_hash.split("$")
    except ValueError:
        return False
    salt = bytes.fromhex(salt_hex)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200_000)
    return hmac.compare_digest(dk.hex(), hash_hex)


def _sign(value: str) -> str:
    return hmac.new(settings.SECRET_KEY.encode(), value.encode(), hashlib.sha256).hexdigest()


def create_session_token(user_id: int) -> str:
    """A tiny signed token: '<user_id>.<expiry>.<signature>' — no extra JWT dependency needed."""
    expiry = int(time.time()) + settings.SESSION_MAX_AGE
    payload = f"{user_id}.{expiry}"
    signature = _sign(payload)
    return f"{payload}.{signature}"


def read_session_token(token: str):
    try:
        user_id_str, expiry_str, signature = token.split(".")
        payload = f"{user_id_str}.{expiry_str}"
        if not hmac.compare_digest(_sign(payload), signature):
            return None
        if int(expiry_str) < int(time.time()):
            return None
        return int(user_id_str)
    except (ValueError, AttributeError):
        return None
