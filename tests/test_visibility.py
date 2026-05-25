"""Tests for user-app visibility (hidden) flag from `/settings/screens`.

PR #35 (commit cd8a54c): при `hidden=True` от API оператора для конкретной
public-camera или access_controls.entrance — entity по умолчанию
**disabled** в HA через `_attr_entity_registry_enabled_default = False`.

Эти два теста — **baseline** до fix'а:

| Тест | Ожидание | Что проверяет |
|---|---|---|
| `test_camera_with_hidden_in_api_disabled_on_first_add` | PASS | Первая регистрация — `_attr_entity_registry_enabled_default` применяется (HA не знает entity → берёт default). |
| `test_camera_with_hidden_in_api_NOT_disabled_on_readd` | FAIL до fix | Re-add — HA восстанавливает entity из `deleted_entities` с прежним `disabled_by=None`. Текущий код это **не** обрабатывает. |

Если оба FAIL — first-add тоже не работает, bug шире нашей гипотезы.
Если оба PASS — bug где-то ещё (не в этом месте).
"""
from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from custom_components.elektronny_gorod.const import (
    CONF_ACCESS_TOKEN,
    CONF_OPERATOR_ID,
    CONF_REFRESH_TOKEN,
    CONF_USER_AGENT,
    DOMAIN,
)
from custom_components.elektronny_gorod.user_agent import UserAgent

# ---------------------------------------------------------------------------- #
# Test fixtures                                                                #
# ---------------------------------------------------------------------------- #

# id-шки для двух public-камер: одна видимая, одна hidden пользователем.
VISIBLE_CAMERA_ID = "111"
HIDDEN_CAMERA_ID = "222"
PLACE_ID = "P1"


def _make_screens_response() -> dict[str, Any]:
    """`/settings/screens` ответ: 1 visible + 1 hidden public-камера."""
    return {
        "screens": [
            {
                "type": "PUBLIC_CAMERAS",
                "entities": [
                    {"id": int(VISIBLE_CAMERA_ID), "type": "PUBLIC_CAMERA", "order": 0},
                ],
                "hidden": [
                    {"id": int(HIDDEN_CAMERA_ID), "type": "PUBLIC_CAMERA"},
                ],
            },
            {
                "type": "ACCESS_CONTROLS",
                "entities": [],
                "hidden": [],
            },
        ]
    }


def _make_places_response() -> list[dict[str, Any]]:
    """`query_places()` — одна subscriber_place со вложенным place."""
    return [
        {
            "subscriber": {"id": "S1", "accountId": "A1", "name": "Test"},
            "place": {"id": PLACE_ID, "address": "addr"},
        }
    ]


def _make_public_cameras_response() -> list[dict[str, Any]]:
    """`query_public_cameras()` — две камеры, обе видны API, hidden решается через /settings/screens."""
    return [
        {"externalCameraId": VISIBLE_CAMERA_ID, "name": "Двор"},
        {"externalCameraId": HIDDEN_CAMERA_ID, "name": "Скрытая"},
    ]


@pytest.fixture
def mock_api_class():
    """Заменить ElektronnyGorodAPI на mock, не трогающий сеть.

    Mock возвращает фиксированные значения для всех методов, которые
    coordinator использует во время `_async_update_data`. Все остальные
    методы AsyncMock'аются по умолчанию.
    """
    with patch(
        "custom_components.elektronny_gorod.coordinator.ElektronnyGorodAPI"
    ) as mock_cls:
        instance = mock_cls.return_value

        # http.user_agent.place_id — coordinator пишет туда string id.
        # Создаём вложенный mock-граф: api.http.user_agent.place_id = setter ok.
        instance.http = AsyncMock()
        instance.http.user_agent = AsyncMock()  # имеет writable .place_id

        instance.query_places = AsyncMock(return_value=_make_places_response())
        instance.query_balance = AsyncMock(return_value={})
        instance.query_access_controls = AsyncMock(return_value=[])  # нет домофонов
        instance.query_cameras = AsyncMock(return_value=[])  # нет place-cameras
        instance.query_public_cameras = AsyncMock(
            return_value=_make_public_cameras_response()
        )
        instance.query_screens_settings = AsyncMock(
            return_value=_make_screens_response()
        )

        yield mock_cls


def _make_config_entry() -> MockConfigEntry:
    """Создать ConfigEntry v3 с минимальным data для bootstrap coordinator."""
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
            "account_id": "A1",
            "subscriber_id": "S1",
            "use_go2rtc": False,
            "go2rtc_base_url": "http://127.0.0.1:1984",
            "go2rtc_rtsp_host": "127.0.0.1",
        },
    )


# ---------------------------------------------------------------------------- #
# Test A — first add (baseline для подтверждения теории)                       #
# ---------------------------------------------------------------------------- #


async def test_camera_with_hidden_in_api_disabled_on_first_add(
    hass: HomeAssistant, mock_api_class
):
    """При первом добавлении entry — camera с `hidden=True` в API получает
    `disabled_by = RegistryEntryDisabler.INTEGRATION`.

    Это работает потому, что HA не знает про эту entity → честно берёт
    `_attr_entity_registry_enabled_default = False` из __init__.
    """
    entry = _make_config_entry()
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    entries = er.async_entries_for_config_entry(registry, entry.entry_id)
    # Должны увидеть две camera entity (по одной на VISIBLE / HIDDEN id).
    camera_entries = {
        e.unique_id: e for e in entries if e.domain == "camera"
    }

    visible_uid = f"{DOMAIN}_camera_{VISIBLE_CAMERA_ID}"
    hidden_uid = f"{DOMAIN}_camera_{HIDDEN_CAMERA_ID}"

    assert visible_uid in camera_entries, (
        f"Visible camera entity not registered. Found: {list(camera_entries)}"
    )
    assert hidden_uid in camera_entries, (
        f"Hidden camera entity not registered. Found: {list(camera_entries)}"
    )

    assert camera_entries[visible_uid].disabled_by is None, (
        "Visible camera должна быть enabled (disabled_by is None)"
    )
    assert (
        camera_entries[hidden_uid].disabled_by
        == er.RegistryEntryDisabler.INTEGRATION
    ), (
        "Hidden camera должна быть disabled_by=INTEGRATION на первой регистрации, "
        f"got: {camera_entries[hidden_uid].disabled_by!r}"
    )


# ---------------------------------------------------------------------------- #
# Test B — re-add (regression baseline, ожидаем FAIL до fix'а)                 #
# ---------------------------------------------------------------------------- #


async def test_camera_with_hidden_in_api_NOT_disabled_on_readd(
    hass: HomeAssistant, mock_api_class
):
    """REGRESSION: при удалении и повторном добавлении entry — hidden state
    из API игнорируется.

    Known limitation HA core: при `config_entries.async_remove()` registry
    entries не удаляются сразу, а сохраняются в `deleted_entities` на ~30
    дней. При re-add (с тем же unique_id) HA восстанавливает старую запись
    с её прежним `disabled_by` (None если был enabled).

    `_attr_entity_registry_enabled_default` применяется только на ПЕРВОЙ
    регистрации — после восстановления из `deleted_entities` он
    игнорируется.

    Этот тест должен FAIL до fix'а — что подтверждает баг (regression
    baseline). После fix'а — должен PASS.
    """
    # ── Шаг 1: первая установка ────────────────────────────────────────────
    entry = _make_config_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    hidden_uid = f"{DOMAIN}_camera_{HIDDEN_CAMERA_ID}"
    entry_after_first = registry.async_get_entity_id("camera", DOMAIN, hidden_uid)
    assert entry_after_first is not None, "Hidden camera не зарегистрирована на первом add"
    assert (
        registry.async_get(entry_after_first).disabled_by
        == er.RegistryEntryDisabler.INTEGRATION
    ), "Baseline: hidden camera должна быть disabled на первой регистрации"

    # ── Шаг 2: эмулируем что пользователь руками enable'нул entity ─────────
    # (Без этого тест проходил бы даже без fix'а — disabled_by сохранился
    # бы из первой регистрации и совпал бы с ожиданием INTEGRATION.)
    registry.async_update_entity(entry_after_first, disabled_by=None)
    assert registry.async_get(entry_after_first).disabled_by is None

    # ── Шаг 3: remove config_entry → entity уходит в deleted_entities ──────
    assert await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()

    # После remove entity исчезает из active registry, но `unique_id` остаётся
    # в `deleted_entities` (HA core implementation detail).
    assert registry.async_get_entity_id("camera", DOMAIN, hidden_uid) is None

    # ── Шаг 4: re-add тот же entry с теми же данными ───────────────────────
    entry2 = _make_config_entry()
    entry2.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry2.entry_id)
    await hass.async_block_till_done()

    # ── Шаг 5: проверяем, что hidden camera ВСЁ ЕЩЁ disabled ──────────────
    # Здесь bug проявится: HA восстановит entity из deleted_entities
    # с её последним `disabled_by=None`, и `_attr_entity_registry_enabled_default`
    # из __init__ будет проигнорирован.
    entry_after_readd = registry.async_get_entity_id("camera", DOMAIN, hidden_uid)
    assert entry_after_readd is not None, (
        "Hidden camera должна быть зарегистрирована после re-add"
    )
    actual_disabled_by = registry.async_get(entry_after_readd).disabled_by
    assert actual_disabled_by == er.RegistryEntryDisabler.INTEGRATION, (
        "После re-add hidden camera должна быть снова disabled_by=INTEGRATION "
        f"(чтобы уважать user app preference из /settings/screens), "
        f"но got: {actual_disabled_by!r}. "
        "Это known limitation HA core: deleted_entities сохраняют user "
        "disabled_by override, и _attr_entity_registry_enabled_default "
        "не применяется на re-register. См. PR #35 follow-up fix."
    )
