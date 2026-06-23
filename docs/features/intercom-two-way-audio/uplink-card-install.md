# Установка карты микрофона (uplink) + ручной тест

Phase C, механизм #1 ([ADR-0013](../../decisions/0013-uplink-mic-transport.md)).
Серверная часть (WS-команда `elektronny_gorod/intercom_uplink` + wiring `UplinkSink` +
дрейф-фикс `rtp.py`) — в коде. Карта раздаётся интеграцией статикой.

## Установка

1. Интеграция раздаёт карту по `/elektronny_gorod_static/eg-intercom-mic-card.js`
   (регистрируется автоматически в `async_setup_entry`).
2. Добавить ресурс: **Settings → Dashboards → ⋮ → Resources → Add resource**
   - URL: `/elektronny_gorod_static/eg-intercom-mic-card.js`
   - Type: **JavaScript Module**
3. На дашборд экрана вызова — карту:
   ```yaml
   type: custom:eg-intercom-mic-card
   title: Домофон — микрофон
   ```
   Рядом с `webrtc-camera` (downlink видео+звук гостя, Slice 1) — получается «трубка»:
   сверху видео+звук гостя, снизу кнопка «🎤 Говорить».

## Как работает (поток)

```
🎤 микрофон браузера (getUserMedia)
  → AudioWorklet (Float32 → Int16 PCM)
  → бинарный кадр [handler_id | PCM] по АВТОРИЗОВАННОМУ HA-WebSocket (тот же, что весь UI)
  → WS-команда elektronny_gorod/intercom_uplink → DoorbellCallController.feed_uplink
  → UplinkSink (resample 48к→8к + G.711 + джиттер-буфер)
  → SipManager.uplink_provider → RtpSession.run_uplink (дрейф-компенсированный) → RTP в домофон
```

Без go2rtc/TURN — едет по тому же WSS, что весь HA-UI (удалённо/4G ок). HTTPS-origin
обязателен (браузер даёт микрофон только на secure origin).

## Ручной тест (на проде, во время реального вызова)

1. Открыть экран вызова при активном вызове домофона (ответить через `elektronny_gorod.answer`).
2. Нажать «🎤 Говорить» → разрешить микрофон. Статус: «микрофон активен (48000 Гц → 8к G.711)».
3. Говорить → проверить, что слышно у домофонной панели.
4. «🔴 Остановить» (или закрыть вкладку — HA снимет binary-handler автоматически).

**Что проверять:**
- Кнопка появляется/работает; статус-строка без ошибок.
- Звук доходит до панели, разговорная латентность (дрейф-фикс убрал заикания из PoC).
- Если «Нет активного вызова» — карта/WS отработали, но вызова нет (WS-команда вернула
  `no_active_call`): нажимать во время активного отвеченного вызова.

**Тестовая среда (без домофона):** `research/intercom-call-probe/test_harness/` —
door-эмулятор со строгим латчингом валидирует SIP/RTP-тракт оффлайн
(`./test_harness/run_loopback.sh`). Серверный uplink-тракт покрыт юнит-тестами
(`test_uplink_ws.py`, `test_sip_uplink.py`, `test_sip_rtp.py`, `test_sip_call_controller.py`).

## Ограничения слайса

- Один одновременный разговор (фикс-порты SIP/RTP, first-answer-wins).
- Авто-старт микрофона по открытию экрана политикой автоплея браузера не гарантируется
  (нужен жест — нажатие кнопки). Это by-design.
- Hands-free (всегда открытый микрофон) — polish следующего слайса; сейчас кнопка-тумблер.
