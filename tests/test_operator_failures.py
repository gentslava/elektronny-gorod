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


async def test_no_places_is_not_a_failure(hass: HomeAssistant) -> None:
    """Учётная запись без адресов — пустой набор данных, а не ошибка.

    Так бывает у только что оформленного договора: интеграция должна
    загрузиться и ждать, а не уходить в повторные попытки.
    """
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
        api.query_places = AsyncMock(return_value=[])

        data = await ElektronnyGorodUpdateCoordinator(hass, entry=entry)._async_update_data()

    assert data == {"places": [], "balances": [], "cameras": [], "locks": [], "dnd": {}}


async def test_one_broken_kind_of_data_does_not_sink_the_rest(
    hass: HomeAssistant,
) -> None:
    """Отказ по одному виду данных не уносит остальные.

    Оператор регулярно молчит про что-то одно; терять из-за этого камеры и
    замки было бы несоразмерно.
    """
    from aiohttp import ClientError

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
        api.query_balance = AsyncMock(side_effect=ClientError(_response(500)))
        api.query_screens_settings = AsyncMock(side_effect=ClientError(_response(500)))
        api.query_access_controls = AsyncMock(return_value=[{
            "id": "AC1",
            "name": "Intercom",
            "entrances": [{"id": "E1", "name": "Подъезд 1", "allowOpen": True}],
        }])
        api.query_cameras = AsyncMock(return_value=[])
        api.query_public_cameras = AsyncMock(return_value=[])
        api.query_dnd_settings = AsyncMock(side_effect=ClientError(_response(500)))

        data = await ElektronnyGorodUpdateCoordinator(hass, entry=entry)._async_update_data()

    assert data["balances"] == [] and data["dnd"] == {}
    assert len(data["locks"]) == 1, "замки должны пережить отказ по балансу"


async def test_every_kind_of_data_degrades_on_its_own(hass: HomeAssistant) -> None:
    """Отказ по домофонам, камерам и замкам не уносит соседей.

    Оператор отказывает по одному виду данных, а не по всем сразу — терять
    из-за этого весь набор было бы несоразмерно.
    """
    from aiohttp import ClientError

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
        api.query_access_controls = AsyncMock(side_effect=ClientError(_response(500)))
        api.query_cameras = AsyncMock(side_effect=ClientError(_response(500)))
        api.query_public_cameras = AsyncMock(side_effect=ClientError(_response(500)))
        api.query_dnd_settings = AsyncMock(return_value=[])
        api.query_balance = AsyncMock(return_value={"balance": 1.0})

        coordinator = ElektronnyGorodUpdateCoordinator(hass, entry=entry)
        data = await coordinator._async_update_data()

    assert data["cameras"] == [] and data["locks"] == []
    assert len(data["balances"]) == 1, "баланс должен пережить отказ по камерам"


async def test_place_without_identifier_is_skipped(hass: HomeAssistant) -> None:
    """Место без идентификатора пропускается, а не роняет обновление."""
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
        api.query_places = AsyncMock(return_value=[
            {"subscriber": {"id": "S1"}, "place": {}},
            {"subscriber": {"id": "S1"}},
        ])
        api.query_screens_settings = AsyncMock(return_value={})
        api.query_access_controls = AsyncMock(return_value=[])
        api.query_cameras = AsyncMock(return_value=[])
        api.query_public_cameras = AsyncMock(return_value=[])
        api.query_dnd_settings = AsyncMock(return_value=[])
        api.query_balance = AsyncMock(return_value=None)

        data = await ElektronnyGorodUpdateCoordinator(hass, entry=entry)._async_update_data()

    assert data["cameras"] == []


async def test_intercom_camera_is_taken_from_the_entrance(hass: HomeAssistant) -> None:
    """Камера домофона берётся из подъезда — там связь точнее.

    На уровне домофона идентификатор камеры у оператора бывает
    рассогласован, поэтому первично поле подъезда.
    """
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
        api.query_access_controls = AsyncMock(return_value=[{
            "id": "AC1",
            "name": "Домофон",
            "externalCameraId": "CAM_AC",
            "entrances": [
                {"id": "E1", "name": "Подъезд 1", "allowOpen": True,
                 "externalCameraId": "CAM_ENTRANCE"},
            ],
        }])
        api.query_cameras = AsyncMock(return_value=[])
        api.query_public_cameras = AsyncMock(return_value=[])
        api.query_dnd_settings = AsyncMock(return_value=[])
        api.query_balance = AsyncMock(return_value=None)

        data = await ElektronnyGorodUpdateCoordinator(hass, entry=entry)._async_update_data()

    ids = {c["id"] for c in data["cameras"]}
    assert "CAM_ENTRANCE" in ids
    assert len(data["locks"]) == 1


async def test_total_outage_is_not_logged_by_us_at_all(
    hass: HomeAssistant, caplog
) -> None:
    """Полное молчание оператора не пишем сами — это делает ядро, и один раз.

    Ядро логирует отказ обновления на переходе и возвращение данных
    (`Error fetching … data` / `Fetching … data recovered`). Свой
    `LOGGER.exception` рядом с ним давал полный трейсбек на КАЖДОМ цикле:
    под три сотни за сутки недоступности, против правила Silver
    `log-when-unavailable`. Заодно проверяем, что наружу уходит тип
    исключения, а не текст оператора: в тексте бывает адрес или id.
    """
    import logging

    from homeassistant.helpers.update_coordinator import UpdateFailed

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
        api.query_places = AsyncMock(
            side_effect=ClientError("сервер по адресу Ленина 1 недоступен")
        )

        coordinator = ElektronnyGorodUpdateCoordinator(hass, entry=entry)

        with caplog.at_level(logging.DEBUG):
            for _ in range(5):
                with pytest.raises(UpdateFailed) as err:
                    await coordinator._async_update_data()

        assert "ClientError" in str(err.value)
        assert "Ленина" not in str(err.value), "текст оператора наружу не выпускаем"
        ours = [
            r for r in caplog.records
            if r.name.startswith("custom_components.elektronny_gorod")
            and (r.exc_info is not None or "недоступ" in r.msg or "places" in r.msg)
        ]
        assert ours == [], "об отказе обновления сообщает ядро, а не мы"


async def test_empty_place_list_complains_once_and_notices_recovery(
    hass: HomeAssistant, caplog
) -> None:
    """Пустой список адресов — одна жалоба, и одна строка о возвращении.

    У заблокированного аккаунта список пуст сутками; жалоба на каждом цикле
    была бы тем же спамом, что и по подзапросам.
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
        api.query_places = AsyncMock(return_value=[])
        api.query_screens_settings = AsyncMock(return_value={})
        api.query_access_controls = AsyncMock(return_value=[])
        api.query_cameras = AsyncMock(return_value=[])
        api.query_public_cameras = AsyncMock(return_value=[])
        api.query_dnd_settings = AsyncMock(return_value=[])
        api.query_balance = AsyncMock(return_value={})

        coordinator = ElektronnyGorodUpdateCoordinator(hass, entry=entry)

        with caplog.at_level(logging.INFO):
            for _ in range(3):
                await coordinator._async_update_data()

            assert len([r for r in caplog.records if "недоступен" in r.msg]) == 1

            caplog.clear()
            api.query_places = AsyncMock(return_value=[{
                "subscriber": {"id": "S1", "accountId": "A1", "name": "Test"},
                "place": {"id": "1000000", "address": "addr"},
            }])
            await coordinator._async_update_data()

            assert [r for r in caplog.records if "снова получен" in r.msg], (
                "возвращение данных должно быть видно"
            )
