# Variant #3: exec-backchannel (scaffolding, НЕ ПРОВЕРЕНО LIVE)

> **ЭКСПЕРИМЕНТ** — scaffolding для сравнения с выбранным вариантом #1 (WS-binary).
> Нельзя тестировать без правки go2rtc.yaml и живого вызова из домофона.
> **НЕ деплоить автоматически — только вручную, по явному решению.**

## Принцип

```
[браузер/карта]  advanced-camera-card (кнопка mic) → WebRTC sendonly → go2rtc
[go2rtc]  exec: python exec_bridge.py #backchannel=1 #audio=alaw/8000
               → записывает backchannel-аудио (G.711 A-law) в stdin exec-процесса
[exec_bridge.py]  читает stdin → форвардит кадры в probe_push_answer (TCP 9988)
[probe_push_answer]  UPLINK_PROVIDER hook → RTP uplink G.711 → домофон
```

**Чем отличается от #1 (WS-binary):**
- Источник кадров: `go2rtc exec: stdin backchannel` (не HA-WebSocket).
- Кодек определяется go2rtc (#audio=alaw/8000 = PCMA G.711).
- Не требует своей Lovelace-карты (AlexxIT/advanced-camera-card с кнопкой mic).
- Требует правки go2rtc.yaml (через REST заблокирован — см. Блокеры).
- Требует TURN на 4G (WebRTC в карте идёт через go2rtc, не HA-WS).

## Файлы

| Файл | Назначение |
|---|---|
| `exec_bridge.py` | Exec-процесс: читает backchannel stdin → TCP-форвард в probe |
| `README.md` | Этот файл: runbook + точная go2rtc.yaml конфигурация + процедура live-теста |

## Блокеры

### 1. Правка go2rtc.yaml ОБЯЗАТЕЛЬНА (через REST невозможно)

Frigate-go2rtc (bundled) блокирует `exec:` через REST-источник с сообщением
`insecure producer` (хардкод в go2rtc `streams.go:Validate`). Единственный путь —
напрямую отредактировать `go2rtc.yaml`.

**Путь к файлу (прод-HA):**
```
ssh home.server
# go2rtc внутри HA container:
docker exec home-assistant-core-skdjyi-homeassistant-1 cat /config/go2rtc.yaml
# Или посмотреть где config:
docker inspect home-assistant-core-skdjyi-homeassistant-1 | grep -i go2rtc
```

Файл обычно: `/opt/homeassistant/config/go2rtc.yaml` или `/config/go2rtc.yaml`.

### 2. TURN-сервер для 4G

advanced-camera-card WebRTC идёт через go2rtc. Если клиент на 4G —
нужен TURN-сервер (настраивается в карте или go2rtc.yaml iceServers).

### 3. Upstream-баги go2rtc (known issues)

| Баг | Описание | Workaround |
|---|---|---|
| #2084 (send-only) | exec: stream с backchannel может не работать если go2rtc не согласовал двунаправленный аудио | `#audio=alaw/8000` явно указывает кодек |
| #1888 (multi-consumer) | несколько WebRTC-потребителей одного strea с backchannel могут конфликтовать | тестировать с одним потребителем |
| #1932 (кодек) | backchannel кодек по умолчанию может не совпасть с G.711 | **лечится `#audio=alaw/8000`** в exec-строке |

## Точная go2rtc.yaml конфигурация

> ⚠️ НЕ применять автоматически. Редактировать вручную после явного решения.

```yaml
# go2rtc.yaml — фрагмент для variant3 exec-backchannel
# Добавить к существующим streams (не удалять другие)

streams:
  # Существующий стрим камеры домофона (пример — имена могут отличаться)
  doorbell_front: rtsp://admin:password@192.168.1.XXX/stream1

  # Новый стрим для backchannel-микрофона
  # ЗАМЕНИ /path/to/exec_bridge.py на реальный путь внутри контейнера HA
  doorbell_backchannel:
    - exec:python3 /config/intercom-probe/variant3_exec/exec_bridge.py#backchannel=1#audio=alaw/8000
```

**Параметры exec-строки:**
- `#backchannel=1` — go2rtc запустит процесс при активном WebRTC-соединении с микрофоном.
- `#audio=alaw/8000` — явно задаём кодек A-law 8кГц (workaround #1932/#2084).

**После правки yaml** — перезапустить go2rtc (или весь HA):
```bash
# Внутри контейнера HA:
kill -HUP $(pgrep go2rtc)
# Или через HA Developer Tools → Services → homeassistant.restart
```

## Карта (AlexxIT/advanced-camera-card)

Вариант #3 использует готовую карту с кнопкой микрофона.

### Установка карты

Через HACS: `Frontend → AlexxIT/advanced-camera-card (aka go2rtc-webrtc)`.

### Конфигурация Lovelace

```yaml
# Lovelace card configuration (пример)
type: custom:advanced-camera-card
entity: camera.doorbell_front    # существующая camera entity
webrtc:
  url: 'ws://go2rtc:1984/api/ws?src=doorbell_front'
  # Для backchannel-микрофона:
  backchannel: true
  backchannel_url: 'ws://go2rtc:1984/api/ws?src=doorbell_backchannel'
  # TURN для 4G:
  iceServers:
    - urls: 'turn:your.turn.server:3478'
      username: user
      credential: password
```

> Точный синтаксис карты — проверить в документации AlexxIT/advanced-camera-card
> (версия может меняться). Поиск: `backchannel` в README карты.

## Процедура live-теста

> Выполнять только при наличии всех предварительных требований.
> НЕ в рабочее время (правка go2rtc.yaml затрагивает продакшн-стримы).

### Шаг 1: Скопировать exec_bridge.py в контейнер HA

```bash
# Из репозитория на хосте:
scp research/intercom-call-probe/variant3_exec/exec_bridge.py \
    home.server:/opt/homeassistant/config/intercom-probe/variant3_exec/

# Или через docker cp:
docker cp research/intercom-call-probe/variant3_exec/exec_bridge.py \
    home-assistant-core-skdjyi-homeassistant-1:/config/intercom-probe/variant3_exec/
```

### Шаг 2: Запустить probe_push_answer с TCP-приёмником

```bash
# На хосте разработчика (или в том же контейнере):
cd research/intercom-call-probe
export ANSWER=1 MIRROR_APP=1 RTP_EARLY=1
export INTERCOM_AC=<ac>
export BRIDGE_PORT=9988   # exec_bridge.py коннектится сюда
# TODO: добавить BRIDGE_PORT-приёмник в probe_push_answer или отдельный bridge-receiver
python probe_push_answer.py
```

> ⚠️ probe_push_answer.py текущей версии не имеет TCP-приёмника для BRIDGE_PORT.
> Нужно добавить `asyncio.start_server(bridge_handler, '0.0.0.0', BRIDGE_PORT)` в main().
> Это часть scaffolding — доделать при реальном тесте.

### Шаг 3: Добавить стрим в go2rtc.yaml

По конфигурации из раздела выше. Перезапустить go2rtc.

### Шаг 4: Настроить advanced-camera-card

По конфигурации Lovelace выше. Убедиться что кнопка микрофона видна.

### Шаг 5: Позвонить в домофон

1. Открыть Lovelace-карту.
2. Нажать кнопку микрофона в карте.
3. Позвонить в домофон (или дождаться входящего).
4. В логе probe: искать `[exec_bridge] forwarded N frames`.
5. Говорить — должно быть слышно у двери.

### Шаг 6: Оценить (критерии сравнения с #1)

| Метрика | #1 WS-binary (baseline) | #3 exec-backchannel (ожидание) |
|---|---|---|
| Латентность mic→дверь | ~ TBD (live) | доп. hop exec-процесс, ожидаем +50–150мс |
| Сложность инфры | нет go2rtc/yaml | правка yaml + карта + TURN |
| Upstream-баги | нет | #2084/#1888/#1932 |
| Своя карта | нужна | не нужна (advanced-camera-card) |
| Надёжность 4G | высокая (HA-WS) | зависит от TURN + upstream-багов |

Записать результат в `FINDINGS.md` (секция D-audio-variant3).

## Что НЕ протестировано без go2rtc + домофона

- Реальный запуск exec: go2rtc (проверка параметров #backchannel/#audio в yaml).
- Формат stdin (реальные байты от go2rtc, кодек, boundary).
- TCP-форвард exec_bridge.py → probe (нужен приёмник в probe_push_answer).
- Работа advanced-camera-card с `backchannel_url`.
- Upstream-баги: воспроизведение #2084/#1888 в конкретной версии go2rtc.

## Связь

- `docs/decisions/0013-uplink-mic-transport.md` — выбор #1, #3 отвергнут
- `docs/features/intercom-two-way-audio/uplink-mic-design.md` §4 — каталог механизмов
- `docs/features/intercom-two-way-audio/design.md` §6.5/§6.6 — exec-риски
- `research/intercom-call-probe/probe_mic_uplink.py` — рабочий вариант #1
- `research/intercom-call-probe/variant2_whip/` — вариант #2 (WHIP-pull)
- `docs/features/intercom-two-way-audio/variants-2-3-plan.md` — общий план сравнения
