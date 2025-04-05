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
        self.operator_id: str = "null"
        self.uuid: str = str(uuid.uuid4())
        self.place_id: str = "null"

    def json(self) -> dict:
        return {
            "phone_manufacturer": self.phone_manufacturer,
            "phone_model": self.phone_model,
            "android_ver": self.android_ver,
            "app_version": self.app_version,
            "account_id": self.account_id,
            "operator_id": self.operator_id,
            "uuid": self.uuid,
            "place_id": self.place_id,
        }

    def from_json(self, value: dict) -> None:
        self.phone_manufacturer: str = value["phone_manufacturer"]
        self.phone_model: str = value["phone_model"]
        self.android_ver: str = value["android_ver"]
        self.app_version: dict = value["app_version"]
        self.account_id: str = value["account_id"]
        self.operator_id: str = value["operator_id"]
        self.uuid: str = value["uuid"]
        self.place_id: str = value["place_id"]

    def __str__(self):
        _phone_manufacturer = self.phone_manufacturer
        _phone_model = self.phone_model
        _android_ver = self.android_ver
        _app_version = self.app_version
        _account_id = self.account_id
        _operator_id = self.operator_id
        _uuid = self.uuid
        _place_id = self.place_id
        return f"{_phone_manufacturer} {_phone_model} | Android {_android_ver} | ntk | {_app_version["name"]} ({_app_version["code"]}) | {_account_id} | {_operator_id} | {_uuid} | {_place_id}"
