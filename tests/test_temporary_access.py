"""Временный доступ по ссылке к выбранным дверям (A-118): транспорт и действия.

Контракт снят из кода «Мой Дом» (static-only, ADR-0006); чтение сроков и
объектов подтверждено живой пробой, создание ждёт подключения услуги на
адресе. Как и у приглашения в дом, проверяется не только happy path, но и
то, чего не происходит: ссылка (`sharedLinkMessage`) не оседает в журнале
и не отдаётся в списке, действия не достаются не-администратору, 404
(услуга не подключена) становится внятным отказом, а отзыв подтверждается
повторным чтением, а не кодом ответа.
"""
from __future__ import annotations

import json
import logging
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiohttp import ClientError, ClientResponse

from homeassistant.core import Context, SupportsResponse
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from custom_components.elektronny_gorod.api import ElektronnyGorodAPI
from custom_components.elektronny_gorod.const import (
    CONF_ACCESS_TOKEN,
    CONF_OPERATOR_ID,
    CONF_REFRESH_TOKEN,
    CONF_USER_AGENT,
    DOMAIN,
)
from custom_components.elektronny_gorod.device import place_device_id
from custom_components.elektronny_gorod.user_agent import UserAgent

_PLACE = "1000000"
_TTLS = [3600, 14400, 43200, 86400]
_CONTROLS = [
    {"id": 11, "name": "Калитка", "roleName": "r", "externalId": "e1"},
    {"id": 22, "name": "Подъезд", "roleName": "r", "externalId": "e2"},
]
# Часовой ASCII: кириллица экранировалась бы в `\uXXXX`, и проверка «нет в
# тексте» прошла бы над самой утечкой.
_SECRET = "TEMP-PASS-LINK-DO-NOT-LOG"


def _api(hass) -> ElektronnyGorodAPI:
    return ElektronnyGorodAPI(hass, UserAgent())


def _response(status: int = 200, payload: Any = None) -> MagicMock:
    response = MagicMock(spec=ClientResponse)
    response.status = status
    response.json = AsyncMock(return_value=payload)
    return response


def _pass(pass_id: int = 7, message: str = "link") -> dict[str, Any]:
    return {
        "id": pass_id,
        "sharedLinkMessage": message,
        "status": "ACTIVE",
        "expiredAt": 1000000,
        "availableAccessControl": [{"id": 11, "name": "Калитка", "roleName": "r"}],
    }


# ─── Транспорт (методы API поверх подменённого http) ──────────────────────────


async def test_ttls_parsed_as_ints(hass) -> None:
    """`time-to-life` возвращает голый массив секунд; булевы не в счёт."""
    api = _api(hass)
    api.http.get = AsyncMock(return_value=_response(200, [3600, 14400.0, True, "x"]))
    assert await api.query_temp_access_ttls(_PLACE) == [3600, 14400]


async def test_controls_keep_only_objects(hass) -> None:
    api = _api(hass)
    api.http.get = AsyncMock(return_value=_response(200, [*_CONTROLS, "junk"]))
    assert await api.query_temp_access_controls(_PLACE) == _CONTROLS


async def test_list_endpoint_accepts_bare_array_and_data_wrapper(hass) -> None:
    """Эндпоинт отдаёт голый массив; обёртка `data` тоже принимается."""
    api = _api(hass)
    api.http.get = AsyncMock(return_value=_response(200, {"data": [_pass()]}))
    assert await api.query_temp_passes(_PLACE) == [_pass()]
    api.http.get = AsyncMock(return_value=_response(200, "not-a-list"))
    assert await api.query_temp_passes(_PLACE) == []


async def test_create_sends_exact_body(hass) -> None:
    """Тело POST — ровно `{placeId:int, ttl, accessControlIds}`."""
    api = _api(hass)
    api.http.post = AsyncMock(return_value=_response(200, _pass()))
    created = await api.create_temp_pass(_PLACE, 3600, [11, 22])
    assert created == _pass()
    assert api.http.post.await_args is not None
    url, body = api.http.post.await_args.args
    assert url == "/api/mh-temp-pass/mobile/v1/rest/v1/temp-passes"
    assert json.loads(body) == {"placeId": 1000000, "ttl": 3600, "accessControlIds": [11, 22]}


async def test_create_non_object_200_is_empty(hass) -> None:
    """Массив/скаляр на 200 не роняет `AttributeError`, а даёт пусто."""
    api = _api(hass)
    api.http.post = AsyncMock(return_value=_response(200, []))
    assert await api.create_temp_pass(_PLACE, 3600, [11]) == {}


async def test_create_rejects_binary_response(hass) -> None:
    """Если http отдал байты (binary-ветка), это не ответ — явный отказ."""
    api = _api(hass)
    api.http.post = AsyncMock(return_value=b"bytes")
    with pytest.raises(TypeError):
        await api.create_temp_pass(_PLACE, 3600, [11])


async def test_list_rejects_binary_response(hass) -> None:
    api = _api(hass)
    api.http.get = AsyncMock(return_value=b"bytes")
    with pytest.raises(TypeError):
        await api.query_temp_passes(_PLACE)


async def test_delete_sends_place_body(hass) -> None:
    """DELETE идёт с телом `{placeId}` — мирроринг приложения."""
    api = _api(hass)
    api.http.delete = AsyncMock(return_value=_response(200, None))
    await api.delete_temp_pass(_PLACE, 7)
    assert api.http.delete.await_args is not None
    url, body = api.http.delete.await_args.args
    assert url == "/api/mh-temp-pass/mobile/v1/rest/v1/temp-passes/7"
    assert json.loads(body) == {"placeId": 1000000}


# ─── Действия ─────────────────────────────────────────────────────────────────


async def _setup(hass, *, subscriber: str = "S1") -> tuple[MagicMock, Any]:
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    ua = UserAgent()
    ua.operator_id = "1"
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=3,
        unique_id=f"test_unique_subscriber_{subscriber}",
        data={
            CONF_ACCESS_TOKEN: "AT",
            CONF_REFRESH_TOKEN: "RT",
            CONF_OPERATOR_ID: "1",
            CONF_USER_AGENT: json.dumps(ua.json()),
            "account_id": f"A{subscriber}",
            "subscriber_id": subscriber,
            "use_go2rtc": False,
            "go2rtc_base_url": "http://127.0.0.1:1984",
            "go2rtc_rtsp_host": "127.0.0.1",
        },
    )
    entry.add_to_hass(hass)
    with patch(
        "custom_components.elektronny_gorod.coordinator.ElektronnyGorodAPI"
    ) as cls:
        api = cls.return_value
        api.http = AsyncMock()
        api.query_places = AsyncMock(return_value=[{
            "subscriber": {"id": subscriber, "accountId": f"A{subscriber}", "name": "T"},
            "place": {"id": _PLACE, "address": "addr"},
        }])
        api.query_balance = AsyncMock(return_value={})
        api.query_access_controls = AsyncMock(return_value=[])
        api.query_cameras = AsyncMock(return_value=[])
        api.query_public_cameras = AsyncMock(return_value=[])
        api.query_screens_settings = AsyncMock(return_value={})
        api.query_dnd_settings = AsyncMock(return_value=[])
        api.query_temp_access_ttls = AsyncMock(return_value=list(_TTLS))
        api.query_temp_access_controls = AsyncMock(return_value=list(_CONTROLS))
        api.query_temp_passes = AsyncMock(return_value=[])
        api.create_temp_pass = AsyncMock(return_value=_pass())
        api.delete_temp_pass = AsyncMock(return_value=None)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return api, entry


def _place(hass, entry) -> str:
    device_id = place_device_id(hass, entry.entry_id, _PLACE)
    assert device_id, "устройство адреса не создано"
    return device_id


async def _user(hass, *, admin: bool = True):
    await hass.auth.async_create_user("Владелец", group_ids=["system-admin"])
    user = await hass.auth.async_create_user(
        "Кто-то", group_ids=["system-admin" if admin else "system-users"]
    )
    assert user.is_admin is admin
    return user


async def _call(hass, service: str, data: dict, *, admin: bool = True, response: bool = True) -> Any:
    user = await _user(hass, admin=admin)
    return await hass.services.async_call(
        DOMAIN, service, data, blocking=True,
        return_response=response, context=Context(user_id=user.id),
    )


def _client_error(status: int) -> ClientError:
    return ClientError(_response(status))


async def test_create_returns_message_without_link_fields_leaking(hass) -> None:
    api, entry = await _setup(hass)
    api.create_temp_pass = AsyncMock(return_value=_pass(message=_SECRET))
    result = await _call(
        hass, "create_temporary_access",
        {"device_id": _place(hass, entry), "ttl": 3600, "access_control_ids": [11]},
    )
    assert result == {"message": _SECRET, "expires_at": 1000000, "status": "ACTIVE"}
    api.create_temp_pass.assert_awaited_once_with(_PLACE, 3600, [11])


async def test_create_defaults_to_all_controls(hass) -> None:
    """Без явного списка доступ выдаётся всем доступным объектам адреса."""
    api, entry = await _setup(hass)
    await _call(hass, "create_temporary_access", {"device_id": _place(hass, entry), "ttl": 3600})
    api.create_temp_pass.assert_awaited_once_with(_PLACE, 3600, [11, 22])


@pytest.mark.parametrize(("sent", "granted"), [(None, [11, 22]), (22, [22]), ("22", [22])])
async def test_create_accepts_ui_shapes_of_controls(hass, sent, granted) -> None:
    """Форма действия шлёт `null` для пустого поля и скаляр для одного объекта."""
    api, entry = await _setup(hass)
    await _call(
        hass, "create_temporary_access",
        {"device_id": _place(hass, entry), "ttl": 3600, "access_control_ids": sent},
    )
    assert api.create_temp_pass.await_args is not None
    assert api.create_temp_pass.await_args.args[2] == granted


async def test_create_rejects_unknown_ttl(hass) -> None:
    api, entry = await _setup(hass)
    with pytest.raises(ServiceValidationError) as err:
        await _call(hass, "create_temporary_access", {"device_id": _place(hass, entry), "ttl": 999})
    assert err.value.translation_key == "temp_access_bad_ttl"
    api.create_temp_pass.assert_not_awaited()


async def test_create_rejects_unknown_control(hass) -> None:
    api, entry = await _setup(hass)
    with pytest.raises(ServiceValidationError) as err:
        await _call(
            hass, "create_temporary_access",
            {"device_id": _place(hass, entry), "ttl": 3600, "access_control_ids": [999]},
        )
    assert err.value.translation_key == "temp_access_bad_control"
    api.create_temp_pass.assert_not_awaited()


async def test_create_refuses_when_no_controls(hass) -> None:
    api, entry = await _setup(hass)
    api.query_temp_access_controls = AsyncMock(return_value=[])
    with pytest.raises(ServiceValidationError) as err:
        await _call(hass, "create_temporary_access", {"device_id": _place(hass, entry), "ttl": 3600})
    assert err.value.translation_key == "temp_access_no_controls"


async def test_create_404_is_not_connected(hass) -> None:
    """Услуга не подключена на адресе → внятный отказ, не «неизвестная ошибка»."""
    api, entry = await _setup(hass)
    api.create_temp_pass = AsyncMock(side_effect=_client_error(404))
    with pytest.raises(ServiceValidationError) as err:
        await _call(hass, "create_temporary_access", {"device_id": _place(hass, entry), "ttl": 3600})
    assert err.value.translation_key == "temp_access_not_connected"


async def test_create_other_error_is_request_failed(hass) -> None:
    api, entry = await _setup(hass)
    api.create_temp_pass = AsyncMock(side_effect=_client_error(500))
    with pytest.raises(HomeAssistantError) as err:
        await _call(hass, "create_temporary_access", {"device_id": _place(hass, entry), "ttl": 3600})
    assert err.value.translation_key == "temp_access_request_failed"


async def test_create_timeout_is_request_failed(hass) -> None:
    """Общий бюджет запроса aiohttp выражает `TimeoutError` (не `ClientError`)."""
    api, entry = await _setup(hass)
    api.create_temp_pass = AsyncMock(side_effect=TimeoutError)
    with pytest.raises(HomeAssistantError) as err:
        await _call(hass, "create_temporary_access", {"device_id": _place(hass, entry), "ttl": 3600})
    assert err.value.translation_key == "temp_access_request_failed"


async def test_create_empty_link_is_refused(hass) -> None:
    api, entry = await _setup(hass)
    api.create_temp_pass = AsyncMock(return_value={"status": "ACTIVE"})
    with pytest.raises(HomeAssistantError) as err:
        await _call(hass, "create_temporary_access", {"device_id": _place(hass, entry), "ttl": 3600})
    assert err.value.translation_key == "temp_access_empty"


async def test_create_requires_admin(hass) -> None:
    api, entry = await _setup(hass)
    with pytest.raises(ServiceValidationError) as err:
        await _call(
            hass, "create_temporary_access",
            {"device_id": _place(hass, entry), "ttl": 3600}, admin=False,
        )
    assert err.value.translation_key == "temp_access_requires_admin"
    api.create_temp_pass.assert_not_awaited()


async def test_create_rejects_non_place_device(hass) -> None:
    api, entry = await _setup(hass)
    with pytest.raises(ServiceValidationError) as err:
        await _call(hass, "create_temporary_access", {"device_id": "not-a-device", "ttl": 3600})
    assert err.value.translation_key == "invite_not_a_place"


async def test_create_is_response_only(hass) -> None:
    await _setup(hass)
    assert (
        hass.services.async_services_for_domain(DOMAIN)["create_temporary_access"].supports_response
        is SupportsResponse.ONLY
    )


async def test_create_link_never_logged(hass, caplog) -> None:
    api, entry = await _setup(hass)
    api.create_temp_pass = AsyncMock(return_value=_pass(message=_SECRET))
    with caplog.at_level(logging.DEBUG):
        await _call(
            hass, "create_temporary_access",
            {"device_id": _place(hass, entry), "ttl": 3600, "access_control_ids": [11]},
        )
    assert _SECRET not in caplog.text


# ─── Список и отзыв ───────────────────────────────────────────────────────────


async def test_list_never_returns_the_link(hass) -> None:
    """Список — для управления: отдаёт состав, но не `sharedLinkMessage`."""
    api, entry = await _setup(hass)
    api.query_temp_passes = AsyncMock(return_value=[_pass(message=_SECRET)])
    result = await _call(hass, "list_temporary_access", {"device_id": _place(hass, entry)})
    assert result == {
        "available_access_controls": [
            {"id": 11, "name": "Калитка"},
            {"id": 22, "name": "Подъезд"},
        ],
        "passes": [
            {
                "id": 7,
                "status": "ACTIVE",
                "expires_at": 1000000,
                "access_controls": [{"id": 11, "name": "Калитка"}],
            }
        ],
    }
    assert _SECRET not in json.dumps(result, ensure_ascii=False)


async def test_list_requires_admin(hass) -> None:
    api, entry = await _setup(hass)
    with pytest.raises(ServiceValidationError) as err:
        await _call(hass, "list_temporary_access", {"device_id": _place(hass, entry)}, admin=False)
    assert err.value.translation_key == "temp_access_requires_admin"


async def test_revoke_confirms_by_reread(hass) -> None:
    api, entry = await _setup(hass)
    # до отзыва пропуск есть, после — нет
    api.query_temp_passes = AsyncMock(side_effect=[[_pass(pass_id=7)], []])
    await _call(
        hass, "revoke_temporary_access",
        {"device_id": _place(hass, entry), "pass_id": 7}, response=False,
    )
    api.delete_temp_pass.assert_awaited_once_with(_PLACE, 7)


async def test_revoke_fails_if_still_listed(hass) -> None:
    """Код 200 не доказывает отзыв: пропуск остался в списке → ошибка."""
    api, entry = await _setup(hass)
    api.query_temp_passes = AsyncMock(return_value=[_pass(pass_id=7)])
    with pytest.raises(HomeAssistantError) as err:
        await _call(
            hass, "revoke_temporary_access",
            {"device_id": _place(hass, entry), "pass_id": 7}, response=False,
        )
    assert err.value.translation_key == "temp_access_revoke_failed"


async def test_revoke_requires_admin(hass) -> None:
    api, entry = await _setup(hass)
    with pytest.raises(ServiceValidationError) as err:
        await _call(
            hass, "revoke_temporary_access",
            {"device_id": _place(hass, entry), "pass_id": 7}, admin=False, response=False,
        )
    assert err.value.translation_key == "temp_access_requires_admin"
    api.delete_temp_pass.assert_not_awaited()


async def test_revoke_404_is_not_connected(hass) -> None:
    api, entry = await _setup(hass)
    api.query_temp_passes = AsyncMock(return_value=[_pass(pass_id=7)])
    api.delete_temp_pass = AsyncMock(side_effect=_client_error(404))
    with pytest.raises(ServiceValidationError) as err:
        await _call(
            hass, "revoke_temporary_access",
            {"device_id": _place(hass, entry), "pass_id": 7}, response=False,
        )
    assert err.value.translation_key == "temp_access_not_connected"


async def test_revoke_unknown_pass_is_validation_error(hass) -> None:
    """Неизвестный id — ошибка ввода до DELETE, а не «проверьте связь».

    Живая проба A-118 (project-audit.md): на неизвестный id сервер отвечает 500.
    """
    api, entry = await _setup(hass)
    api.query_temp_passes = AsyncMock(return_value=[_pass(pass_id=8)])
    with pytest.raises(ServiceValidationError) as err:
        await _call(
            hass, "revoke_temporary_access",
            {"device_id": _place(hass, entry), "pass_id": 7}, response=False,
        )
    assert err.value.translation_key == "temp_access_unknown_pass"
    api.delete_temp_pass.assert_not_awaited()


async def test_revoke_refuses_when_read_fails(hass) -> None:
    """Отказ при чтении перед отзывом — переведённая ошибка, до DELETE не доходит."""
    api, entry = await _setup(hass)
    api.query_temp_passes = AsyncMock(side_effect=_client_error(500))
    with pytest.raises(HomeAssistantError) as err:
        await _call(
            hass, "revoke_temporary_access",
            {"device_id": _place(hass, entry), "pass_id": 7}, response=False,
        )
    assert err.value.translation_key == "temp_access_request_failed"
    api.delete_temp_pass.assert_not_awaited()


async def test_list_404_is_not_connected(hass) -> None:
    """Отказ в списке переводится, сырой текст с URL наружу не уходит."""
    api, entry = await _setup(hass)
    api.query_temp_passes = AsyncMock(side_effect=_client_error(404))
    with pytest.raises(ServiceValidationError) as err:
        await _call(hass, "list_temporary_access", {"device_id": _place(hass, entry)})
    assert err.value.translation_key == "temp_access_not_connected"


async def test_create_refuses_when_reads_fail(hass) -> None:
    """Отказ при чтении сроков — переведённая ошибка, до создания не доходит."""
    api, entry = await _setup(hass)
    api.query_temp_access_ttls = AsyncMock(side_effect=_client_error(500))
    with pytest.raises(HomeAssistantError) as err:
        await _call(hass, "create_temporary_access", {"device_id": _place(hass, entry), "ttl": 3600})
    assert err.value.translation_key == "temp_access_request_failed"
    api.create_temp_pass.assert_not_awaited()


@pytest.mark.parametrize(
    ("service", "data", "response"),
    [
        ("create_temporary_access", {"ttl": 3600}, True),
        ("list_temporary_access", {}, True),
        ("revoke_temporary_access", {"pass_id": 7}, False),
    ],
)
async def test_call_without_user_is_rejected(hass, service, data, response) -> None:
    """Вызов без пользователя (так приходит автоматизация) отклоняется.

    Ядерный admin-сервис такой вызов пропустил бы — ради этого гейт свой.
    """
    api, entry = await _setup(hass)
    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN, service, {"device_id": _place(hass, entry), **data},
            blocking=True, return_response=response, context=Context(user_id=None),
        )
    assert err.value.translation_key == "temp_access_requires_admin"
    for method in (
        api.query_temp_access_ttls,
        api.query_temp_access_controls,
        api.query_temp_passes,
        api.create_temp_pass,
        api.delete_temp_pass,
    ):
        method.assert_not_awaited()


def test_link_key_stays_under_redaction() -> None:
    """Ключ ссылки временного доступа не должен тихо пропасть из редакции.

    Сегодня сток недостижим, поведением его не проверить — поэтому пин.
    """
    from custom_components.elektronny_gorod._logging import SENSITIVE_KEYS, redact

    assert "sharedlinkmessage" in SENSITIVE_KEYS
    assert _SECRET not in str(redact({"sharedLinkMessage": _SECRET}))
