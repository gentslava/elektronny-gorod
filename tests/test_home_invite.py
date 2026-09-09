"""Приглашение в дом (член семьи или гость): транспорт и действие.

Приглашение делает принявшего абонентом адреса у оператора, и принять
его может любой, кто открыл ссылку. Поэтому проверяется не только то,
что запрос уходит по верному адресу, но и то, чего не происходит:
ссылка не оседает в журнале, действие не достаётся не-администратору, а
неподтверждённому оператору запрос вообще не отправляется.

Контракт снят с расшифрованного трафика приложения и зафиксирован в
[api-reference], фикстуры — в `tests/fixtures/mobile_app_9_9_0/`.
"""
from __future__ import annotations

import json
import logging
import pathlib
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiohttp import ClientError, ClientResponse

from homeassistant.core import Context, SupportsResponse
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from custom_components.elektronny_gorod.api import ElektronnyGorodAPI
from custom_components.elektronny_gorod.const import (
    BASE_API_URL,
    CONF_ACCESS_TOKEN,
    CONF_OPERATOR_ID,
    CONF_REFRESH_TOKEN,
    CONF_USER_AGENT,
    DOMAIN,
)
from custom_components.elektronny_gorod.device import place_device_id
from custom_components.elektronny_gorod.user_agent import UserAgent

_FIXTURES = pathlib.Path(__file__).resolve().parent / "fixtures/mobile_app_9_9_0"
_PLACE = "1000000"
_NTK_APP = 2
_SERVICE = "create_home_invite"

# Часовой ASCII: кириллический маркер экранируется при `%r` и в JSON-логах в
# `\uXXXX`, и проверка «нет в тексте» прошла бы над самой утечкой.
_SECRET = "GUEST-INVITE-SECRET-DO-NOT-LOG"


def _api(hass) -> ElektronnyGorodAPI:
    return ElektronnyGorodAPI(hass, UserAgent())


def _response(status: int = 200, payload: Any = None) -> MagicMock:
    response = MagicMock(spec=ClientResponse)
    response.status = status
    response.json = AsyncMock(return_value=payload)
    return response


def _success_payload() -> dict[str, Any]:
    return json.loads((_FIXTURES / "guest_invite_success.json").read_text())


# ─── Транспорт ──────────────────────────────────────────────────────────────


async def test_invite_request_matches_the_app(hass) -> None:
    """Адрес, место и бренд — как у приложения, и без тела.

    Тело у этого POST отсутствует: приложение шлёт его пустым, и оператор
    определяет всё по query. Отправить что-то в теле значило бы разойтись с
    приложением на ровном месте.
    """
    api = _api(hass)
    api.http.post = AsyncMock(return_value=_response(200, _success_payload()))

    await api.create_home_invite(_PLACE, _NTK_APP)

    api.http.post.assert_awaited_once_with(
        f"/api/mh-auth/mobile/v1/guests/link?placeId={_PLACE}&app={_NTK_APP}", None
    )


async def test_invite_query_survives_a_hostile_place_id(hass) -> None:
    """Место уезжает в query экранированным, а не разрывает её.

    Значение приходит от вызывающего. Незакодированный `&` пришил бы к
    запросу лишний параметр — например, чужой `app`.
    """
    api = _api(hass)
    api.http.post = AsyncMock(return_value=_response(200, _success_payload()))

    await api.create_home_invite("1&app=4", _NTK_APP)

    assert api.http.post.await_args.args[0] == (
        f"/api/mh-auth/mobile/v1/guests/link?placeId=1%26app%3D4&app={_NTK_APP}"
    )


async def test_invite_returns_link_and_message(hass) -> None:
    """Наружу отдаём ровно то, что прислал оператор."""
    api = _api(hass)
    payload = _success_payload()
    api.http.post = AsyncMock(return_value=_response(200, payload))

    assert await api.create_home_invite(_PLACE, _NTK_APP) == payload["data"]


async def test_invite_refusal_is_not_disguised_as_emptiness(hass) -> None:
    """Отказ оператора проходит наружу.

    Пустое приглашение выглядело бы как успешное — человек отправил бы
    гостю ничего и узнал бы об этом у двери.
    """
    api = _api(hass)
    api.http.post = AsyncMock(side_effect=ClientError(_response(401)))

    with pytest.raises(ClientError):
        await api.create_home_invite(_PLACE, _NTK_APP)


def _wire_response(
    *, status: int, ok: bool, payload: Any = None, length: str = "128"
) -> MagicMock:
    """Ответ уровня aiohttp: `http.py` читает у него url/method/reason/headers."""
    response = MagicMock(spec=ClientResponse)
    response.url = f"https://{BASE_API_URL}/api/mh-auth/mobile/v1/guests/link"
    response.method = "POST"
    response.status = status
    response.reason = "OK" if ok else "Unauthorized"
    response.ok = ok
    response.headers = {"Content-Length": length}
    response.json = AsyncMock(return_value=payload)
    return response


async def test_unauthorized_answer_is_not_parsed_as_json(hass) -> None:
    """На 401 оператор отвечает текстом, а не JSON — разбирать нечего.

    Проверка идёт через настоящий `http.py`: именно он решает по
    `response.ok`, отдать ответ вызывающему или бросить. Мок на уровне
    `api.http.post` эту развилку бы обошёл — не осталось бы ничего, что
    удерживает разбор от срабатывания на теле `text/plain`.
    """
    contract = json.loads((_FIXTURES / "guest_invite_unauthorized.json").read_text())
    assert contract["body_kind"] == "non_json_text"

    api = _api(hass)
    response = _wire_response(status=contract["http_status"], ok=False)
    response.json = AsyncMock(side_effect=AssertionError("тело 401 разбирали как JSON"))
    session = MagicMock()
    session.post = AsyncMock(return_value=response)

    with patch(
        "custom_components.elektronny_gorod.http.async_get_clientsession",
        return_value=session,
    ):
        with pytest.raises(ClientError):
            await api.create_home_invite(_PLACE, _NTK_APP)

    response.json.assert_not_awaited()


async def test_invite_never_reaches_the_journal_through_the_wire(hass, caplog) -> None:
    """Ключ не появляется в журнале и на уровне транспорта.

    Действие ходит к оператору через `http.py`, а тот логирует запрос и
    ответ на `debug`. Именно debug-логи прикладывают к обращениям в
    поддержку — а здесь по ссылке посторонний войдёт в подъезд.
    """
    api = _api(hass)
    caplog.set_level(logging.DEBUG)
    session = MagicMock()
    session.post = AsyncMock(
        return_value=_wire_response(status=200, ok=True, payload={"data": _invite()})
    )

    with patch(
        "custom_components.elektronny_gorod.http.async_get_clientsession",
        return_value=session,
    ):
        invite = await api.create_home_invite(_PLACE, _NTK_APP)

    assert invite["link"].endswith(_SECRET)
    assert _SECRET not in caplog.text


async def test_invite_refuses_a_response_that_is_not_a_response(hass) -> None:
    """Чужой тип ответа — отказ, а не разбор наугад."""
    api = _api(hass)
    api.http.post = AsyncMock(return_value=object())

    with pytest.raises(TypeError):
        await api.create_home_invite(_PLACE, _NTK_APP)


# ─── Действие ───────────────────────────────────────────────────────────────


def _invite() -> dict[str, str]:
    return {
        "link": f"https://example.invalid/guest-invite?invite={_SECRET}",
        "message": f"Приглашение действительно 30 мин. {_SECRET}",
    }


async def _setup(
    hass,
    *,
    operator_id: str = "1",
    place_id: str = _PLACE,
    subscriber: str = "S1",
) -> tuple[MagicMock, Any]:
    """Загрузить запись с одним адресом; вернуть дублёра API и саму запись."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    ua = UserAgent()
    ua.operator_id = operator_id
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=3,
        unique_id=f"test_unique_subscriber_{subscriber}",
        data={
            CONF_ACCESS_TOKEN: "AT",
            CONF_REFRESH_TOKEN: "RT",
            CONF_OPERATOR_ID: operator_id,
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
        api.http.user_agent = AsyncMock()
        api.query_places = AsyncMock(return_value=[{
            "subscriber": {
                "id": subscriber,
                "accountId": f"A{subscriber}",
                "name": "Test",
            },
            "place": {"id": place_id, "address": "addr"},
        }])
        api.query_balance = AsyncMock(return_value={})
        api.query_access_controls = AsyncMock(return_value=[])
        api.query_cameras = AsyncMock(return_value=[])
        api.query_public_cameras = AsyncMock(return_value=[])
        api.query_screens_settings = AsyncMock(return_value={})
        api.query_dnd_settings = AsyncMock(return_value=[])
        api.create_home_invite = AsyncMock(return_value=_invite())
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return api, entry


def _place_device(hass, entry, place_id: str = _PLACE) -> str:
    device_id = place_device_id(hass, entry.entry_id, place_id)
    assert device_id, "устройство адреса не создано — тест проверял бы не то"
    return device_id


async def _as_user(hass, *, admin: bool = True):
    """Пользователь нужной роли.

    Первый созданный пользователь становится владельцем, а `is_admin` у
    владельца истинно независимо от групп. Без заглушки-владельца «обычный»
    пользователь оказался бы владельцем — и тест на отказ падал бы с
    невнятным `DID NOT RAISE` вместо названного диагноза.
    """
    await hass.auth.async_create_user("Владелец", group_ids=["system-admin"])
    user = await hass.auth.async_create_user("Кто-то", group_ids=[
        "system-admin" if admin else "system-users"
    ])
    assert user.is_admin is admin, "дублёр пользователя не отражает роль"
    return user


async def _call(hass, device_id: str, *, admin: bool = True) -> Any:
    """Вызвать действие от имени администратора или обычного пользователя."""
    user = await _as_user(hass, admin=admin)
    return await hass.services.async_call(
        DOMAIN,
        _SERVICE,
        {"device_id": device_id},
        blocking=True,
        return_response=True,
        context=Context(user_id=user.id),
    )


async def test_invite_reaches_the_caller(hass) -> None:
    """Администратор получает ссылку и текст — это и есть смысл действия."""
    api, entry = await _setup(hass)

    assert await _call(hass, _place_device(hass, entry)) == _invite()
    api.create_home_invite.assert_awaited_once_with(_PLACE, _NTK_APP)


async def test_only_link_and_message_leave_the_integration(hass) -> None:
    """Всё лишнее из ответа оператора наружу не выходит.

    Ответ действия попадает в трассировки скриптов через
    `response_variable` и остаётся там надолго. Оператор шлёт вместе со
    ссылкой и другой материал (`uuid` приглашения) — ему в трассировке не
    место.
    """
    api, entry = await _setup(hass)
    api.create_home_invite = AsyncMock(
        return_value={**_invite(), "uuid": f"{_SECRET}-UUID", "qr": "..."}
    )

    assert await _call(hass, _place_device(hass, entry)) == _invite()


async def test_invite_is_response_only(hass) -> None:
    """Без `return_response` действие не выполняется вовсе.

    `SupportsResponse.OPTIONAL` означал бы, что вызов без ответа молча
    создаёт у оператора действующее приглашение и роняет его на пол.
    """
    api, entry = await _setup(hass)
    user = await _as_user(hass)

    with pytest.raises(HomeAssistantError, match="return_response"):
        await hass.services.async_call(
            DOMAIN,
            _SERVICE,
            {"device_id": _place_device(hass, entry)},
            blocking=True,
            context=Context(user_id=user.id),
        )

    api.create_home_invite.assert_not_awaited()


async def test_device_is_required(hass) -> None:
    """Без адреса действие не запускается: схема отклоняет вызов.

    Без схемы обращение к отсутствующему полю дало бы `KeyError` и
    «неизвестную ошибку» вместо внятного сообщения о незаполненном поле.
    """
    import voluptuous as vol

    api, _ = await _setup(hass)
    user = await _as_user(hass)

    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN, _SERVICE, {}, blocking=True,
            return_response=True, context=Context(user_id=user.id),
        )

    api.create_home_invite.assert_not_awaited()


async def test_invite_is_refused_to_a_non_admin(hass) -> None:
    """Обычному пользователю приглашение не выдаётся.

    Принявший становится абонентом адреса у оператора, поэтому одной
    авторизации в HA мало: любой скрипт, запущенный от обычного
    пользователя, иначе смог бы раздавать членство в доме.
    """
    api, entry = await _setup(hass)

    with pytest.raises(ServiceValidationError) as err:
        await _call(hass, _place_device(hass, entry), admin=False)

    assert err.value.translation_key == "invite_requires_admin"
    api.create_home_invite.assert_not_awaited()


async def test_invite_is_refused_without_a_caller(hass) -> None:
    """Вызов без пользователя отклоняется — и это решение, а не упущение.

    Автоматизация стирает `user_id` (`Context(parent_id=...)`), поэтому
    ядерный `async_register_admin_service` пропустил бы такой вызов без
    проверки: любой домочадец через `automation.trigger` раздавал бы
    членство в доме. Цена — из автоматизации действие недоступно; текст отказа
    об этом говорит.
    """
    api, entry = await _setup(hass)

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN,
            _SERVICE,
            {"device_id": _place_device(hass, entry)},
            blocking=True,
            return_response=True,
            context=Context(),
        )

    assert err.value.translation_key == "invite_requires_admin"
    api.create_home_invite.assert_not_awaited()


async def test_unconfirmed_operator_is_refused_without_asking(hass) -> None:
    """Неподтверждённому оператору запрос не уходит вовсе.

    Код бренда для «Дом.ру» известен только из энума приложения, живого
    запроса на нём никто не наблюдал. Отправить его наугад — значит от
    имени человека сходить к оператору с непроверенным запросом.
    """
    api, entry = await _setup(hass, operator_id="2")

    with pytest.raises(ServiceValidationError) as err:
        await _call(hass, _place_device(hass, entry))

    assert err.value.translation_key == "invite_operator_unsupported"
    api.create_home_invite.assert_not_awaited()


async def test_a_device_that_is_not_a_place_is_named_as_such(hass) -> None:
    """Камера и незнакомое устройство — отказ по существу.

    Селектор в интерфейсе показывает только адреса, но вызов из YAML
    ничем не ограничен, и «неизвестная ошибка» тут увела бы человека
    искать поломку вместо неверно выбранного устройства.
    """
    from homeassistant.helpers import device_registry as dr

    api, entry = await _setup(hass)
    camera = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "camera_777")},
        name="Камера",
    )

    for device_id in (camera.id, "no-such-device-id"):
        with pytest.raises(ServiceValidationError) as err:
            await _call(hass, device_id)
        assert err.value.translation_key == "invite_not_a_place"

    api.create_home_invite.assert_not_awaited()


async def test_unloaded_entry_is_named_as_such(hass) -> None:
    """Устройство есть, запись выгружена — так и сказать.

    Устройство адреса переживает выгрузку записи. Отказ «это не адрес»
    отправил бы человека проверять выбор устройства вместо выключенной
    интеграции.
    """
    api, entry = await _setup(hass)
    device_id = _place_device(hass, entry)

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError) as err:
        await _call(hass, device_id)

    assert err.value.translation_key == "integration_not_loaded"
    api.create_home_invite.assert_not_awaited()


async def test_invite_goes_to_the_account_that_owns_the_place(hass) -> None:
    """Два аккаунта не путаются: запрос уходит владельцу адреса.

    Ошибка тут означала бы поход к оператору с чужим токеном и чужим
    кодом бренда — то есть выдачу ключа от чужой квартиры.
    """
    other_place = "2000000"
    first_api, first_entry = await _setup(hass)
    second_api, second_entry = await _setup(
        hass, operator_id="2", place_id=other_place, subscriber="S2"
    )

    await _call(hass, _place_device(hass, first_entry))

    first_api.create_home_invite.assert_awaited_once_with(_PLACE, _NTK_APP)
    second_api.create_home_invite.assert_not_awaited()

    # Обратная сторона: адрес второй записи ведёт к её оператору, и он
    # неподтверждённый — значит маршрут ушёл именно туда, а не к первой.
    with pytest.raises(ServiceValidationError) as err:
        await _call(hass, _place_device(hass, second_entry, other_place))
    assert err.value.translation_key == "invite_operator_unsupported"


@pytest.mark.parametrize(
    ("error", "why"),
    [
        (ClientError("boom"), "отказ соединения"),
        (TimeoutError(), "общий бюджет запроса"),
        (ValueError("Expecting value"), "200 с телом, которое не JSON"),
    ],
)
async def test_transport_failures_are_all_translated(hass, error, why) -> None:
    """Каждый класс сбоя доходит текстом, а не «неизвестной ошибкой».

    Таймаут стоит здесь не для симметрии: общий бюджет запроса aiohttp
    выражает `TimeoutError`, который не наследует `ClientError`, — на этом
    уже спотыкались и отпирание замка, и вход в аккаунт.
    """
    api, entry = await _setup(hass)
    api.create_home_invite = AsyncMock(side_effect=error)

    with pytest.raises(HomeAssistantError) as err:
        await _call(hass, _place_device(hass, entry))

    assert err.value.translation_key == "invite_request_failed", why


@pytest.mark.parametrize(
    "invite",
    [{"message": "текст без ссылки"}, {"link": "", "message": "текст"}],
    ids=["no-link-key", "empty-link"],
)
async def test_success_without_a_link_is_refused(hass, invite) -> None:
    """200 без ссылки — отказ, а не успех; пустая строка — тоже не ссылка.

    Иначе человек отправил бы гостю пустоту и узнал бы об этом у двери.
    """
    api, entry = await _setup(hass)
    api.create_home_invite = AsyncMock(return_value=invite)

    with pytest.raises(HomeAssistantError) as err:
        await _call(hass, _place_device(hass, entry))

    assert err.value.translation_key == "invite_empty"


async def test_invite_never_reaches_the_journal(hass, caplog) -> None:
    """Ключ не появляется в журнале ни на одном уровне.

    Отладочные логи прикладывают к обращениям в поддержку, а это ссылка,
    по которой посторонний войдёт в подъезд.
    """
    _, entry = await _setup(hass)

    with caplog.at_level(logging.DEBUG):
        await _call(hass, _place_device(hass, entry))

    assert _SECRET not in caplog.text


@pytest.mark.parametrize(
    "payload",
    [[], "строка", {"data": ["x"]}, {"data": "строка"}],
    ids=["array", "scalar", "data-array", "data-scalar"],
)
async def test_operator_answer_of_a_wrong_shape_is_refused(hass, payload) -> None:
    """Массив или скаляр вместо объекта — отказ, а не «неизвестная ошибка».

    Сквозь настоящий разбор ответа: транспорт подменён, а `create_home_invite`
    — боевой. Контракт снят с приложения, поэтому случай маловероятен; но
    необёрнутый `AttributeError` дал бы человеку ровно ту непонятную ошибку,
    ради устранения которой написан весь блок отказов.
    """
    api, entry = await _setup(hass)
    real = _api(hass)
    real.http.post = AsyncMock(return_value=_response(200, payload))
    api.create_home_invite = real.create_home_invite

    with pytest.raises(HomeAssistantError) as err:
        await _call(hass, _place_device(hass, entry))

    assert err.value.translation_key == "invite_empty"


async def test_transport_survives_a_payload_that_is_not_an_object(hass) -> None:
    """Транспорт отдаёт пустое, а не падает, если оператор прислал массив."""
    api = _api(hass)
    for payload in ([], "строка", None, {"data": []}, {"data": ["x"]}, {"data": "строка"}):
        api.http.post = AsyncMock(return_value=_response(200, payload))
        assert await api.create_home_invite(_PLACE, _NTK_APP) == {}


async def test_invite_link_key_stays_under_redaction() -> None:
    """Ключ `link` не должен тихо исчезнуть из списка редакции.

    Сток, который он закрывает, сегодня недостижим, поэтому поведением его
    не проверить — а решение ADR-0004 закрепить надо: без этой проверки
    удаление ключа не заметил бы ни один тест.
    """
    from custom_components.elektronny_gorod._logging import SENSITIVE_KEYS

    assert "link" in SENSITIVE_KEYS


async def test_refusals_are_translated() -> None:
    """У каждого отказа есть текст во всех трёх файлах переводов."""
    base = pathlib.Path(__file__).resolve().parent.parent / "custom_components/elektronny_gorod"
    for name in ("strings.json", "translations/ru.json", "translations/en.json"):
        data = json.loads((base / name).read_text(encoding="utf-8"))
        for key in (
            "invite_requires_admin",
            "invite_operator_unsupported",
            "invite_not_a_place",
            "invite_request_failed",
            "invite_empty",
            "integration_not_loaded",
        ):
            assert data["exceptions"].get(key, {}).get("message"), f"{name}: {key}"
        service = data.get("services", {}).get(_SERVICE, {})
        assert service.get("name") and service.get("description"), name
        assert service.get("fields", {}).get("device_id", {}).get("name"), name


async def test_action_declares_response_only(hass) -> None:
    """Регистрация действия объявляет `SupportsResponse.ONLY`."""
    await _setup(hass)

    service = hass.services.async_services_for_domain(DOMAIN)[_SERVICE]
    assert service.supports_response is SupportsResponse.ONLY
