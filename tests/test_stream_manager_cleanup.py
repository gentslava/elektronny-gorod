"""Снятие потоков go2rtc, когда камера перестала быть нужной.

Камеру скрывают в приложении оператора или отключают в Home Assistant — и
поток `eg_<id>` надо убрать. Но не любой ценой: если к нему кто-то ещё
подключён снаружи (Frigate, вторая вкладка), обрывать нельзя. Этот слой
раньше проверялся хуже остальных, а ошибка в нём либо оставляет мусор в
конфигурации go2rtc навсегда, либо рвёт чужой просмотр.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.elektronny_gorod.go2rtc import Go2RtcRequestError
from custom_components.elektronny_gorod.stream_manager import ManagedCameraState

from test_stream_manager import _manager


def _state(**overrides) -> ManagedCameraState:
    state = ManagedCameraState(
        camera_id="100", stream_name="eg_100", display_name="Front door"
    )
    for key, value in overrides.items():
        setattr(state, key, value)
    return state


def _info(*, consumers: int = 0, producer: bool = False) -> MagicMock:
    info = MagicMock()
    info.consumer_count = consumers
    info.producer_active = producer
    return info


# ─── Удаление потока ────────────────────────────────────────────────────────


async def test_deleted_stream_leaves_no_trace() -> None:
    manager, _, client = _manager()
    client.async_delete_stream = AsyncMock()
    state = _state(present=True, preloaded=True, consumer_count=3, producer_active=True)

    await manager._async_delete_stream(state)

    client.async_delete_stream.assert_awaited_once_with("eg_100")
    assert state.status == "excluded"
    assert not state.present and not state.preloaded and not state.producer_active
    assert state.consumer_count == 0 and not state.cleanup_pending


@pytest.mark.parametrize(
    ("failure", "expected_status"),
    [
        (Go2RtcRequestError("delete", "auth"), "delete_auth"),
        (RuntimeError("что-то неожиданное"), "delete_unexpected"),
    ],
)
async def test_failed_delete_is_retried_later(failure, expected_status) -> None:
    """Неудачное удаление помечается к повтору, а не забывается.

    Иначе поток остался бы в конфигурации go2rtc навсегда — ровно та проблема
    с раздуванием конфига, которая уже описана в аудите.
    """
    manager, _, client = _manager()
    client.async_delete_stream = AsyncMock(side_effect=failure)
    state = _state(present=True)

    await manager._async_delete_stream(state)

    assert state.status == expected_status
    assert state.cleanup_pending, "повтор потерян"
    assert state.present, "поток на месте — состояние врать не должно"


# ─── Мягкая уборка: свой прогрев снять, чужих не трогать ────────────────────


async def test_cleanup_drops_our_preload_first() -> None:
    """Сначала снимается наш прогрев — он и держит поток поднятым."""
    manager, _, client = _manager()
    client.async_disable_preload = AsyncMock()
    client.async_get_stream = AsyncMock(return_value=None)
    manager._owned_preloads.add("eg_100")
    state = _state(present=True, preloaded=True)

    await manager._async_cleanup_stream(state)

    client.async_disable_preload.assert_awaited_once_with("eg_100")
    assert not state.preloaded
    assert "eg_100" not in manager._owned_preloads


@pytest.mark.parametrize(
    ("failure", "expected_status"),
    [
        (Go2RtcRequestError("preload", "network"), "preload_disable_network"),
        (RuntimeError("неожиданно"), "preload_disable_unexpected"),
    ],
)
async def test_failed_preload_removal_stops_the_cleanup(failure, expected_status) -> None:
    """Не сняв свой прогрев, дальше идти нельзя — иначе снимем чужое."""
    manager, _, client = _manager()
    client.async_disable_preload = AsyncMock(side_effect=failure)
    client.async_get_stream = AsyncMock()
    state = _state(present=True, preloaded=True)

    await manager._async_cleanup_stream(state)

    assert state.status == expected_status
    assert state.cleanup_pending
    client.async_get_stream.assert_not_awaited()


async def test_cleanup_of_an_absent_stream_just_marks_it_gone() -> None:
    manager, _, client = _manager()
    client.async_get_stream = AsyncMock()
    state = _state(present=False, consumer_count=2, producer_active=True)

    await manager._async_cleanup_stream(state)

    assert state.status == "excluded"
    assert state.consumer_count == 0 and not state.producer_active
    client.async_get_stream.assert_not_awaited()


async def test_stream_gone_from_go2rtc_is_accepted() -> None:
    """Поток уже кто-то убрал — считаем задачу выполненной."""
    manager, _, client = _manager()
    client.async_get_stream = AsyncMock(return_value=None)
    state = _state(present=True)

    await manager._async_cleanup_stream(state)

    assert state.status == "excluded" and not state.present
    assert not state.cleanup_pending


async def test_external_viewer_keeps_the_stream_alive() -> None:
    """Чужой просмотр обрывать нельзя — уборка откладывается.

    Frigate или вторая вкладка держат тот же поток; снять его значило бы
    оборвать чужое видео посреди просмотра.
    """
    manager, _, client = _manager()
    client.async_get_stream = AsyncMock(return_value=_info(consumers=2, producer=True))
    state = _state(present=True)

    await manager._async_cleanup_stream(state)

    assert state.cleanup_pending, "уборку надо повторить позже"
    assert state.status == "cleanup_pending"
    assert state.consumer_count == 2 and state.producer_active


@pytest.mark.parametrize(
    ("failure", "expected_status"),
    [
        (Go2RtcRequestError("get", "timeout"), "cleanup_get_timeout"),
        (RuntimeError("неожиданно"), "cleanup_get_unexpected"),
    ],
)
async def test_unknown_stream_state_defers_the_cleanup(failure, expected_status) -> None:
    """Не зная, смотрит ли кто-то поток, снимать его нельзя."""
    manager, _, client = _manager()
    client.async_get_stream = AsyncMock(side_effect=failure)
    state = _state(present=True)

    await manager._async_cleanup_stream(state)

    assert state.status == expected_status
    assert state.cleanup_pending


# ─── Диагностические подписчики ─────────────────────────────────────────────


def test_broken_listener_does_not_break_the_refresh() -> None:
    """Сломанный подписчик не должен ронять обновление потоков.

    Подписчик здесь — сенсор диагностики; его ошибка не повод останавливать
    работу с камерами.
    """
    manager, _, _ = _manager()
    healthy = MagicMock()
    manager._listeners.add(lambda: (_ for _ in ()).throw(RuntimeError("сломался")))
    manager._listeners.add(healthy)

    manager._notify_listeners()

    healthy.assert_called_once()


# ─── Расписание и реакция на изменения в реестре ────────────────────────────


async def test_due_refresh_runs_when_the_camera_is_still_eligible() -> None:
    """Отложенное обновление срабатывает по сроку и снимает свою запись.

    Через него держатся живыми потоки внешних потребителей; не сработав, оно
    оставило бы поток мёртвым до следующей сверки.
    """
    from unittest.mock import patch as _patch

    manager, _, _ = _manager()
    manager._started = True
    manager.keep_warm = True
    manager.is_camera_eligible = MagicMock(return_value=True)
    manager.async_refresh = AsyncMock()

    with _patch(
        "custom_components.elektronny_gorod.stream_manager.async_call_later"
    ) as later:
        manager._schedule_due("100", 0)
        due = later.call_args.args[2]

    await due(None)

    manager.async_refresh.assert_awaited_once_with("100", "background_due")
    assert "100" not in manager._due_unsubs


async def test_due_refresh_skips_a_camera_that_became_ineligible() -> None:
    """Камеру успели скрыть — обновлять её по старому сроку не надо."""
    from unittest.mock import patch as _patch

    manager, _, _ = _manager()
    manager._started = True
    manager.keep_warm = True
    manager.is_camera_eligible = MagicMock(return_value=False)
    manager.async_refresh = AsyncMock()

    with _patch(
        "custom_components.elektronny_gorod.stream_manager.async_call_later"
    ) as later:
        manager._schedule_due("100", 0)
        due = later.call_args.args[2]

    await due(None)

    manager.async_refresh.assert_not_awaited()


async def test_reconcile_interval_skips_while_stopping() -> None:
    """Во время остановки сверка не запускается — гонка с teardown."""
    manager, _, _ = _manager()
    manager.async_reconcile = AsyncMock()
    manager._stopping = True

    await manager._async_reconcile_interval(None)

    manager.async_reconcile.assert_not_awaited()

    manager._stopping = False
    await manager._async_reconcile_interval(None)
    manager.async_reconcile.assert_awaited_once()


def test_registry_change_for_a_foreign_entity_is_ignored() -> None:
    """Изменение чужой сущности не тянет за собой сверку потоков."""
    from unittest.mock import MagicMock as MM

    manager, _, _ = _manager()
    manager._started = True

    manager._handle_registry_update(MM(data={"entity_id": "light.kitchen"}))

    assert manager._prompt_reconcile_unsub is None


def test_registry_change_before_start_is_ignored() -> None:
    manager, _, _ = _manager()
    manager._started = False

    manager._handle_registry_update(MagicMock(data={"entity_id": "camera.x"}))

    assert manager._prompt_reconcile_unsub is None


async def test_preload_failure_is_classified() -> None:
    """Неожиданный сбой прогрева не выпускает наружу детали транспорта."""
    manager, _, client = _manager()
    client.async_enable_preload = AsyncMock(side_effect=RuntimeError("сокет"))
    state = _state(present=True)

    assert await manager._async_enable_preload(state) is False
    assert state.status == "preload_unexpected"
    assert "сокет" not in state.status


async def test_patch_failure_falls_back_to_the_operator_url() -> None:
    """Неожиданный сбой go2rtc не оставляет камеру без видео.

    Прокси не поднялся — отдаём прямой адрес оператора: видео без звука
    лучше, чем чёрный прямоугольник.
    """
    manager, coordinator, client = _manager()
    client.async_patch_stream = AsyncMock(side_effect=RuntimeError("сокет"))

    result = await manager.async_refresh("100", "ha_open")

    assert result.url and not result.proxied
    assert manager._state_for("100").status == "patch_unexpected"
