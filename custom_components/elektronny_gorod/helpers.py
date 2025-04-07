import hashlib
import base64
from datetime import datetime
from collections.abc import Callable


def contains(items: list, condition: Callable) -> bool:
    return any(condition(item) for item in items)


def find(items: list, condition: Callable) -> object:
    for item in items:
        if condition(item):
            return item
    return None


def get_timestamp() -> str:
    return f"{datetime.now().isoformat()[:-3]}Z"


def hash_password(password: str) -> str:
    password_bytes = password.encode("utf-8")
    sha1_hash = hashlib.sha1(password_bytes).digest()
    base64_encoded = base64.b64encode(sha1_hash).decode("utf-8")
    return base64_encoded


def hash_password_timestamp(password: str, timestamp: str) -> str:
    password_bytes = password.encode("utf-8")
    combo = password_bytes + timestamp.encode("utf-8")
    md5_encoded = hashlib.md5(combo).hexdigest()
    return md5_encoded
