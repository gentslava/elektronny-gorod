import json

def is_json(value: str):
    try:
        json.loads(value)
    except ValueError as e:
        return False
    return True
