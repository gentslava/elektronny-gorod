import uuid
from random import choice
from .const import (
    APP_VERSION,
    ANDROID_DEVICES,
    ANDROID_OS_VER,
)

class UserAgent:
    def __init__(self) -> None:
        rand_phone = choice(ANDROID_DEVICES)
        self.phone_manufacturer: str = rand_phone["manufacturer"]
        self.phone_model: str = rand_phone["model"]
        self.android_ver: str = ANDROID_OS_VER
        self.app_version: dict = APP_VERSION
        self.account_id: str = ""
        self.operator_id: str | int = "null"
        self.uuid: str = str(uuid.uuid4())
        self.place_id: str = "null"

    def __str__(self):
        manufacturer = self.phone_manufacturer
        model = self.phone_model
        ver = self.android_ver
        app_ver = self.app_version
        account_id = self.account_id
        operator_id = self.operator_id
        uuid = self.uuid
        place_id = self.place_id
        return f"{manufacturer} {model} | Android {ver} | ntk | {app_ver["name"]} ({app_ver["code"]}) | {account_id} | {operator_id} | {uuid} | {place_id}"
