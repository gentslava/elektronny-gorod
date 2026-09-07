"""Сборка камер и замков из ответа оператора — формы, которые редко видно.

Домофон без подъездов и камера, привязанная к месту, а не к домофону,
встречаются у реальных абонентов, но в тестовых данных до сих пор не
попадались. Ошибка здесь не падает, а тихо теряет устройство: камеры нет в
списке — и человек не понимает, почему она есть в приложении и нет в Home
Assistant.
"""
from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.core import HomeAssistant

from test_operator_failures import _make_config_entry


def _coordinator(hass: HomeAssistant, entry, api: MagicMock):
    from custom_components.elektronny_gorod.coordinator import (
        ElektronnyGorodUpdateCoordinator,
    )

    with patch(
        "custom_components.elektronny_gorod.coordinator.ElektronnyGorodAPI",
        return_value=api,
    ):
        return ElektronnyGorodUpdateCoordinator(hass, entry=entry)


def _api(**overrides) -> MagicMock:
    api = MagicMock()
    api.http = AsyncMock()
    api.http.user_agent = AsyncMock()
    api.query_places = AsyncMock(return_value=[{
        "subscriber": {"id": "S1", "accountId": "A1", "name": "Test"},
        "place": {"id": "1000000", "address": "addr"},
    }])
    api.query_screens_settings = AsyncMock(return_value={})
    api.query_access_controls = AsyncMock(return_value=[])
    api.query_cameras = AsyncMock(return_value=[])
    api.query_public_cameras = AsyncMock(return_value=[])
    api.query_dnd_settings = AsyncMock(return_value=[])
    api.query_balance = AsyncMock(return_value={})
    for key, value in overrides.items():
        setattr(api, key, AsyncMock(return_value=value))
    return api


async def test_intercom_without_entrances_still_gives_a_camera_and_a_lock(
    hass: HomeAssistant,
) -> None:
    """Домофон без списка подъездов — сам себе подъезд.

    Такой домофон обслуживает одну дверь, и оператор не присылает `entrances`
    вовсе. Пропустить эту форму значит потерять и камеру, и кнопку открытия.
    """
    entry = _make_config_entry()
    entry.add_to_hass(hass)
    api = _api(query_access_controls=[{
        "id": "2000",
        "name": "Калитка",
        "externalCameraId": "CAM-GATE",
        "allowOpen": True,
    }])

    data = await _coordinator(hass, entry, api)._async_update_data()

    assert [c["id"] for c in data["cameras"]] == ["CAM-GATE"]
    assert len(data["locks"]) == 1
    assert data["locks"][0]["access_control_id"] == "2000"


async def test_place_camera_is_taken_by_its_external_id(
    hass: HomeAssistant,
) -> None:
    """Камера места опознаётся по внешнему id, а не по внутреннему.

    Идентификаторы у оператора двух видов, и поток отдаётся по внешнему:
    перепутать их значит показать чёрный прямоугольник.
    """
    entry = _make_config_entry()
    entry.add_to_hass(hass)
    api = _api(query_cameras=[
        {"id": "internal", "externalCameraId": "CAM-YARD", "name": "Двор"},
    ])

    data = await _coordinator(hass, entry, api)._async_update_data()

    assert [c["id"] for c in data["cameras"]] == ["CAM-YARD"]


async def test_broken_lock_data_does_not_take_the_cameras_down(
    hass: HomeAssistant, caplog
) -> None:
    """Отказ на сборке замков не уносит с собой камеры того же адреса.

    Частичные данные лучше пустых: камеры продолжают работать, а о пропаже
    замков сказано один раз.
    """
    entry = _make_config_entry()
    entry.add_to_hass(hass)
    api = _api(query_access_controls=[{
        "id": "2000",
        "name": "Калитка",
        "externalCameraId": "CAM-GATE",
    }])
    coordinator = _coordinator(hass, entry, api)

    with patch.object(
        coordinator,
        "_collect_locks_for_place",
        side_effect=ValueError("форма ответа изменилась"),
    ), caplog.at_level(logging.INFO):
        data = await coordinator._async_update_data()
        await coordinator._async_update_data()

    assert [c["id"] for c in data["cameras"]] == ["CAM-GATE"]
    assert data["locks"] == []
    complaints = [r for r in caplog.records if "Замки недоступны" in r.getMessage()]
    assert len(complaints) == 1, "жалоба повторяется на каждом цикле"
