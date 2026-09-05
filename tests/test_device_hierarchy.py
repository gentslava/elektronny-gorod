"""Устройства интеграции сгруппированы под устройством адреса (place).

Плоский список камер и замков — регрессия относительно 4.0: HA 2026.8 объявил
`via_device` устаревшим, а 2026.9 убрал его из `DeviceInfo`; связь теперь
задаётся готовым `via_device_id`.

Фикстура намеренно шире одного домофона: два адреса ловят привязку к чужому
месту, а вторая точка входа без `externalCameraId` — единственная конфигурация,
где устройство создаёт только `lock.py`. С одним адресом и одной точкой входа
любая частичная регрессия маскируется: все платформы пишут в одно устройство,
а пропуск `via_device_id` ядро трактует как «не менять».

Ключевой параметр — `with_account_history`. Когда в записи есть `account_id` и
`subscriber_id`, `event.py` заводит сущность истории аккаунта, которая попутно
создаёт устройство адреса, и до-фиксовый код выглядит здоровым. Без этих ключей
адрес не создаёт никто: там и виден плоский список из A-100. Прогон на коде до
фикса даёт 5 падений на 2026.8.1 и 6 на 2026.9 именно в этой конфигурации —
и ноль в полной.
"""

from __future__ import annotations

import json
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo

from custom_components.elektronny_gorod.const import DOMAIN
from custom_components.elektronny_gorod.device import linked_to_place, place_device_id

_PLACE_A = "1001"
_PLACE_B = "1002"
_INTERCOM_CAMERA = "111"
_AC_A = 2001
_AC_B = 2002
_ENTRANCE_A = 3001
# Вторая точка входа того же домофона без камеры: устройство для неё создаёт
# только `lock.py` — остальные платформы сюда не доходят.
_ENTRANCE_A2 = 3002
_ENTRANCE_B = 3009


def _entry(*, with_account_history: bool = True) -> MockConfigEntry:
    from custom_components.elektronny_gorod.const import (
        CONF_ACCESS_TOKEN,
        CONF_OPERATOR_ID,
        CONF_REFRESH_TOKEN,
        CONF_USER_AGENT,
    )
    from custom_components.elektronny_gorod.user_agent import UserAgent

    ua = UserAgent()
    ua.operator_id = "1"
    return MockConfigEntry(
        domain=DOMAIN,
        version=3,
        unique_id="test_unique_subscriber_S1",
        title="Test",
        data={
            CONF_ACCESS_TOKEN: "T1",
            CONF_REFRESH_TOKEN: "R1",
            CONF_OPERATOR_ID: "1",
            CONF_USER_AGENT: json.dumps(ua.json()),
            # Без них `event.py` не создаёт сущность истории аккаунта — а вместе
            # с ней исчезает единственный побочный создатель устройства адреса.
            **(
                {"account_id": "A1", "subscriber_id": "S1"}
                if with_account_history
                else {}
            ),
            "use_go2rtc": False,
        },
    )


def _access_controls(place_id: str) -> list[dict]:
    if place_id == _PLACE_A:
        return [
            {
                "id": _AC_A,
                "name": "Домофон",
                "entrances": [
                    {
                        "id": _ENTRANCE_A,
                        "name": "Подъезд",
                        "externalCameraId": int(_INTERCOM_CAMERA),
                        "allowOpen": True,
                    },
                    {"id": _ENTRANCE_A2, "name": "Калитка", "allowOpen": True},
                ],
            }
        ]
    return [
        {
            "id": _AC_B,
            "name": "Домофон",
            "entrances": [
                {"id": _ENTRANCE_B, "name": "Подъезд", "allowOpen": True}
            ],
        }
    ]


@pytest.fixture
def mock_api():
    from custom_components.elektronny_gorod.api import HistoryPage

    with patch(
        "custom_components.elektronny_gorod.coordinator.ElektronnyGorodAPI"
    ) as mock_cls:
        instance = mock_cls.return_value
        instance.http = AsyncMock()
        instance.http.user_agent = MagicMock()
        instance.query_places = AsyncMock(
            return_value=[
                {
                    "subscriber": {"id": "S1", "accountId": "A1", "name": "Test"},
                    "place": {"id": _PLACE_A, "address": "ул. Тестовая 1"},
                },
                {
                    "subscriber": {"id": "S2", "accountId": "A1", "name": "Test"},
                    "place": {"id": _PLACE_B, "address": "ул. Тестовая 2"},
                },
            ]
        )
        instance.query_balance = AsyncMock(return_value={})
        instance.query_access_controls = AsyncMock(side_effect=_access_controls)
        instance.query_cameras = AsyncMock(return_value=[])
        instance.query_public_cameras = AsyncMock(return_value=[])
        instance.query_screens_settings = AsyncMock(return_value={"screens": []})
        instance.query_dnd_settings = AsyncMock(return_value=[])
        instance.query_events = AsyncMock(
            return_value=HistoryPage(events=(), number=0, last=True)
        )
        yield mock_cls


async def _setup(hass, *, with_account_history: bool = True) -> MockConfigEntry:
    entry = _entry(with_account_history=with_account_history)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def _device(hass, entry, uid: str):
    return dr.async_get(hass).async_get_device_by_identifier(
        (DOMAIN, uid), entry.entry_id
    )


def _entrance_uid(place_id: str, ac_id: int, entrance_id: int) -> str:
    return f"entrance_{place_id}_{ac_id}_{entrance_id}"


@pytest.mark.parametrize("with_account_history", [True, False])
async def test_place_devices_created(hass, mock_api, with_account_history) -> None:
    """Каждый адрес существует как отдельное устройство — родитель группы."""
    entry = await _setup(hass, with_account_history=with_account_history)

    for place_id in (_PLACE_A, _PLACE_B):
        place = _device(hass, entry, f"place_{place_id}")
        assert place is not None, place_id
        assert place.primary_config_entry == entry.entry_id


@pytest.mark.parametrize("with_account_history", [True, False])
async def test_entrances_linked_to_their_own_place(
    hass, mock_api, with_account_history
) -> None:
    """Каждая точка входа висит под своим адресом, а не под первым попавшимся."""
    entry = await _setup(hass, with_account_history=with_account_history)

    expected = {
        _entrance_uid(_PLACE_A, _AC_A, _ENTRANCE_A): _PLACE_A,
        _entrance_uid(_PLACE_A, _AC_A, _ENTRANCE_A2): _PLACE_A,
        _entrance_uid(_PLACE_B, _AC_B, _ENTRANCE_B): _PLACE_B,
    }
    for uid, place_id in expected.items():
        entrance = _device(hass, entry, uid)
        place = _device(hass, entry, f"place_{place_id}")
        assert entrance is not None, uid
        assert entrance.via_device_id == place.id, (
            f"{uid} привязан не к своему адресу"
        )


async def test_cameraless_entrance_linked(hass, mock_api) -> None:
    """Точку входа без камеры создаёт только `lock.py` — связь всё равно есть."""
    entry = await _setup(hass, with_account_history=False)

    entrance = _device(hass, entry, _entrance_uid(_PLACE_A, _AC_A, _ENTRANCE_A2))
    place = _device(hass, entry, f"place_{_PLACE_A}")

    assert place is not None, "устройство адреса не создано"
    assert entrance is not None
    assert entrance.via_device_id == place.id


@pytest.mark.parametrize("with_account_history", [True, False])
async def test_no_orphan_entrance_devices(
    hass, mock_api, with_account_history
) -> None:
    """Ни одна точка входа не остаётся без адреса.

    Только `entrance_*`: личные и городские камеры (`camera_*`) — намеренно
    самостоятельные устройства, у них родителя нет и не было.
    """
    entry = await _setup(hass, with_account_history=with_account_history)

    registry = dr.async_get(hass)
    devices = dr.async_entries_for_config_entry(registry, entry.entry_id)
    orphans = [
        device.name
        for device in devices
        if any(ident[1].startswith("entrance_") for ident in device.identifiers)
        and device.via_device_id is None
    ]

    assert not orphans, f"точки входа без привязки к адресу: {orphans}"


async def test_flat_device_gets_linked_on_restart(hass, mock_api) -> None:
    """Установки, обновляющиеся с плоской версии, получают связь при старте.

    Отдельная миграция не нужна: `async_get_or_create` дописывает
    `via_device_id` существующему устройству по тем же identifiers.
    """
    entry = _entry(with_account_history=False)
    entry.add_to_hass(hass)

    registry = dr.async_get(hass)
    flat = registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, _entrance_uid(_PLACE_A, _AC_A, _ENTRANCE_A))},
        name="Домофон",
    )
    assert flat.via_device_id is None

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    place = _device(hass, entry, f"place_{_PLACE_A}")
    relinked = _device(hass, entry, _entrance_uid(_PLACE_A, _AC_A, _ENTRANCE_A))

    assert relinked.id == flat.id, "устройство пересоздано вместо обновления"
    assert relinked.via_device_id == place.id


async def test_place_device_id_scoped_to_entry(hass, mock_api) -> None:
    """Адрес чужой записи не виден: identifiers уникальны только внутри entry."""
    entry = await _setup(hass)
    other = MockConfigEntry(domain=DOMAIN, version=3, unique_id="other")
    other.add_to_hass(hass)

    assert place_device_id(hass, entry.entry_id, _PLACE_A) is not None
    assert place_device_id(hass, other.entry_id, _PLACE_A) is None


async def test_place_device_id_absent_place(hass, mock_api) -> None:
    """Неизвестный адрес — `None`, а не исключение."""
    entry = await _setup(hass)

    assert place_device_id(hass, entry.entry_id, "9999") is None
    assert place_device_id(hass, entry.entry_id, "") is None


def test_linked_to_place_omits_key_when_unknown() -> None:
    """Без известного адреса ключ отсутствует, а не равен None.

    Явный `None` ядро понимает как «отвязать» и стёр бы существующую связь.
    """
    info = linked_to_place(DeviceInfo(identifiers={(DOMAIN, "x")}), None)

    assert "via_device_id" not in info

    linked = linked_to_place(DeviceInfo(identifiers={(DOMAIN, "x")}), "abc")

    assert linked["via_device_id"] == "abc"


async def test_malformed_place_does_not_create_device(hass, mock_api) -> None:
    """Место без id пропускается, а не порождает мусорное устройство."""
    from custom_components.elektronny_gorod.device import async_register_place_devices

    entry = await _setup(hass)
    async_register_place_devices(
        hass, entry, {"places": [{"place": {"address": "без id"}}, {}]}
    )

    assert _device(hass, entry, "place_") is None


async def test_setup_does_not_use_deprecated_via_device(hass, mock_api, caplog) -> None:
    """Ни одна платформа не адресует родителя устаревшим `via_device`.

    Это и есть исходный отказ A-100: ядро сообщает об устаревшем параметре, а
    когда фрейм интеграции не определяется — поднимает сообщение до
    `RuntimeError`, и сущность не создаётся вовсе. В тестовом харнессе фрейм
    определяется, поэтому остаётся только предупреждение — по нему и ловим.

    Срабатывает на 2026.9+, где ядро сообщает об устаревшем параметре. На
    минимуме 2026.8.1 `via_device` — ещё штатный аргумент без отчёта, там и
    отказа нет.

    Дополняет pyright не по версиям, а по способу обнаружения: тот видит
    только литеральный `via_device=` в типизированном коде, а проверка ниже
    не зависит от того, как собран `DeviceInfo`. Зеркально: если `via_device`
    добавить рядом с `via_device_id`, ядро упадёт раньше отчёта, и эта
    проверка промолчит — там сработает pyright.
    """
    caplog.set_level(logging.WARNING)

    await _setup(hass, with_account_history=False)

    deprecated = [
        record.getMessage()
        for record in caplog.records
        if "via_device" in record.getMessage()
        and "deprecated" in record.getMessage().lower()
    ]

    assert not deprecated, deprecated
