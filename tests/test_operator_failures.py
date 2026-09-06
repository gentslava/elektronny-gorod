"""Реакция на отказы оператора: отзыв токена и устойчивое молчание.

Отзыв токена раньше поднимался как `UpdateFailed` — то есть «повторим позже».
Повтором это не лечится: сколько ни ждать, ответ будет тот же. Запись просто
уходила в «недоступна», а пользователю оставалось догадываться, что делать.

Устойчивое молчание по отдельным видам данных, наоборот, логировалось на
каждом цикле обновления — раз в пять минут, бесконечно.
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiohttp import ClientError, ClientResponse
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from custom_components.elektronny_gorod.const import (
    CONF_ACCESS_TOKEN,
    CONF_OPERATOR_ID,
    CONF_REFRESH_TOKEN,
    CONF_USER_AGENT,
    DOMAIN,
)
from custom_components.elektronny_gorod.http import is_unauthorized
from custom_components.elektronny_gorod.user_agent import UserAgent


def _response(status: int) -> MagicMock:
    response = MagicMock(spec=ClientResponse)
    response.status = status
    return response


def _make_config_entry() -> MockConfigEntry:
    ua = UserAgent()
    ua.operator_id = "1"
    return MockConfigEntry(
        domain=DOMAIN,
        version=3,
        unique_id="test_unique_subscriber_S1",
        title="Test",
        data={
            CONF_ACCESS_TOKEN: "STALE",
            CONF_REFRESH_TOKEN: "R1",
            CONF_OPERATOR_ID: "1",
            CONF_USER_AGENT: json.dumps(ua.json()),
            "account_id": "A1",
            "subscriber_id": "S1",
            "use_go2rtc": False,
        },
    )


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (ClientError(_response(401)), True),
        (ClientError(_response(500)), False),
        (ClientError(_response(531)), False),
        (ClientError("нет ответа вовсе"), False),
        (TimeoutError(), False),
    ],
)
def test_only_401_counts_as_revoked_token(error, expected) -> None:
    """Отзыв токена отличается от временной ошибки оператора.

    Оператор регулярно отдаёт `531` и `500` — по ним звать пользователя
    заново вводить пароль нельзя.
    """
    assert is_unauthorized(error) is expected


async def test_revoked_token_starts_reauth(hass: HomeAssistant) -> None:
    """401 при загрузке — запись просит повторный вход, а не «недоступна»."""
    entry = _make_config_entry()
    entry.add_to_hass(hass)

    with patch(
        "custom_components.elektronny_gorod.coordinator.ElektronnyGorodAPI"
    ) as cls:
        api = cls.return_value
        api.http = AsyncMock()
        api.http.user_agent = AsyncMock()
        api.query_places = AsyncMock(side_effect=ClientError(_response(401)))

        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert len(flows) == 1, "Home Assistant не предложил войти заново"
    assert flows[0]["context"]["source"] == "reauth"


async def test_operator_outage_does_not_ask_for_credentials(
    hass: HomeAssistant,
) -> None:
    """Временный отказ оператора повторный вход не запускает.

    Иначе каждое падение на стороне оператора выглядело бы как «ваш пароль
    больше не подходит».
    """
    entry = _make_config_entry()
    entry.add_to_hass(hass)

    with patch(
        "custom_components.elektronny_gorod.coordinator.ElektronnyGorodAPI"
    ) as cls:
        api = cls.return_value
        api.http = AsyncMock()
        api.http.user_agent = AsyncMock()
        api.query_places = AsyncMock(side_effect=ClientError(_response(500)))

        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert not hass.config_entries.flow.async_progress_by_handler(DOMAIN)


async def test_persistent_failure_logs_once_not_every_cycle(
    hass: HomeAssistant, caplog
) -> None:
    """Устойчивый отказ подзапроса — одна строка, а не одна на каждый цикл.

    Оператор молчит про отдельные виды данных сутками. При обновлении раз в
    пять минут прежний `warning` на каждом цикле давал под три сотни
    одинаковых строк в сутки на каждый отказавший вид.
    """
    import logging

    from custom_components.elektronny_gorod.coordinator import (
        ElektronnyGorodUpdateCoordinator,
    )

    entry = _make_config_entry()
    entry.add_to_hass(hass)

    with patch(
        "custom_components.elektronny_gorod.coordinator.ElektronnyGorodAPI"
    ) as cls:
        api = cls.return_value
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
        api.query_balance = AsyncMock(side_effect=ClientError(_response(500)))

        coordinator = ElektronnyGorodUpdateCoordinator(hass, entry=entry)

        with caplog.at_level(logging.INFO):
            for _ in range(5):
                await coordinator._async_update_data()

            complaints = [r for r in caplog.records if "недоступны" in r.msg]
            assert len(complaints) == 1, "жалоба повторяется на каждом цикле"

            # Данные вернулись — об этом должно быть сказано ровно один раз.
            api.query_balance = AsyncMock(return_value={"balance": 1.0})
            for _ in range(3):
                await coordinator._async_update_data()

        recovered = [r for r in caplog.records if "снова отвечают" in r.msg]
        assert len(recovered) == 1


async def test_foreign_entry_id_is_not_resolved(hass: HomeAssistant) -> None:
    """Идентификатор чужой интеграции не доходит до её данных.

    Реестр записей глобальный. Раньше домен проверялся неявно — координатор
    искали в нашем словаре, и чужой идентификатор просто не находился. У media
    source идентификатор приходит из пользовательского `media-source://`-адреса,
    поэтому без явной проверки запрос уходил в `runtime_data` чужой записи.
    """
    from homeassistant.config_entries import ConfigEntryState

    from custom_components.elektronny_gorod.coordinator import async_get_coordinator

    foreign = MockConfigEntry(domain="sun", title="Sun")
    foreign.add_to_hass(hass)
    foreign.runtime_data = object()
    foreign.mock_state(hass, ConfigEntryState.LOADED)

    assert async_get_coordinator(hass, foreign.entry_id) is None
    assert async_get_coordinator(hass, "нет такой записи") is None


async def test_unloaded_entry_is_not_resolved(hass: HomeAssistant) -> None:
    """У выгруженной записи данных нет — ядро их удаляет."""
    from homeassistant.config_entries import ConfigEntryState

    from custom_components.elektronny_gorod.coordinator import async_get_coordinator

    entry = _make_config_entry()
    entry.add_to_hass(hass)
    entry.runtime_data = object()
    entry.mock_state(hass, ConfigEntryState.NOT_LOADED)

    assert async_get_coordinator(hass, entry.entry_id) is None
