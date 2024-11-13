import json
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
