import json
import uuid
from random import choice
from collections.abc import Callable
from .const import APP_VERSION, iPHONE_iOS_CODES

def is_json(value: str) -> bool:
    try:
        json.loads(value)
    except ValueError as e:
        return False
    return True

def contains(items: list, condition: Callable) -> bool:
    return any(condition(item) for item in items)

def find(items: list, condition: Callable) -> object:
    for item in items:
        if condition(item):
            return item
    return None

def generate_user_agent(
    iphone: str | None = None,
    ios: str | None = None,
    app_ver: str = APP_VERSION,
    account_id: str = "_",
    operator: str = "1"
) -> str:
    iphone_code = iphone
    ios_code = ios
    if iphone is None or ios is None:
        rand_iphone = choice(iPHONE_iOS_CODES)
        iphone_code = choice(rand_iphone["code"])
        ios_code = choice(rand_iphone["os"])
    return f"{iphone_code} | {ios_code} | ntk | {app_ver} | {account_id} | {operator} | {str(uuid.uuid4()).upper()}"
