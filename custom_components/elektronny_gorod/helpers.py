import json
import uuid
from collections.abc import Callable

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
    iphone: str = "iPhone15,3",
    ios: str = "iOS 17.1.2",
    app_ver: str = "6.16.5 (build 1)",
    account_id: str = "_",
    operator: str = "1"
) -> str:
    return f"{iphone} | {ios} | ntk | {app_ver} | {account_id} | {operator} | {str(uuid.uuid4()).upper()}"