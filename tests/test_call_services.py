"""Сервисы ответа и отбоя должны отказывать внятно.

Успешно завершиться, ничего не сделав, — значит соврать вызывающему.
Автоматизация не отличит ответ на звонок от промаха по времени, а человек в
интерфейсе не поймёт, почему кнопка молчит. Тот же класс, что кнопка
«Закрыть» у замка, и то же правило Silver `action-exceptions`.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

from custom_components.elektronny_gorod import (
    SERVICE_ANSWER,
    SERVICE_HANGUP,
    _async_register_sip_services,
)
from custom_components.elektronny_gorod.const import DOMAIN

_SIP_DATA = f"{DOMAIN}_sip"


def _controller(*, ringing: bool = False, live: bool | None = None) -> MagicMock:
    """Дублёр контроллера.

    `ringing` — открыто ли окно ответа (это и решает, кому отвечать).
    `live` — есть ли что снимать при отбое. По умолчанию совпадает с
    `ringing`, но их можно развести: у отвеченного разговора окно ответа
    давно истекло, а снимать есть что — мост и микрофон работают.
    """
    controller = MagicMock()
    controller.current_call.return_value = object() if ringing else None
    controller.async_answer = AsyncMock(return_value=True)
    controller.async_hangup = AsyncMock(
        return_value=ringing if live is None else live
    )
    return controller


def _register(hass: HomeAssistant, *controllers: MagicMock) -> None:
    hass.data[_SIP_DATA] = {f"entry-{i}": c for i, c in enumerate(controllers)}
    _async_register_sip_services(hass)


@pytest.mark.parametrize("service", [SERVICE_ANSWER, SERVICE_HANGUP])
async def test_service_refuses_without_active_call(
    hass: HomeAssistant, service: str
) -> None:
    """Нет вызова вовсе — отказ с причиной, а не тишина."""
    controller = _controller(ringing=False, live=False)
    _register(hass, controller)

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(DOMAIN, service, {}, blocking=True)

    assert err.value.translation_key == "no_active_call"
    assert controller.async_answer.await_count == 0


async def test_hangup_ends_a_conversation_past_the_answer_window(
    hass: HomeAssistant,
) -> None:
    """Разговор завершается и после того, как окно ответа истекло.

    Дедлайн приходит от оператора при звонке и на ответ не продлевается, а
    разговор живёт до страховки в две минуты. Отбой, спрашивающий «идёт ли
    вызов» вместо «есть ли что снимать», отказывался завершать живой
    разговор — с открытым микрофоном, до срабатывания страховки.
    """
    talking = _controller(ringing=False, live=True)
    _register(hass, talking)

    await hass.services.async_call(DOMAIN, SERVICE_HANGUP, {}, blocking=True)

    talking.async_hangup.assert_awaited_once()


async def test_answer_picks_the_ringing_intercom(hass: HomeAssistant) -> None:
    """Отвечаем тому домофону, который звонит, а не первому попавшемуся."""
    silent = _controller(ringing=False)
    ringing = _controller(ringing=True)
    _register(hass, silent, ringing)

    await hass.services.async_call(DOMAIN, SERVICE_ANSWER, {}, blocking=True)

    ringing.async_answer.assert_awaited_once()
    assert silent.async_answer.await_count == 0


async def test_hangup_asks_every_controller(hass: HomeAssistant) -> None:
    """Отбой спрашивает все контроллеры: снимать умеет только каждый сам.

    Судить снаружи о том, есть ли что снимать, нельзя — именно на этом и
    строилась регрессия.
    """
    idle = _controller(ringing=False, live=False)
    talking = _controller(ringing=False, live=True)
    _register(hass, idle, talking)

    await hass.services.async_call(DOMAIN, SERVICE_HANGUP, {}, blocking=True)

    idle.async_hangup.assert_awaited_once()
    talking.async_hangup.assert_awaited_once()


async def test_refusal_message_is_translated() -> None:
    """У отказа есть текст во всех трёх файлах переводов."""
    import json
    import pathlib

    base = pathlib.Path(__file__).resolve().parent.parent / "custom_components/elektronny_gorod"
    for name in ("strings.json", "translations/ru.json", "translations/en.json"):
        data = json.loads((base / name).read_text(encoding="utf-8"))
        exceptions = data.get("exceptions", {})
        for key in ("no_active_call", "integration_not_loaded"):
            assert exceptions.get(key, {}).get("message"), f"{name}: {key}"


async def test_services_exist_before_any_entry_is_loaded(hass: HomeAssistant) -> None:
    """Действия существуют до загрузки записи.

    Правило Bronze `action-setup`. Иначе автоматизация, ссылающаяся на
    `answer`, падает при проверке с «сервис не найден», и человек ищет
    ошибку у себя, хотя дело в недоступной интеграции.
    """
    from custom_components.elektronny_gorod import async_setup

    assert await async_setup(hass, {}) is True

    assert hass.services.has_service(DOMAIN, SERVICE_ANSWER)
    assert hass.services.has_service(DOMAIN, SERVICE_HANGUP)


@pytest.mark.parametrize("service", [SERVICE_ANSWER, SERVICE_HANGUP])
async def test_service_without_any_entry_names_the_real_reason(
    hass: HomeAssistant, service: str
) -> None:
    """Без загруженных записей причина названа своя, а не «нет вызова».

    Раз действие существует всегда, отказ «сейчас нет входящего вызова»
    отправил бы человека искать пропущенный звонок вместо выгруженной
    интеграции.
    """
    from custom_components.elektronny_gorod import async_setup

    await async_setup(hass, {})

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(DOMAIN, service, {}, blocking=True)

    assert err.value.translation_key == "integration_not_loaded"


async def test_actions_survive_the_unload_of_the_last_entry(
    hass: HomeAssistant,
) -> None:
    """Действия переживают выгрузку последней записи.

    Регистрация живёт в `async_setup`, а его Home Assistant зовёт один раз за
    запуск: домен уже в `hass.config.components`, и при повторной загрузке
    записи туда не возвращается. Снимать сервисы на выгрузке последней записи
    означало бы, что после смены опций, переавторизации или «Перезагрузить»
    кнопки экрана вызова отвечают «сервис не найден» до перезапуска HA.
    """
    from custom_components.elektronny_gorod import async_setup, async_unload_entry

    await async_setup(hass, {})
    entry = MagicMock()
    entry.entry_id = "entry-1"
    controller = _controller(ringing=True)
    hass.data[_SIP_DATA] = {entry.entry_id: controller}

    with patch.object(
        hass.config_entries,
        "async_unload_platforms",
        new=AsyncMock(return_value=True),
    ):
        assert await async_unload_entry(hass, entry) is True

    controller.async_hangup.assert_awaited_once()
    assert hass.services.has_service(DOMAIN, SERVICE_ANSWER)
    assert hass.services.has_service(DOMAIN, SERVICE_HANGUP)


async def test_yaml_configuration_is_rejected_rather_than_ignored(
    hass: HomeAssistant, caplog
) -> None:
    """Блок `elektronny_gorod:` в `configuration.yaml` не проходит молча.

    Интеграция настраивается только через интерфейс. Без схемы такой блок
    игнорировался бы без единого слова, и человек ждал бы от него эффекта.
    Ядро на такой блок не бросает, а пишет в журнал и заводит проблему в
    «Ремонте» — проверяем именно это, а не отказ схемы.
    """
    import logging

    from homeassistant.helpers import issue_registry as ir

    from custom_components.elektronny_gorod import CONFIG_SCHEMA

    assert CONFIG_SCHEMA({}) == {}

    with caplog.at_level(logging.ERROR):
        CONFIG_SCHEMA({DOMAIN: {"phone": "+70000000000"}})

    assert "does not support YAML setup" in caplog.text
    assert any(
        issue.issue_id.endswith(DOMAIN)
        for issue in ir.async_get(hass).issues.values()
    ), "проблема в «Ремонте» не заведена"
