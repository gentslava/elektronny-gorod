import hashlib
import base64
from collections.abc import Callable


def contains(items: list, condition: Callable) -> bool:
    return any(condition(item) for item in items)


def find(items: list, condition: Callable) -> dict | None:
    for item in items:
        if condition(item):
            return item
    return None


def append_unique(target_list, new_dict):
    existing_ids = [d['id'] for d in target_list]

    if new_dict['id'] not in existing_ids:
        target_list.append(new_dict)


def dedupe_by_id(items: list[dict]) -> list[dict]:
    seen_ids = set()
    unique_by_id = []
    for item in items:
        item_id = item.get("id")
        if item_id and item_id not in seen_ids:
            unique_by_id.append(item)
            seen_ids.add(item_id)
    return unique_by_id


def hash_password(password: str) -> str:
    password_bytes = password.encode("utf-8")
    sha1_hash = hashlib.sha1(password_bytes).digest()
    base64_encoded = base64.b64encode(sha1_hash).decode("utf-8")
    return base64_encoded


def hash_password_timestamp(login: str, password: str, time: str) -> str:
    prefix = "DigitalHomeNTKpassword"
    secret = "789sdgHJs678wertv34712376"
    raw_string = f"{prefix}{login}{password}{time}{secret}"
    md5_encoded = hashlib.md5(raw_string.encode()).hexdigest()
    return md5_encoded
