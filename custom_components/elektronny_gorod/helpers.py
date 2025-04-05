from collections.abc import Callable

def contains(items: list, condition: Callable) -> bool:
    return any(condition(item) for item in items)

def find(items: list, condition: Callable) -> object:
    for item in items:
        if condition(item):
            return item
    return None
