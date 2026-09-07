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


async def test_screens_settings_degrade_to_everything_visible(hass) -> None:
    """Пустой ответ — считаем, что скрытого нет.

    Иначе отсутствие настроек прятало бы у пользователя камеры, которые он не
    прятал. А вот отказ оператора пустотой не притворяется: различить их
    может только вызывающий, и координатор говорит о нём одной строкой.

    Осторожно: на отказе координатор подставляет то же «ничего не скрыто»,
    а не прежнюю видимость. Если это совпадёт с загрузкой записи,
    восстановление видимости снимет скрытие, выставленное интеграцией. Так
    было и до проброса отказа; вынесено хвостом в A-115.
    """
    api = _api(hass)
    api.http.get = AsyncMock(return_value=_response(200, None))

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


class _LooksLikeAResponse:
    """Утиный двойник ответа: без проверки типа его разобрали бы.

    Подсовывать словарь бессмысленно: методы обёрнуты в `except Exception`,
    и разбор словаря упал бы на `.json()`, дав ровно тот же отказ, что и
    сработавшая проверка, — тест не отличил бы одно от другого. Двойник же
    разбирается успешно, поэтому снятие проверки видно сразу.
    """

    status = 200

    async def json(self) -> dict[str, Any]:
        # Полезная нагрузка нарочно годится каждому вызывающему: если проверку
        # снять, метод вернёт разобранное, и тест это увидит.
        return {
            "data": {"URL": "rtsp://х", "id": "X"},
            "access_token": "AT",
            "do_not_disturb": [{"type": "INTERCOM_CALLS", "status": True}],
        }


@pytest.mark.parametrize(
    ("method", "args", "kwargs", "verb", "fallback"),
    [
        ("query_old_cameras", (), {}, "get", []),
        ("query_sections", ("PLACE",), {}, "get", []),
        ("query_camera_stream", ("CAM",), {}, "get", None),
    ],
)
async def test_lookalike_response_yields_the_safe_fallback(
    hass, method, args, kwargs, verb, fallback
) -> None:
    """Ответом оказалось не то — метод отдаёт пустоту, а не разбирает мусор.

    Эти методы кормят координатор: разобранный мусор доехал бы до сущностей
    и до состояния в интерфейсе.
    """
    api = _api(hass)
    api._phone = _PHONE
    setattr(api.http, verb, AsyncMock(return_value=_LooksLikeAResponse()))

    assert await getattr(api, method)(*args, **kwargs) == fallback


@pytest.mark.parametrize(
    ("method", "args", "kwargs", "verb", "raises", "message"),
    [
        ("query_contracts", (_PHONE,), {}, "get", ValueError, "unknown_status"),
        ("query_profile", (), {}, "get", ValueError, "unknown_status"),
        ("query_balance", ("PLACE",), {}, "get", TypeError, "Unexpected response type"),
        ("query_places", (), {}, "get", TypeError, "Unexpected response type"),
        ("query_event_download", ("EV",), {}, "get", TypeError, "Unexpected response type"),
        (
            "query_access_controls",
            ("PLACE",),
            {},
            "get",
            TypeError,
            "Unexpected response type",
        ),
        ("verify_password", ("TS", "H1", "H2"), {}, "post", ValueError, "unknown_status"),
        ("request_sms_code", (_CONTRACT,), {}, "post", ValueError, "unknown_status"),
        ("verify_sms_code", (_CONTRACT, "1234"), {}, "post", ValueError, "unknown_status"),
        (
            "query_camera_events",
            ("CAM",),
            {"lower_date": "a", "upper_date": "b"},
            "get",
            TypeError,
            "Unexpected response type",
        ),
        ("query_cameras", ("PLACE",), {}, "get", TypeError, "Unexpected response type"),
        (
            "query_public_cameras",
            ("PLACE",),
            {},
            "get",
            TypeError,
            "Unexpected response type",
        ),
        (
            "query_screens_settings",
            ("PLACE",),
            {},
            "get",
            TypeError,
            "Unexpected response type",
        ),
        (
            "query_dnd_settings",
            ("PLACE",),
            {},
            "get",
            TypeError,
            "Unexpected response type",
        ),
        ("query_events", ([1],), {}, "post", TypeError, "Unexpected response type"),
        ("mint_sip_device", ("PLACE", "AC"), {}, "post", TypeError, "Unexpected response type"),
    ],
)
async def test_lookalike_response_is_refused(
    hass, method, args, kwargs, verb, raises, message
) -> None:
    """Ответом оказалось не то — метод отказывает, а не возвращает разобранное.

    Вход и выдача SIP-устройства пустоту вернуть не могут: пустой результат
    там неотличим от успеха с пустыми данными.
    """
    api = _api(hass)
    api._phone = _PHONE
    setattr(api.http, verb, AsyncMock(return_value=_LooksLikeAResponse()))

    with pytest.raises(raises) as err:
        await getattr(api, method)(*args, **kwargs)

    assert message in str(err.value)


async def test_snapshot_refuses_anything_that_is_not_a_frame(hass) -> None:
    """Ни байты, ни ответ — отказ, а не разбор мусора."""
    api = _api(hass)
    api.http.get = AsyncMock(return_value=_LooksLikeAResponse())

    with pytest.raises(TypeError):
        await api.query_camera_snapshot("CAM", 640, 480)


@pytest.mark.parametrize(
    ("method", "args"),
    [
        ("query_cameras", ("PLACE",)),
        ("query_public_cameras", ("PLACE",)),
        ("query_screens_settings", ("PLACE",)),
        ("query_dnd_settings", ("PLACE",)),
    ],
)
async def test_collector_methods_do_not_disguise_refusal_as_emptiness(
    hass, method, args
) -> None:
    """Отказ оператора не притворяется пустым ответом.

    Эти четыре метода кормят координатор, а он один умеет отличить «данных
    нет» от «оператор молчит» и сказать об этом один раз. Пока отказ
    глотался здесь, координатор считал молчание успехом: камеры пропадали из
    интерфейса без единой строки в журнале ни на одном уровне.
    """
    api = _api(hass)
    api.http.get = AsyncMock(side_effect=_refusal(500))

    with pytest.raises(ClientError):
        await getattr(api, method)(*args)
