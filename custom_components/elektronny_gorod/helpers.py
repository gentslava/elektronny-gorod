import json
import uuid

def is_json(value: str):
    try:
        json.loads(value)
    except ValueError as e:
        return False
    return True

def contains(list, condition):
    return any(condition(item) for item in list)

def find(list, condition):
    for item in list:
        if condition(item):
            return item
    return None

def generate_user_agent(
    iphone: str = "iPhone15,3",
    ios: str = "iOS 17.1.2",
    app_ver: str = "6.16.5 (build 1)",
    account_id: str = "_",
    operator: str = "1"
):
    return f"{iphone} | {ios} | ntk | {app_ver} | {account_id} | {operator} | {str(uuid.uuid4()).upper()}"