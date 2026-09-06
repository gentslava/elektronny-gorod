"""Аудио-мост: жизненный цикл, раздача потока и остановка.

Чистая часть моста (аргументы ffmpeg, адрес источника) покрыта в
`test_sip_bridge.py`. Здесь — то, что раньше проверялось только живым звонком:
запуск, поведение при подключении и обрыве клиента, тишина-keepalive и
остановка процесса. Ровно тот слой, где отказ означает разговор без звука.
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.elektronny_gorod.sip import bridge as bridge_module
from custom_components.elektronny_gorod.sip.bridge import AudioBridge, detect_lan_ip

_MODULE = "custom_components.elektronny_gorod.sip.bridge"


def _proc(*, running: bool = True) -> MagicMock:
    """Поддельный ffmpeg: живой процесс со stdin и stdout."""
    proc = MagicMock()
    proc.returncode = None if running else 0
    proc.stdin = MagicMock()
    proc.stdin.is_closing.return_value = False
    proc.stdout = MagicMock()
    proc.stdout.read = AsyncMock(return_value=b"")
    proc.wait = AsyncMock(return_value=0)
    return proc


def _writer() -> MagicMock:
    writer = MagicMock()
    writer.is_closing.return_value = False
    writer.drain = AsyncMock()
    return writer


# ─── Адрес, по которому go2rtc дотянется до моста ───────────────────────────


def test_lan_ip_is_the_outbound_interface() -> None:
    """Берём адрес интерфейса, через который уходит наружу трафик."""
    sock = MagicMock()
    sock.getsockname.return_value = ("192.168.1.50", 12345)
    with patch(f"{_MODULE}.socket.socket", return_value=sock):
        assert detect_lan_ip() == "192.168.1.50"
    sock.close.assert_called_once()


def test_lan_ip_falls_back_when_there_is_no_network() -> None:
    """Без сети мост всё равно должен подняться — на петле.

    Иначе отсутствие маршрута наружу уронило бы приём вызова целиком, хотя
    go2rtc может жить на том же хосте.
    """
    sock = MagicMock()
    sock.connect.side_effect = OSError("нет маршрута")
    with patch(f"{_MODULE}.socket.socket", return_value=sock):
        assert detect_lan_ip() == "127.0.0.1"
    sock.close.assert_called_once()


# ─── Запуск и остановка ─────────────────────────────────────────────────────


async def _started_bridge(payload_type: int = 0) -> tuple[AudioBridge, MagicMock, MagicMock]:
    proc = _proc()
    server = MagicMock()
    with (
        patch(f"{_MODULE}.asyncio.create_subprocess_exec", AsyncMock(return_value=proc)),
        patch(f"{_MODULE}.asyncio.start_server", AsyncMock(return_value=server)),
    ):
        bridge = AudioBridge("192.168.1.100", 40020, payload_type=payload_type)
        await bridge.start()
    return bridge, proc, server


async def test_start_brings_up_process_server_and_loops() -> None:
    bridge, proc, server = await _started_bridge()
    try:
        assert bridge._proc is proc
        assert bridge._server is server
        assert bridge._broadcast is not None and bridge._keepalive is not None
    finally:
        await bridge.stop()


async def test_stop_terminates_everything_it_started() -> None:
    bridge, proc, server = await _started_bridge()
    broadcast, keepalive = bridge._broadcast, bridge._keepalive
    client = _writer()
    bridge._clients.add(client)

    await bridge.stop()
    # Отмена доезжает на следующем такте цикла.
    for _ in range(3):
        await asyncio.sleep(0)

    assert broadcast.done() and keepalive.done()
    server.close.assert_called_once()
    client.close.assert_called_once()
    proc.terminate.assert_called_once()
    assert bridge._proc is None and bridge._clients == set()


async def test_stop_kills_a_process_that_will_not_exit() -> None:
    """Если ffmpeg не завершился по-хорошему, его снимают принудительно.

    Иначе он остался бы держать порт, и следующий звонок не поднял бы мост.
    """
    bridge, proc, _server = await _started_bridge()
    proc.wait = AsyncMock(side_effect=TimeoutError)

    await bridge.stop()

    proc.kill.assert_called_once()


async def test_stop_without_start_is_harmless() -> None:
    """Отбой до поднятия моста не должен ничего ронять."""
    await AudioBridge("192.168.1.100", 40020, payload_type=0).stop()


# ─── Раздача потока клиенту ─────────────────────────────────────────────────


async def test_client_gets_the_stream_headers() -> None:
    """go2rtc подключается и получает mpegts-заголовки."""
    bridge, proc, _ = await _started_bridge()
    try:
        reader = MagicMock()
        reader.readuntil = AsyncMock(return_value=b"GET / HTTP/1.1\r\n\r\n")
        writer = _writer()
        proc.returncode = 0  # чтобы цикл ожидания завершился сразу

        await bridge._handle_client(reader, writer)

        headers = writer.write.call_args[0][0]
        assert b"200 OK" in headers and b"video/mp2t" in headers
        assert writer not in bridge._clients
    finally:
        await bridge.stop()


async def test_client_that_never_sends_a_request_is_still_served() -> None:
    """Пробы go2rtc без полного запроса тоже получают поток.

    go2rtc в ходе согласования подключается и отваливается несколько раз;
    отказ такой пробе означал бы разговор без звука.
    """
    bridge, proc, _ = await _started_bridge()
    try:
        reader = MagicMock()
        reader.readuntil = AsyncMock(side_effect=TimeoutError)
        writer = _writer()
        proc.returncode = 0

        await bridge._handle_client(reader, writer)

        assert b"200 OK" in writer.write.call_args[0][0]
    finally:
        await bridge.stop()


async def test_client_lost_before_headers_is_dropped() -> None:
    bridge, proc, _ = await _started_bridge()
    try:
        reader = MagicMock()
        reader.readuntil = AsyncMock(return_value=b"\r\n\r\n")
        writer = _writer()
        writer.drain = AsyncMock(side_effect=ConnectionResetError)

        await bridge._handle_client(reader, writer)

        assert writer not in bridge._clients
        writer.close.assert_called_once()
    finally:
        await bridge.stop()


async def test_stream_reaches_every_client() -> None:
    bridge, proc, _ = await _started_bridge()
    try:
        first, second = _writer(), _writer()
        bridge._clients.update({first, second})
        proc.stdout.read = AsyncMock(side_effect=[b"mpegts-chunk", b""])

        await bridge._broadcast_loop()

        first.write.assert_called_once_with(b"mpegts-chunk")
        second.write.assert_called_once_with(b"mpegts-chunk")
    finally:
        await bridge.stop()


async def test_stalled_client_is_dropped_not_waited_for() -> None:
    """Зависший потребитель выкидывается, а не задерживает остальных.

    Один медленный клиент иначе остановил бы раздачу всем — то есть один
    подвисший go2rtc обрывал бы звук разговора.
    """
    bridge, proc, _ = await _started_bridge()
    try:
        healthy, stalled = _writer(), _writer()
        stalled.drain = AsyncMock(side_effect=TimeoutError)
        bridge._clients.update({healthy, stalled})
        proc.stdout.read = AsyncMock(side_effect=[b"chunk", b""])

        await bridge._broadcast_loop()

        assert stalled not in bridge._clients
        assert healthy in bridge._clients
        stalled.close.assert_called_once()
    finally:
        await bridge.stop()


async def test_broadcast_without_process_returns() -> None:
    bridge = AudioBridge("192.168.1.100", 40020, payload_type=0)
    await bridge._broadcast_loop()


# ─── Кормление и тишина ─────────────────────────────────────────────────────


async def test_downlink_frame_reaches_ffmpeg() -> None:
    bridge, proc, _ = await _started_bridge()
    try:
        bridge.feed_downlink(b"guest-audio")
        proc.stdin.write.assert_any_call(b"guest-audio")
    finally:
        await bridge.stop()


@pytest.mark.parametrize(
    ("what", "break_it"),
    [
        ("процесс завершился", lambda proc: setattr(proc, "returncode", 1)),
        ("stdin закрыт", lambda proc: proc.stdin.is_closing.__setattr__(
            "return_value", True)),
        ("stdin отсутствует", lambda proc: setattr(proc, "stdin", None)),
    ],
)
async def test_feeding_a_dead_process_is_silent(what, break_it) -> None:
    """Кадр в мёртвый ffmpeg не должен ронять обработку звонка.

    Кадры приходят из RTP-потока домофона по двадцать в секунду; исключение
    здесь оборвало бы приём вызова целиком из-за уже мёртвого моста.
    """
    bridge, proc, _ = await _started_bridge()
    try:
        break_it(proc)
        bridge.feed_downlink(b"frame")
        if proc.stdin is not None:
            proc.stdin.write.assert_not_called()
    finally:
        await bridge.stop()


async def test_broken_pipe_while_feeding_is_swallowed() -> None:
    """Обрыв канала к ffmpeg не выбрасывает исключение в обработчик звонка."""
    bridge, proc, _ = await _started_bridge()
    try:
        proc.stdin.write.side_effect = BrokenPipeError
        bridge.feed_downlink(b"frame")
    finally:
        await bridge.stop()


@pytest.mark.parametrize(
    ("payload_type", "silence_byte"),
    [(0, 0xFF), (8, 0xD5)],
)
async def test_silence_matches_the_codec(payload_type, silence_byte) -> None:
    """Тишина у µ-law и A-law разная — иначе ffmpeg получит шум."""
    bridge, proc, _ = await _started_bridge(payload_type=payload_type)
    try:
        bridge._last_write = -100.0  # заведомо давно
        bridge._write(bridge._silence)
        written = proc.stdin.write.call_args[0][0]
        assert set(written) == {silence_byte}
        assert len(written) == 160, "кадр 20 мс при 8 кГц"
    finally:
        await bridge.stop()


async def test_keepalive_fills_pauses_with_silence() -> None:
    """В паузах downlink вход ffmpeg не должен пустеть.

    Иначе поток на выходе прерывается, и подключившийся клиент не получает
    заголовков для декодирования — звук у собеседника пропадает.
    """
    bridge, proc, _ = await _started_bridge()
    try:
        bridge._last_write = -100.0
        task = asyncio.get_running_loop().create_task(bridge._keepalive_loop())
        for _ in range(5):
            await asyncio.sleep(0)
        await asyncio.sleep(0.05)
        task.cancel()
        assert proc.stdin.write.called
    finally:
        await bridge.stop()


def test_closing_an_already_closed_client_is_harmless() -> None:
    writer = _writer()
    writer.is_closing.return_value = True
    bridge_module.AudioBridge._safe_close(writer)
    writer.close.assert_not_called()

    broken = _writer()
    broken.close.side_effect = OSError
    bridge_module.AudioBridge._safe_close(broken)


async def test_client_waits_while_the_stream_is_alive() -> None:
    """Клиент держится, пока жив ffmpeg — обрыв каждые полсекунды недопустим.

    go2rtc подключается один раз на разговор; переподключение стоит паузы в
    звуке, а мост как раз и сделан, чтобы её не было.
    """
    bridge, proc, _ = await _started_bridge()
    try:
        reader = MagicMock()
        reader.readuntil = AsyncMock(return_value=b"\r\n\r\n")
        writer = _writer()

        serving = asyncio.get_running_loop().create_task(
            bridge._handle_client(reader, writer)
        )
        for _ in range(3):
            await asyncio.sleep(0)
        assert writer in bridge._clients, "клиент должен быть в раздаче"

        proc.returncode = 0  # ffmpeg завершился — цикл ожидания выходит
        await asyncio.sleep(0.6)
        await serving

        assert writer not in bridge._clients
    finally:
        await bridge.stop()


async def test_stop_survives_a_broken_pipe_to_ffmpeg() -> None:
    """Закрытие уже оборванного канала не мешает остановке."""
    bridge, proc, _ = await _started_bridge()
    proc.stdin.close.side_effect = BrokenPipeError

    await bridge.stop()

    proc.terminate.assert_called_once()


async def test_stop_of_an_already_gone_process_is_harmless() -> None:
    """ffmpeg успел умереть сам — снимать нечего, падать не за что."""
    bridge, proc, _ = await _started_bridge()
    proc.terminate.side_effect = ProcessLookupError
    proc.kill.side_effect = ProcessLookupError

    await bridge.stop()
