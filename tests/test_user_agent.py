"""Эмуляция клиента оператора: что переживает перезагрузку, а что обновляется.

`user_agent` — это то, чем интеграция представляется оператору. Часть его
описывает устройство и обязана быть стабильной, часть описывает приложение
и обязана следовать за нашей константой. Раньше различия не было, и обе
половины восстанавливались из записи целиком.
"""
from __future__ import annotations

from custom_components.elektronny_gorod.const import APP_VERSION
from custom_components.elektronny_gorod.user_agent import UserAgent

# Форма, в которой user_agent лежит в `entry.data` у давно настроенной
# записи: версия приложения такая, какой она была на момент настройки.
_STORED = {
    "phone_manufacturer": "Google",
    "phone_model": "Pixel 7 Pro",
    "android_ver": "16",
    "app_version": {"name": "9.9.0", "code": "90900020"},
    "account_id": "A1",
    "operator_id": "1",
    "uuid": "11111111-2222-3333-4444-555555555555",
    "place_id": "1000000",
}


def test_device_identity_survives_reload() -> None:
    """Телефон остаётся тем же телефоном.

    Модель, `uuid` и `account_id` — это то, по чему оператор узнаёт
    устройство. Смена любого из них выглядела бы как переезд аккаунта на
    новый телефон при каждой перезагрузке Home Assistant.
    """
    agent = UserAgent()
    agent.from_json(_STORED)

    assert agent.phone_manufacturer == "Google"
    assert agent.phone_model == "Pixel 7 Pro"
    assert agent.uuid == _STORED["uuid"]
    assert agent.account_id == "A1"
    assert agent.operator_id == "1"
    assert agent.place_id == "1000000"
    assert agent.android_ver == "16"


def test_app_version_follows_the_constant_not_the_entry() -> None:
    """Поднятая версия приложения доезжает до уже настроенных записей.

    Настоящее приложение обновляется, а телефон под ним остаётся прежним.
    Пока версия читалась из записи, поднятие константы доставалось только
    новым аккаунтам, а остальные навсегда оставались на той версии, при
    которой их настроили, — вопреки ADR-0006.
    """
    agent = UserAgent()
    agent.from_json(_STORED)

    assert agent.app_version == APP_VERSION
    assert agent.app_version != _STORED["app_version"], (
        "фикстура совпала с текущей версией — тест перестал что-либо проверять"
    )
    assert f'{APP_VERSION["name"]} ({APP_VERSION["code"]})' in str(agent)


def test_round_trip_keeps_what_it_should() -> None:
    """`json()` → `from_json()` не теряет и не выдумывает устройство."""
    agent = UserAgent()
    agent.account_id = "A9"
    agent.operator_id = "1"
    agent.place_id = "2000000"
    restored = UserAgent()
    restored.from_json(agent.json())

    assert restored.json() == agent.json()
