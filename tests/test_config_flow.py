"""Config-flow tests (A-73 — Bronze IQS gate).

Покрывают три ветки аутентификации + go2rtc-меню + abort/reauth-кейсы.
API мокается на уровне namespace `config_flow.ElektronnyGorodAPI` (ленивый
`@property api` создаёт инстанс при первом обращении в step), поэтому сетевых
запросов к оператору нет.
"""
from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.elektronny_gorod.const import (
    DOMAIN,
    CONF_ACCESS_TOKEN,
    CONF_ACCOUNT_ID,
    CONF_CONTRACT,
    CONF_OPERATOR_ID,
    CONF_PHONE,
    CONF_PASSWORD,
    CONF_REFRESH_TOKEN,
    CONF_SMS,
    CONF_SUBSCRIBER_ID,
    CONF_USER_AGENT,
    CONF_USE_GO2RTC,
    CONF_GO2RTC_BASE_URL,
    CONF_GO2RTC_RTSP_HOST,
    CONF_GO2RTC_USERNAME,
    CONF_GO2RTC_PASSWORD,
)
from custom_components.elektronny_gorod.config_flow import ElektronnyGorodConfigFlow
from custom_components.elektronny_gorod.go2rtc import Go2RtcValidationResult


_PROFILE = {"subscriber": {"name": "Ivan", "accountId": "1131686", "id": 2104659}}
_AUTH = {"accessToken": "AT", "refreshToken": "RT", "operatorId": 1}
_CONTRACT = {"subscriberId": 2104659, "address": "Some St 1", "accountId": "1131686"}


@pytest.fixture
def mock_api() -> Generator[MagicMock, None, None]:
    """Мок ElektronnyGorodAPI в namespace config_flow (ленивый инстанс из @property)."""
    with patch(
        "custom_components.elektronny_gorod.config_flow.ElektronnyGorodAPI"
    ) as cls:
        api = cls.return_value
        api.query_contracts = AsyncMock()
        api.verify_password = AsyncMock(return_value=_AUTH)
        api.verify_sms_code = AsyncMock(return_value=_AUTH)
        api.request_sms_code = AsyncMock(return_value=None)
        api.query_profile = AsyncMock(return_value=_PROFILE)
        yield api


@pytest.fixture
def _mock_clientsession() -> Generator[None, None, None]:
    """Не создавать реальную aiohttp-сессию в go2rtc-step (см. test_options_flow)."""
    with patch(
        "custom_components.elektronny_gorod.config_flow.async_get_clientsession",
        return_value=MagicMock(),
    ):
        yield


def _existing_entry(hass: HomeAssistant, **overrides) -> MockConfigEntry:
    data = {
        CONF_NAME: "Ivan (1131686)",
        CONF_ACCOUNT_ID: "1131686",
        CONF_SUBSCRIBER_ID: 2104659,
        CONF_ACCESS_TOKEN: "OLD_AT",
        CONF_REFRESH_TOKEN: "OLD_RT",
        CONF_OPERATOR_ID: "1",
        CONF_USER_AGENT: '{"a":"b"}',
    }
    data.update(overrides)
    entry = MockConfigEntry(domain=DOMAIN, version=3, title=data[CONF_NAME], data=data)
    entry.add_to_hass(hass)
    return entry


async def test_user_phone_sms_happy(
    hass: HomeAssistant, mock_api: MagicMock, mock_setup_entry
) -> None:
    """phone → contract → sms → go2rtc-menu → skip → CREATE_ENTRY."""
    mock_api.query_contracts.return_value = {"password": False, "contracts": [_CONTRACT]}

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PHONE: "+79990000000"}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "contract"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_CONTRACT: "2104659"}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "sms"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_SMS: "1234"}
    )
    assert result["type"] == FlowResultType.MENU
    assert result["step_id"] == "go2rtc_menu"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "skip_go2rtc"}
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Ivan (1131686)"
    assert result["data"][CONF_ACCESS_TOKEN] == "AT"
    assert result["data"][CONF_USE_GO2RTC] is False
    mock_api.request_sms_code.assert_awaited_once()
    mock_api.verify_sms_code.assert_awaited_once()


async def test_user_phone_password_happy(
    hass: HomeAssistant, mock_api: MagicMock, mock_setup_entry
) -> None:
    """phone (password=True) → password → go2rtc-menu → skip → CREATE_ENTRY."""
    mock_api.query_contracts.return_value = {"password": True}

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PHONE: "+79990000000"}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "password"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: "hunter2"}
    )
    assert result["type"] == FlowResultType.MENU

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "skip_go2rtc"}
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_ACCESS_TOKEN] == "AT"
    mock_api.verify_password.assert_awaited_once()


async def test_user_access_token_advanced(
    hass: HomeAssistant, mock_api: MagicMock, mock_setup_entry
) -> None:
    """advanced mode: paste access_token → go2rtc-menu → skip → CREATE_ENTRY."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER, "show_advanced_options": True}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ACCESS_TOKEN: "PASTED_TOKEN"}
    )
    assert result["type"] == FlowResultType.MENU

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "skip_go2rtc"}
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_ACCESS_TOKEN] == "PASTED_TOKEN"


async def test_go2rtc_setup_valid(
    hass: HomeAssistant, mock_api: MagicMock, mock_setup_entry, _mock_clientsession
) -> None:
    """advanced token → go2rtc → validate ok → CREATE_ENTRY с go2rtc-данными."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER, "show_advanced_options": True}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ACCESS_TOKEN: "PASTED_TOKEN"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "go2rtc"}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "go2rtc"

    with patch(
        "custom_components.elektronny_gorod.config_flow.validate_go2rtc",
        new=AsyncMock(
            return_value=Go2RtcValidationResult(ok=True, error="", rtsp_host="127.0.0.1")
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_GO2RTC_BASE_URL: "http://127.0.0.1:1984",
                CONF_GO2RTC_USERNAME: "admin",
                CONF_GO2RTC_PASSWORD: "secret",
            },
        )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_USE_GO2RTC] is True
    assert result["data"][CONF_GO2RTC_RTSP_HOST] == "127.0.0.1"
    assert result["data"][CONF_GO2RTC_USERNAME] == "admin"


async def test_invalid_phone_shows_error(hass: HomeAssistant, mock_api: MagicMock) -> None:
    """Пустой phone → форма с error invalid_phone, без обращения к API."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PHONE: "   "}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {CONF_PHONE: "invalid_phone"}
    mock_api.query_contracts.assert_not_awaited()


async def test_abort_already_configured(
    hass: HomeAssistant, mock_api: MagicMock
) -> None:
    """Повтор по совпадающему access_token → abort already_configured."""
    _existing_entry(hass, access_token="PASTED_TOKEN")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER, "show_advanced_options": True}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ACCESS_TOKEN: "PASTED_TOKEN"}
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth_updates_entry_and_aborts(
    hass: HomeAssistant, mock_api: MagicMock
) -> None:
    """Совпадение name+account+subscriber (но иной токен) → обновление data + abort reauth_successful."""
    entry = _existing_entry(hass, access_token="OLD_AT")

    with patch.object(
        hass.config_entries, "async_reload", new=AsyncMock(return_value=True)
    ) as reload:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER, "show_advanced_options": True}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_ACCESS_TOKEN: "NEW_AT"}
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    # data обновлена свежим токеном.
    assert entry.data[CONF_ACCESS_TOKEN] == "NEW_AT"
    reload.assert_awaited_once()


# ─── Ветки ошибок: правило Silver `config-flow-test-coverage` ───────────────
#
# Пользователь ошибается чаще, чем делает всё правильно, и именно эти ветки
# решают, увидит он объяснение или пустую форму. Проверка их покрытия сразу
# нашла abort `no_contracts` без перевода — вместо текста показался бы ключ.


async def test_empty_access_token_shows_error(
    hass: HomeAssistant, mock_api: MagicMock
) -> None:
    """Пустой токен в расширенном режиме — форма с ошибкой, не падение."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER, "show_advanced_options": True}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ACCESS_TOKEN: "   "}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {CONF_ACCESS_TOKEN: "invalid_access_token"}


async def test_profile_failure_after_token_shows_error(
    hass: HomeAssistant, mock_api: MagicMock
) -> None:
    """Токен принят, но профиль не отдался — сообщение вместо трассировки."""
    mock_api.query_profile = AsyncMock(side_effect=ValueError("unauthorized"))

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER, "show_advanced_options": True}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ACCESS_TOKEN: "PASTED_TOKEN"}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {CONF_PHONE: "unauthorized"}


async def test_phone_without_contracts_shows_error(
    hass: HomeAssistant, mock_api: MagicMock
) -> None:
    """Номер известен оператору, но договоров нет."""
    mock_api.query_contracts.return_value = {"password": False, "contracts": []}

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PHONE: "+79990000000"}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {CONF_PHONE: "no_contracts"}


async def test_contracts_request_failure_shows_error(
    hass: HomeAssistant, mock_api: MagicMock
) -> None:
    """Оператор отказал на запросе договоров."""
    mock_api.query_contracts = AsyncMock(side_effect=ValueError("limit_exceeded"))

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PHONE: "+79990000000"}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {CONF_PHONE: "limit_exceeded"}


async def _to_password_step(hass: HomeAssistant, mock_api: MagicMock):
    mock_api.query_contracts.return_value = {"password": True}
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    return await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PHONE: "+79990000000"}
    )


async def test_empty_password_shows_error(
    hass: HomeAssistant, mock_api: MagicMock
) -> None:
    """Пустой пароль — снова форма пароля с ошибкой."""
    result = await _to_password_step(hass, mock_api)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: ""}
    )

    assert result["step_id"] == "password"
    assert result["errors"] == {CONF_PASSWORD: "invalid_password"}


async def test_password_rejected_shows_error(
    hass: HomeAssistant, mock_api: MagicMock
) -> None:
    """Оператор ответил без токена — пароль не подошёл."""
    mock_api.verify_password = AsyncMock(return_value={"operatorId": 1})

    result = await _to_password_step(hass, mock_api)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: "wrong"}
    )

    assert result["step_id"] == "password"
    assert result["errors"] == {CONF_PASSWORD: "invalid_password"}


async def test_password_request_failure_shows_error(
    hass: HomeAssistant, mock_api: MagicMock
) -> None:
    """Оператор отказал при проверке пароля."""
    mock_api.verify_password = AsyncMock(side_effect=ValueError("invalid_login"))

    result = await _to_password_step(hass, mock_api)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: "secret"}
    )

    assert result["errors"] == {CONF_PASSWORD: "invalid_login"}


async def _to_contract_step(hass: HomeAssistant, mock_api: MagicMock):
    mock_api.query_contracts.return_value = {"password": False, "contracts": [_CONTRACT]}
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    return await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PHONE: "+79990000000"}
    )


async def test_sms_request_failure_shows_error(
    hass: HomeAssistant, mock_api: MagicMock
) -> None:
    """Договор выбран, но SMS не ушла."""
    mock_api.request_sms_code = AsyncMock(side_effect=ValueError("limit_exceeded"))

    result = await _to_contract_step(hass, mock_api)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_CONTRACT: "2104659"}
    )

    assert result["step_id"] == "contract"
    assert result["errors"] == {CONF_CONTRACT: "limit_exceeded"}


async def _to_sms_step(hass: HomeAssistant, mock_api: MagicMock):
    result = await _to_contract_step(hass, mock_api)
    return await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_CONTRACT: "2104659"}
    )


async def test_empty_sms_code_shows_error(
    hass: HomeAssistant, mock_api: MagicMock
) -> None:
    """Пустой код — форма кода с ошибкой."""
    result = await _to_sms_step(hass, mock_api)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_SMS: ""}
    )

    assert result["step_id"] == "sms"
    assert result["errors"] == {CONF_SMS: "invalid_code"}


async def test_sms_code_rejected_shows_error(
    hass: HomeAssistant, mock_api: MagicMock
) -> None:
    """Оператор ответил без токена — код не подошёл."""
    mock_api.verify_sms_code = AsyncMock(return_value={"operatorId": 1})

    result = await _to_sms_step(hass, mock_api)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_SMS: "0000"}
    )

    assert result["errors"] == {CONF_SMS: "invalid_code"}


async def test_sms_verification_failure_shows_error(
    hass: HomeAssistant, mock_api: MagicMock
) -> None:
    """Оператор отказал при проверке кода."""
    mock_api.verify_sms_code = AsyncMock(side_effect=ValueError("invalid_code"))

    result = await _to_sms_step(hass, mock_api)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_SMS: "0000"}
    )

    assert result["errors"] == {CONF_SMS: "invalid_code"}


async def test_go2rtc_without_url_shows_error(
    hass: HomeAssistant, mock_api: MagicMock, _mock_clientsession
) -> None:
    """Настройка go2rtc без адреса — форма с ошибкой, оператор не дёргается."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER, "show_advanced_options": True}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ACCESS_TOKEN: "PASTED_TOKEN"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "go2rtc"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_GO2RTC_BASE_URL: ""}
    )

    assert result["step_id"] == "go2rtc"
    assert result["errors"] == {"base": "go2rtc_required_fields"}


async def test_go2rtc_validation_failure_shows_reason(
    hass: HomeAssistant, mock_api: MagicMock, _mock_clientsession
) -> None:
    """Причина отказа go2rtc доходит до пользователя как есть."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER, "show_advanced_options": True}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ACCESS_TOKEN: "PASTED_TOKEN"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "go2rtc"}
    )

    with patch(
        "custom_components.elektronny_gorod.config_flow.validate_go2rtc",
        new=AsyncMock(
            return_value=Go2RtcValidationResult(
                ok=False, error="go2rtc_auth_failed", rtsp_host=None
            )
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_GO2RTC_BASE_URL: "http://127.0.0.1:1984"}
        )

    assert result["errors"] == {"base": "go2rtc_auth_failed"}


async def test_unknown_contract_shows_error(
    hass: HomeAssistant, mock_api: MagicMock
) -> None:
    """Выбран договор, которого нет в списке."""
    result = await _to_contract_step(hass, mock_api)
    flow = hass.config_entries.flow._progress[result["flow_id"]]

    # Через форму такой ответ не пройдёт — `vol.In` отсечёт его раньше, — но
    # шаг обязан пережить и его: список договоров приходит от оператора и
    # между показом формы и ответом мог смениться.
    outcome = await flow.async_step_contract({CONF_CONTRACT: "999999"})
    assert outcome["errors"] == {CONF_CONTRACT: "invalid_contract"}

    outcome = await flow.async_step_contract({CONF_CONTRACT: ""})
    assert outcome["errors"] == {CONF_CONTRACT: "invalid_contract"}


async def test_first_step_offers_phone_and_token(
    hass: HomeAssistant, mock_api: MagicMock
) -> None:
    """Первый шаг спрашивает телефон и, для опытных, токен.

    Набор полей больше не зависит от `show_advanced_options`: ядро объявило
    свойство устаревшим и на всё время депрекации возвращает `True`, поэтому
    ветка «только телефон» была недостижима, а в HA 2027.6 обращение к
    свойству уронило бы config flow целиком.
    """
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER, "show_advanced_options": False}
    )

    assert result["step_id"] == "user"
    keys = {str(k) for k in result["data_schema"].schema}
    assert keys == {CONF_PHONE, CONF_ACCESS_TOKEN}


async def test_config_flow_avoids_deprecated_core_api() -> None:
    """`show_advanced_options` в коде не осталось.

    Ядро удаляет свойство в HA 2027.6. Это тот же класс поломки, что убрал
    `via_device` в 2026.9 и оставил установки без камер и замков.
    """
    import pathlib

    source = pathlib.Path(
        "custom_components/elektronny_gorod/config_flow.py"
    ).read_text(encoding="utf-8")
    # Ищем обращение, а не упоминание: объясняющий комментарий остаётся.
    assert "self.show_advanced_options" not in source


# ─── Защитные проверки внутреннего состояния ────────────────────────────────
#
# Через форму сюда не прийти: шаги вызываются по порядку и заполняют состояние
# сами. Но шаг обязан пережить и рассинхрон — например, если поток возобновили
# после перезапуска. Проверяем прямым вызовом, иначе эти ветки нельзя ни
# покрыть, ни доказать, что причина отказа переводится.


def _bare_flow(hass: HomeAssistant):
    flow = ElektronnyGorodConfigFlow()
    flow.hass = hass
    return flow


async def test_password_step_without_phone_aborts(hass: HomeAssistant) -> None:
    flow = _bare_flow(hass)
    result = await flow.async_step_password({CONF_PASSWORD: "secret"})
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "missing_phone"


async def test_contract_step_without_contracts_aborts(hass: HomeAssistant) -> None:
    flow = _bare_flow(hass)
    result = await flow.async_step_contract()
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "no_contracts"


async def test_sms_step_without_contract_aborts(hass: HomeAssistant) -> None:
    flow = _bare_flow(hass)
    result = await flow.async_step_sms({CONF_SMS: "1234"})
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "missing_contract"


async def test_account_step_without_token_aborts(hass: HomeAssistant) -> None:
    flow = _bare_flow(hass)
    result = await flow.get_account()
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "missing_access_token"


async def test_go2rtc_steps_without_entry_data_abort(hass: HomeAssistant) -> None:
    """Оба go2rtc-шага отказывают, если данные записи не собраны."""
    flow = _bare_flow(hass)
    skipped = await flow.async_step_skip_go2rtc()
    configured = await flow.async_step_go2rtc()

    assert skipped["reason"] == "missing_entry_data"
    assert configured["reason"] == "missing_entry_data"


async def test_abort_reasons_are_translated() -> None:
    """У каждой причины отказа есть текст во всех трёх файлах переводов.

    Без перевода Home Assistant показывает пользователю сырой ключ. Так и было
    с `no_contracts`, пока покрытие этих веток не довели до конца.
    """
    import json
    import pathlib
    import re

    base = pathlib.Path("custom_components/elektronny_gorod")
    used = set(re.findall(
        r'async_abort\(reason="([a-z_]+)"', (base / "config_flow.py").read_text()
    ))
    assert used, "не нашли ни одной причины отказа — проверка выродилась"

    for name in ("strings.json", "translations/ru.json", "translations/en.json"):
        data = json.loads((base / name).read_text(encoding="utf-8"))
        missing = sorted(used - set(data["config"].get("abort", {})))
        assert not missing, f"{name}: нет перевода для {missing}"


async def test_options_flow_requires_url_when_enabled(
    hass: HomeAssistant, _mock_clientsession
) -> None:
    """Включили go2rtc в настройках, но не указали адрес."""
    entry = _existing_entry(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_USE_GO2RTC: True, CONF_GO2RTC_BASE_URL: ""}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "go2rtc_required_fields"}

