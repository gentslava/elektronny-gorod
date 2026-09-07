"""Тесты сущности замка (домофона).

До этого файла `lock.py` не был покрыт ничем: ни действия, ни атрибуты.
Именно поэтому незамеченной прожила кнопка «Закрыть», которая молча ничего
не делала.
"""
from __future__ import annotations

import json
from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.components.lock import LockEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from custom_components.elektronny_gorod.const import (
    CONF_ACCESS_TOKEN,
    CONF_OPERATOR_ID,
    CONF_REFRESH_TOKEN,
    CONF_USER_AGENT,
    DOMAIN,
)
from custom_components.elektronny_gorod.entity_migration import lock_unique_id
from custom_components.elektronny_gorod.user_agent import UserAgent

PLACE_ID = "1000000"
AC_ID = "2000"
ENTRANCE_ID = "3000"


def _access_controls() -> list[dict[str, Any]]:
    return [{
        "id": AC_ID,
        "name": "Intercom",
        "entrances": [{
            "id": ENTRANCE_ID,
            "name": "Entrance 1",
            "allowOpen": True,
        }],
    }]


@pytest.fixture
def mock_api():
    """API mock: одно место с одним замком."""
    with patch(
        "custom_components.elektronny_gorod.coordinator.ElektronnyGorodAPI"
    ) as mock_cls:
        instance = mock_cls.return_value
        instance.http = AsyncMock()
        instance.http.user_agent = AsyncMock()
        instance.query_places = AsyncMock(return_value=[{
            "subscriber": {"id": "S1", "accountId": "A1", "name": "Test"},
            "place": {"id": PLACE_ID, "address": "addr"},
        }])
        instance.query_access_controls = AsyncMock(return_value=_access_controls())
        instance.query_cameras = AsyncMock(return_value=[])
        instance.query_public_cameras = AsyncMock(return_value=[])
        instance.query_screens_settings = AsyncMock(return_value={})
        instance.query_dnd_settings = AsyncMock(return_value=[])
        instance.query_balance = AsyncMock(return_value=None)
        instance.open_lock = AsyncMock()
        yield instance


def _make_config_entry() -> MockConfigEntry:
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


async def _setup_lock(hass: HomeAssistant) -> str:
    entry = _make_config_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    eid = registry.async_get_entity_id(
        "lock", DOMAIN, lock_unique_id(PLACE_ID, AC_ID, ENTRANCE_ID)
    )
    assert eid is not None, "замок не создан"
    return eid


async def test_single_control_for_a_single_action(hass: HomeAssistant, mock_api):
    """Домофон не объявляет «Открыть»: физическое действие у него одно.

    В домене `lock` это отдельная возможность «отпустить защёлку», но у
    домофона она совпадает с «отпереть» — дверь человек открывает рукой.
    Объявление добавило бы в карточку вторую кнопку для того же вызова.
    """
    eid = await _setup_lock(hass)
    state = hass.states.get(eid)

    assert not LockEntityFeature(state.attributes["supported_features"] or 0)


async def test_unlock_still_opens_the_door(hass: HomeAssistant, mock_api):
    """`lock.unlock` работает по-прежнему — автоматизации зовут его."""
    eid = await _setup_lock(hass)

    await hass.services.async_call(
        "lock", "unlock", {"entity_id": eid}, blocking=True
    )

    mock_api.open_lock.assert_awaited_once_with(PLACE_ID, AC_ID, ENTRANCE_ID)


async def test_lock_refuses_with_a_reason(hass: HomeAssistant, mock_api):
    """Запереть домофон нельзя, и он об этом говорит.

    Раньше метод молча выставлял `LOCKED` и писал в лог: со стороны
    пользователя кнопка просто ничего не делала. Оператора при этом не
    трогаем — запирает защёлку само железо.
    """
    eid = await _setup_lock(hass)

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            "lock", "lock", {"entity_id": eid}, blocking=True
        )

    assert err.value.translation_key == "cannot_lock"
    assert mock_api.open_lock.await_count == 0


async def test_attributes_are_snake_case_and_typed(hass: HomeAssistant, mock_api):
    """Ключи snake_case, `openable` булев, имена переводятся.

    Строка `"False"` истинна в шаблоне, поэтому проверка `openable` раньше
    срабатывала всегда.
    """
    import pathlib
    import re

    eid = await _setup_lock(hass)
    attrs = hass.states.get(eid).attributes

    assert attrs["place_id"] == PLACE_ID
    assert attrs["access_control_id"] == AC_ID
    assert attrs["entrance_id"] == ENTRANCE_ID
    assert attrs["openable"] is True

    core_attrs = {
        "friendly_name", "device_class", "icon", "supported_features",
        "attribution", "entity_picture", "assumed_state", "code_format",
    }
    ours = {k for k in attrs if k not in core_attrs}
    snake = re.compile(r"^[a-z][a-z0-9_]*$")
    bad = sorted(k for k in ours if not snake.match(k))
    assert not bad, f"ключи не snake_case: {bad}"

    base = pathlib.Path(__file__).resolve().parent.parent / "custom_components/elektronny_gorod"
    for name in ("strings.json", "translations/ru.json", "translations/en.json"):
        data = json.loads((base / name).read_text(encoding="utf-8"))
        translated = data["entity"]["lock"]["lock"].get("state_attributes", {})
        missing = sorted(ours - set(translated))
        assert not missing, f"{name}: нет перевода имени для {missing}"
        exceptions = data.get("exceptions", {})
        for key in ("cannot_lock", "cannot_unlock"):
            assert exceptions.get(key, {}).get("message"), f"{name}: нет текста {key}"


async def test_unlock_failure_shows_jammed_and_says_so(
    hass: HomeAssistant, mock_api
):
    """Оператор не открыл — замок показывает заедание И сообщает об отказе.

    Одного состояния мало: `jammed` держится две секунды и возвращается в
    «заперто», а вызывающий получал успех. Автоматизация «открыть и
    впустить» не отличала открытую дверь от закрытой, и через две секунды
    исчезал даже визуальный след (правило Silver `action-exceptions`).
    """
    from aiohttp import ClientError

    eid = await _setup_lock(hass)
    mock_api.open_lock = AsyncMock(side_effect=ClientError("531"))

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            "lock", "unlock", {"entity_id": eid}, blocking=True
        )
    await hass.async_block_till_done()

    assert err.value.translation_key == "cannot_unlock"
    assert hass.states.get(eid).state == "jammed"


async def test_repeated_unlock_does_not_stack_timers(hass: HomeAssistant, mock_api):
    """Второе нажатие переносит возврат в «заперто», а не заводит второй таймер.

    Иначе первый таймер вернул бы состояние посреди второго открытия.
    """
    eid = await _setup_lock(hass)
    await hass.services.async_call("lock", "unlock", {"entity_id": eid}, blocking=True)
    await hass.async_block_till_done()
    await hass.services.async_call("lock", "unlock", {"entity_id": eid}, blocking=True)
    await hass.async_block_till_done()

    assert mock_api.open_lock.await_count == 2
    assert hass.states.get(eid).state in ("unlocked", "unlocking")


async def test_lock_without_coordinator_data_has_no_attributes(
    hass: HomeAssistant, mock_api
):
    """Пока данных нет, атрибутов тоже нет — вместо выдуманных значений."""
    from custom_components.elektronny_gorod.lock import ElektronnyGorodLock

    coordinator = MagicMock()
    coordinator.data = {"locks": []}
    lock = ElektronnyGorodLock(
        coordinator,
        {
            "place_id": PLACE_ID,
            "access_control_id": AC_ID,
            "entrance_id": ENTRANCE_ID,
            "name": "Entrance 1",
            "openable": True,
        },
    )

    assert lock.extra_state_attributes is None
    assert lock.available is False


async def test_lock_returns_to_locked_after_the_door_closes(
    hass: HomeAssistant, mock_api
):
    """Замок сам возвращается в «заперто» — защёлку запирает железо.

    Без возврата состояние навсегда осталось бы «отперто», и автоматизации,
    построенные на нём, перестали бы срабатывать на следующем открытии.
    """
    from homeassistant.util import dt as dt_util
    from pytest_homeassistant_custom_component.common import async_fire_time_changed

    from custom_components.elektronny_gorod.lock import LOCK_UNLOCK_DELAY

    eid = await _setup_lock(hass)
    await hass.services.async_call("lock", "unlock", {"entity_id": eid}, blocking=True)
    await hass.async_block_till_done()
    assert hass.states.get(eid).state == "unlocked"

    async_fire_time_changed(
        hass, dt_util.utcnow() + timedelta(seconds=LOCK_UNLOCK_DELAY + 1)
    )
    await hass.async_block_till_done()

    assert hass.states.get(eid).state == "locked"


async def test_unlock_timeout_also_refuses_and_does_not_stick(
    hass: HomeAssistant, mock_api
):
    """Оператор молчит дольше бюджета — отказ такой же внятный, как при 5xx.

    Таймаут полного запроса приходит не `ClientError`, а голым
    `TimeoutError`, и мимо обработки уходили сразу две вещи: вызывающий
    получал пустую «неизвестную ошибку», а замок навсегда оставался в
    «отпирается» — возврат в «заперто» планируется только в обработанных
    ветках. В отличие от «заело», это состояние само не проходило.
    """
    eid = await _setup_lock(hass)
    mock_api.open_lock = AsyncMock(side_effect=TimeoutError())

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            "lock", "unlock", {"entity_id": eid}, blocking=True
        )
    await hass.async_block_till_done()

    assert err.value.translation_key == "cannot_unlock"
    assert hass.states.get(eid).state == "jammed", "состояние не должно залипнуть"
