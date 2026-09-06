"""Контракт авторизации и списков у оператора.

Эти методы — граница с чужим API, и до сих пор они были покрыты хуже всего
остального. Тесты фиксируют и адреса запросов, и разбор ответа, и то, во что
превращается отказ: config flow ловит только `ValueError`, поэтому любое
другое исключение доедет до пользователя как «неизвестная ошибка» с
трассировкой вместо подсказки в форме.
"""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiohttp import ClientError, ClientResponse

from custom_components.elektronny_gorod.api import ElektronnyGorodAPI
from custom_components.elektronny_gorod.user_agent import UserAgent

_PHONE = "+79990000000"
_CONTRACT = {
    "accountId": "ACC",
    "address": "Some St 1",
    "operatorId": 1,
    "subscriberId": 42,
    "placeId": "PLACE",
}


def _api(hass) -> ElektronnyGorodAPI:
    return ElektronnyGorodAPI(hass, UserAgent())


def _response(status: int = 200, payload: Any = None) -> MagicMock:
    response = MagicMock(spec=ClientResponse)
    response.status = status
    response.json = AsyncMock(return_value=payload)
    return response


def _refusal(status: int) -> ClientError:
    """Отказ оператора в том виде, в каком его создаёт `http.py`."""
    return ClientError(_response(status))


# ─── Вход: телефон ──────────────────────────────────────────────────────────


async def test_login_with_contracts_asks_for_sms(hass) -> None:
    """`300` от оператора означает: договоры есть, пароля нет — нужен код."""
    api = _api(hass)
    api.http.get = AsyncMock(return_value=_response(300, [_CONTRACT]))

    assert await api.query_contracts(_PHONE) == {
        "password": False,
        "contracts": [_CONTRACT],
    }
    api.http.get.assert_awaited_once_with(f"/auth/v2/login/{_PHONE}")


async def test_login_with_password_skips_sms(hass) -> None:
    """`200` означает: у учётной записи задан пароль."""
    api = _api(hass)
    api.http.get = AsyncMock(return_value=_response(200))

    assert await api.query_contracts(_PHONE) == {"password": True, "contracts": []}


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (204, "unregistered"),
        (418, "unknown_status"),
    ],
)
async def test_login_status_becomes_form_error(hass, status, expected) -> None:
    """Каждый нештатный статус превращается в ключ ошибки формы."""
    api = _api(hass)
    api.http.get = AsyncMock(return_value=_response(status))

    with pytest.raises(ValueError, match=expected):
        await api.query_contracts(_PHONE)


async def test_login_rejected_by_operator(hass) -> None:
    """`400` — номер оператору не подошёл."""
    api = _api(hass)
    api.http.get = AsyncMock(side_effect=_refusal(400))

    with pytest.raises(ValueError, match="invalid_login"):
        await api.query_contracts(_PHONE)


@pytest.mark.parametrize("failure", [TimeoutError(), OSError("сеть отвалилась")])
async def test_login_transport_failure_stays_a_form_error(hass, failure) -> None:
    """Таймаут и сетевая ошибка тоже доходят до формы как ошибка.

    Раньше распаковка ответа из исключения падала с `IndexError` на
    исключениях без аргументов, и вместо подсказки в форме пользователь видел
    «неизвестную ошибку» с трассировкой в журнале. Для этого оператора
    таймаут — обычное дело.
    """
    api = _api(hass)
    api.http.get = AsyncMock(side_effect=failure)

    with pytest.raises(ValueError, match="unknown_status"):
        await api.query_contracts(_PHONE)


# ─── Вход: пароль и код ─────────────────────────────────────────────────────


async def test_password_auth_sends_both_hashes(hass) -> None:
    """Пароль уходит двумя хэшами, сам пароль в запрос не попадает."""
    import json

    api = _api(hass)
    api.http.get = AsyncMock(return_value=_response(200))
    await api.query_contracts(_PHONE)
    api.http.post = AsyncMock(return_value=_response(200, {"accessToken": "AT"}))

    assert await api.verify_password("TS", "H1", "H2") == {"accessToken": "AT"}

    url, body = api.http.post.await_args.args
    assert url == f"/auth/v2/auth/{_PHONE}/password"
    payload = json.loads(body)
    assert payload == {"login": _PHONE, "timestamp": "TS", "hash1": "H1", "hash2": "H2"}


async def test_password_auth_without_phone_refuses(hass) -> None:
    """Без известного номера шаг пароля невозможен."""
    api = _api(hass)

    with pytest.raises(ValueError, match="missing_phone"):
        await api.verify_password("TS", "H1", "H2")


async def test_wrong_password_becomes_form_error(hass) -> None:
    api = _api(hass)
    api.http.get = AsyncMock(return_value=_response(200))
    await api.query_contracts(_PHONE)
    api.http.post = AsyncMock(side_effect=_refusal(400))

    with pytest.raises(ValueError, match="invalid_password"):
        await api.verify_password("TS", "H1", "H2")


async def test_sms_request_sends_contract_identity(hass) -> None:
    import json

    api = _api(hass)
    api.http.get = AsyncMock(return_value=_response(300, [_CONTRACT]))
    await api.query_contracts(_PHONE)
    api.http.post = AsyncMock(return_value=_response(200))

    assert await api.request_sms_code(_CONTRACT) is None

    url, body = api.http.post.await_args.args
    assert url == f"/auth/v2/confirmation/{_PHONE}"
    assert json.loads(body)["subscriberId"] == "42", "идентификатор уходит строкой"


async def test_too_many_sms_requests(hass) -> None:
    """`429` — оператор просит подождать, и форма должна это сказать."""
    api = _api(hass)
    api.http.get = AsyncMock(return_value=_response(300, [_CONTRACT]))
    await api.query_contracts(_PHONE)
    api.http.post = AsyncMock(side_effect=_refusal(429))

    with pytest.raises(ValueError, match="limit_exceeded"):
        await api.request_sms_code(_CONTRACT)


async def test_sms_verification_sends_code_twice(hass) -> None:
    """Код уходит в двух полях — так делает приложение оператора."""
    import json

    api = _api(hass)
    api.http.get = AsyncMock(return_value=_response(300, [_CONTRACT]))
    await api.query_contracts(_PHONE)
    api.http.post = AsyncMock(return_value=_response(200, {"accessToken": "AT"}))

    assert await api.verify_sms_code(_CONTRACT, "1234") == {"accessToken": "AT"}

    url, body = api.http.post.await_args.args
    assert url == f"/auth/v3/auth/{_PHONE}/confirmation"
    payload = json.loads(body)
    assert payload["confirm1"] == payload["confirm2"] == "1234"


async def test_malformed_sms_code(hass) -> None:
    api = _api(hass)
    api.http.get = AsyncMock(return_value=_response(300, [_CONTRACT]))
    await api.query_contracts(_PHONE)
    api.http.post = AsyncMock(side_effect=_refusal(406))

    with pytest.raises(ValueError, match="invalid_format"):
        await api.verify_sms_code(_CONTRACT, "нет")


# ─── Профиль и деньги ───────────────────────────────────────────────────────


async def test_profile_unwraps_data(hass) -> None:
    api = _api(hass)
    api.http.get = AsyncMock(return_value=_response(200, {"data": {"subscriber": {}}}))

    assert await api.query_profile() == {"subscriber": {}}
    api.http.get.assert_awaited_once_with("/rest/v1/subscribers/profiles")


async def test_empty_profile_is_not_a_crash(hass) -> None:
    """Пустой ответ — пустой профиль, а не падение."""
    api = _api(hass)
    api.http.get = AsyncMock(return_value=_response(200, None))

    assert await api.query_profile() == {}


async def test_expired_token_on_profile(hass) -> None:
    api = _api(hass)
    api.http.get = AsyncMock(side_effect=_refusal(401))

    with pytest.raises(ValueError, match="unauthorized"):
        await api.query_profile()


async def test_balance_asks_for_one_place(hass) -> None:
    api = _api(hass)
    api.http.get = AsyncMock(return_value=_response(200, {"data": {"balance": 1.5}}))

    assert await api.query_balance("PLACE") == {"balance": 1.5}
    api.http.get.assert_awaited_once_with(
        "/api/mh-payment/mobile/v1/finance?placeId=PLACE"
    )


# ─── Списки ─────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("method", "url", "payload", "expected"),
    [
        ("query_places", "/rest/v3/subscriber-places", {"data": [{"id": 1}]}, [{"id": 1}]),
        ("query_places", "/rest/v3/subscriber-places", None, []),
        (
            "query_old_cameras",
            "/rest/v1/forpost/cameras",
            {"data": [{"ID": 7}]},
            [{"ID": 7}],
        ),
    ],
)
async def test_listing_without_place(hass, method, url, payload, expected) -> None:
    api = _api(hass)
    api.http.get = AsyncMock(return_value=_response(200, payload))

    assert await getattr(api, method)() == expected
    api.http.get.assert_awaited_once_with(url)


@pytest.mark.parametrize(
    ("method", "url"),
    [
        ("query_access_controls", "/rest/v1/places/PLACE/accesscontrols"),
        ("query_cameras", "/rest/v1/places/PLACE/cameras"),
        ("query_public_cameras", "/rest/v2/places/PLACE/public/cameras"),
    ],
)
async def test_listing_for_place(hass, method, url) -> None:
    """Адрес запроса — часть контракта: он повторяет приложение оператора."""
    api = _api(hass)
    api.http.get = AsyncMock(return_value=_response(200, {"data": [{"id": 1}]}))

    assert await getattr(api, method)("PLACE") == [{"id": 1}]
    api.http.get.assert_awaited_once_with(url)


async def test_sections_read_their_own_key(hass) -> None:
    """Разделы экрана лежат под `sections`, а не под `data`.

    Отдельный контракт: адрес тоже другой — `screen-sections`.
    """
    api = _api(hass)
    api.http.get = AsyncMock(return_value=_response(200, {"sections": [{"id": 1}]}))

    assert await api.query_sections("PLACE") == [{"id": 1}]
    api.http.get.assert_awaited_once_with("/rest/v1/places/PLACE/screen-sections")


async def test_sections_survive_operator_failure(hass) -> None:
    """Разделы необязательны: их отказ не должен ронять обновление."""
    api = _api(hass)
    api.http.get = AsyncMock(side_effect=_refusal(500))

    assert await api.query_sections("PLACE") == []


@pytest.mark.parametrize(
    "method",
    ["query_access_controls", "query_cameras", "query_public_cameras"],
)
async def test_empty_listing_is_a_list(hass, method) -> None:
    """Пустой ответ даёт пустой список, а не `None`.

    Дальше по коду результат перебирают циклом — `None` уронил бы обновление
    целиком, а не отдельный вид данных.
    """
    api = _api(hass)
    api.http.get = AsyncMock(return_value=_response(200, None))

    assert await getattr(api, method)("PLACE") == []


async def test_open_lock_targets_the_entrance(hass) -> None:
    api = _api(hass)
    api.http.post = AsyncMock(return_value=_response(200))

    await api.open_lock("PLACE", "AC", "ENT")

    url = api.http.post.await_args.args[0]
    assert "PLACE" in url and "AC" in url and "ENT" in url


# ─── Пользовательские настройки и снимок ────────────────────────────────────


async def test_screens_settings_return_user_preferences(hass) -> None:
    """Настройки видимости приходят как есть — это выбор пользователя."""
    payload = {"screens": [{"type": "PUBLIC_CAMERAS", "hidden": [{"id": "7"}]}]}
    api = _api(hass)
    api.http.get = AsyncMock(return_value=_response(200, payload))

    assert await api.query_screens_settings("PLACE") == payload
    api.http.get.assert_awaited_once_with(
        "/api/mh-customer/mobile/v1/customers/places/PLACE/settings/screens"
    )


@pytest.mark.parametrize("outcome", [None, _refusal(500)])
async def test_screens_settings_degrade_to_everything_visible(hass, outcome) -> None:
    """Нет настроек или отказ — считаем, что скрытого нет.

    Иначе сбой этого необязательного запроса прятал бы у пользователя камеры,
    которые он не прятал.
    """
    api = _api(hass)
    if isinstance(outcome, Exception):
        api.http.get = AsyncMock(side_effect=outcome)
    else:
        api.http.get = AsyncMock(return_value=_response(200, outcome))

    assert await api.query_screens_settings("PLACE") == {}


async def test_dnd_unwraps_its_own_key(hass) -> None:
    """Режим «не беспокоить» лежит под своим ключом, а не под `data`."""
    items = [{"type": "INTERCOM_CALLS", "status": True}]
    api = _api(hass)
    api.http.get = AsyncMock(return_value=_response(200, {"do_not_disturb": items}))

    assert await api.query_dnd_settings("PLACE") == items


@pytest.mark.parametrize("payload", [None, {}, {"do_not_disturb": None}])
async def test_dnd_missing_is_an_empty_list(hass, payload) -> None:
    api = _api(hass)
    api.http.get = AsyncMock(return_value=_response(200, payload))

    assert await api.query_dnd_settings("PLACE") == []


async def test_dnd_update_reports_acceptance(hass) -> None:
    """Переключатель должен знать, принял ли оператор изменение."""
    import json

    items = [{"type": "INTERCOM_CALLS", "status": False}]
    api = _api(hass)
    api.http.post = AsyncMock(return_value=_response(200))
    api.http.post.return_value.ok = True

    assert await api.post_dnd_settings("PLACE", items) is True
    url, body = api.http.post.await_args.args
    assert url.endswith("/settings/do_not_disturb")
    assert json.loads(body) == items, "тело — голый массив, без обёртки"


@pytest.mark.parametrize("failure", [_refusal(500), TimeoutError()])
async def test_dnd_update_reports_refusal(hass, failure) -> None:
    """Отказ не должен выглядеть как успешное переключение."""
    api = _api(hass)
    api.http.post = AsyncMock(side_effect=failure)

    assert await api.post_dnd_settings("PLACE", []) is False


async def test_stream_url_missing_is_not_a_crash(hass) -> None:
    """Нет потока — `None`, а не исключение: камера просто без видео."""
    api = _api(hass)
    api.http.get = AsyncMock(side_effect=_refusal(500))

    assert await api.query_camera_stream("CAM") is None


async def test_snapshot_asks_for_the_requested_size(hass) -> None:
    """Размер уходит оператору в запросе — от него зависит вес кадра."""
    api = _api(hass)
    api.http.get = AsyncMock(return_value=b"\xff\xd8jpeg")

    assert await api.query_camera_snapshot("CAM", 300, 169) == b"\xff\xd8jpeg"
    api.http.get.assert_awaited_once_with(
        "/rest/v1/forpost/cameras/CAM/snapshots?width=300&height=169", binary=True
    )


async def test_snapshot_rejects_unexpected_payload(hass) -> None:
    """Не кадр и не ответ — это ошибка, а не «пустая картинка»."""
    api = _api(hass)
    api.http.get = AsyncMock(return_value={"not": "bytes"})

    with pytest.raises(TypeError):
        await api.query_camera_snapshot("CAM", 300, 169)


async def test_open_lock_without_entrance_targets_access_control(hass) -> None:
    """У домофона без подъездов адрес другой — это часть контракта."""
    api = _api(hass)
    api.http.post = AsyncMock(return_value=_response(200))

    await api.open_lock("PLACE", "AC", None)

    url = api.http.post.await_args.args[0]
    assert url.endswith("/accesscontrols/AC/actions")


# ─── Защита от неожиданного ответа ──────────────────────────────────────────


@pytest.mark.parametrize(
    ("method", "args", "verb"),
    [
        ("query_contracts", (_PHONE,), "get"),
        ("query_profile", (), "get"),
        ("query_balance", ("PLACE",), "get"),
        ("query_places", (), "get"),
        ("query_access_controls", ("PLACE",), "get"),
    ],
)
async def test_unexpected_response_type_is_refused(hass, method, args, verb) -> None:
    """Не-ответ вместо ответа — отказ, а не разбор чего попало.

    Проверка стоит на каждом методе: `http` объявлен возвращающим либо ответ,
    либо байты, и без неё разбор пошёл бы по неизвестному объекту.
    """
    api = _api(hass)
    setattr(api.http, verb, AsyncMock(return_value={"не": "ответ"}))

    with pytest.raises((TypeError, ValueError)):
        await getattr(api, method)(*args)


async def test_snapshot_accepts_a_response_object(hass) -> None:
    """Снимок может прийти и ответом — тогда читаем тело."""
    api = _api(hass)
    response = _response(200)
    response.read = AsyncMock(return_value=b"\xff\xd8jpeg")
    api.http.get = AsyncMock(return_value=response)

    assert await api.query_camera_snapshot("CAM", 80, 45) == b"\xff\xd8jpeg"


@pytest.mark.parametrize(
    ("method", "args"),
    [
        ("query_old_cameras", ()),
        ("query_cameras", ("PLACE",)),
        ("query_public_cameras", ("PLACE",)),
    ],
)
async def test_camera_listings_degrade_instead_of_failing(hass, method, args) -> None:
    """Списки камер отказ переживают: пустой список вместо исключения.

    Обновление идёт по местам подряд, и отказ одного вида данных не должен
    ронять остальные. Домофоны ведут себя иначе — там исключение уходит
    наверх, и его ловит уже координатор, который отличает отказ по месту от
    отказа целиком.
    """
    api = _api(hass)
    api.http.get = AsyncMock(return_value={"не": "ответ"})

    assert await getattr(api, method)(*args) == []


@pytest.mark.parametrize(
    ("method", "args", "verb"),
    [
        ("verify_password", ("TS", "H1", "H2"), "post"),
        ("request_sms_code", (_CONTRACT,), "post"),
        ("verify_sms_code", (_CONTRACT, "1234"), "post"),
        ("query_camera_events", ("CAM",), "get"),
        ("query_sections", ("PLACE",), "get"),
        ("query_screens_settings", ("PLACE",), "get"),
        ("query_dnd_settings", ("PLACE",), "get"),
        ("query_camera_stream", ("CAM",), "get"),
        ("mint_sip_device", ("PLACE", "AC"), "post"),
    ],
)
async def test_every_method_guards_the_response_type(hass, method, args, verb) -> None:
    """Ни один метод не разбирает то, что ответом не является.

    `http` объявлен возвращающим ответ либо байты; проверка стоит на каждом
    методе, и без неё разбор пошёл бы по неизвестному объекту. Часть методов
    отказ переживает молча — им достаточно не упасть.
    """
    api = _api(hass)
    api._phone = _PHONE
    setattr(api.http, verb, AsyncMock(return_value={"не": "ответ"}))

    try:
        await getattr(api, method)(*args)
    except (TypeError, ValueError, KeyError):
        pass  # отказ — тоже корректный исход, лишь бы не разбор мусора
