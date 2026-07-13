# Варианты uplink-микрофона #2 и #3 — план сравнения

- **Дата:** 2026-06-24
- **Статус:** scaffolding готов; live-тест отложен (нет доступа к go2rtc/домофону)
- **Связь:** [uplink-mic-design.md](uplink-mic-design.md) §4, [ADR-0013](../../decisions/0013-uplink-mic-transport.md)

## Контекст

Выбранный механизм: **#1 WS-binary** (HA WebSocket binary-audio, ADR-0013).
Механизмы #2 и #3 отвергнуты на этапе ADR, но могут потребоваться для сравнения
или как fallback если #1 упрётся в ограничения. Scaffolding создан для быстрого
live-теста без повторного исследования.

## Что есть (scaffolding)

### Вариант #2 (WHIP-pull) — `research/intercom-call-probe/variant2_whip/`

| Файл | Статус |
|---|---|
| `probe_mic_whip.py` | scaffolding, синтаксис проверен, НЕ проверено live |
| `mic_whip.html` | scaffolding, НЕ проверено live |
| `README.md` | runbook + точная процедура live-теста |

**Принцип:** браузер → go2rtc WHIP-producer → ffmpeg RTSP-pull → G.711 → probe uplink.

### Вариант #3 (exec-backchannel) — `research/intercom-call-probe/variant3_exec/`

| Файл | Статус |
|---|---|
| `exec_bridge.py` | scaffolding, синтаксис проверен, НЕ проверено live |
| `README.md` | runbook + точная go2rtc.yaml конфигурация + процедура live-теста |

**Принцип:** go2rtc exec: → backchannel stdin → exec_bridge.py → probe uplink.

## Что нужно для live-теста

### Вариант #2 (WHIP-pull)

| Требование | Как получить |
|---|---|
| Существующий стрим go2rtc | `curl http://go2rtc:1984/api/streams` + имя стрима камеры домофона |
| go2rtc доступен из браузера | по HTTP(S) с токеном если auth включён |
| TURN-сервер (для 4G) | раскомментировать `iceServers` в `mic_whip.html` |
| ffmpeg в PATH | apt/brew install ffmpeg (или в Docker) |
| probe_push_answer запущен | `ANSWER=1 MIRROR_APP=1 RTP_EARLY=1` |

Подробнее — `variant2_whip/README.md §Процедура live-теста`.

### Вариант #3 (exec-backchannel)

| Требование | Как получить |
|---|---|
| Доступ к go2rtc.yaml | ssh home.server + путь к config в контейнере |
| Правка go2rtc.yaml | точная конфигурация в `variant3_exec/README.md §go2rtc.yaml` |
| advanced-camera-card | установить через HACS |
| TURN-сервер (для 4G) | настроить в карте / go2rtc.yaml |
| exec_bridge.py в контейнере | скопировать (инструкция в README) |
| TCP-приёмник в probe | доработать probe_push_answer (см. TODO в README варианта) |

Подробнее — `variant3_exec/README.md §Процедура live-теста`.

## Критерии сравнения с #1

| Метрика | #1 WS-binary | #2 WHIP-pull | #3 exec-backchannel |
|---|---|---|---|
| Источник кадров | HA-WebSocket binary | go2rtc RTSP-pull (ffmpeg) | go2rtc exec: stdin |
| go2rtc/yaml нужны? | Нет | Почти (стрим-таргет) | Да (yaml + exec:) |
| TURN на 4G? | Нет (HA-WS 443/WSS) | Да (WHIP ICE) | Да (WebRTC в карте) |
| Своя Lovelace-карта? | Да (WS-binary) | Да (WHIP-publish) | Нет (advanced-camera-card) |
| Upstream-баги go2rtc | Нет | Нет (#2 обходит insecure-гейт) | #2084/#1888/#1932 |
| Дополнительный hop | Нет | ffmpeg RTSP-pull | exec-процесс + TCP |
| Ожидаемая латентность | baseline | +100–300мс (RTSP bufer) | +50–150мс (pipe) |
| Надёжность 4G | Высокая | Зависит от TURN | Зависит от TURN |

## Когда тестировать

Live-тест #2/#3 оправдан если:
1. **#1 не прошёл production-валидацию** (голос не доходит до двери с реальной интеграцией).
2. **Требование «готовая карта»**: пользователь не хочет кастомную Lovelace-карту → #3.
3. **Latency-тест**: требуется сравнить реальные задержки #1 vs #2 vs #3.

Решение о live-тесте принимать явно (не автоматически). Фиксировать в ADR-0013.

## Ограничения scaffolding

Не проверено без go2rtc + домофона:
- **#2**: реальный WHIP ICE negotiation, go2rtc mix downlink+uplink в RTSP,
  кодек в RTSP-потоке (Opus vs PCM).
- **#3**: реальный exec: запуск go2rtc, формат backchannel stdin,
  TCP-форвард exec_bridge → probe (нужен приёмник в probe_push_answer).
- Оба: latency measurement на 4G, underrun-статистика.

Синтаксис Python проверен (`python3 -m py_compile`).

## Связь

- `research/intercom-call-probe/probe_mic_uplink.py` — рабочий #1 (baseline)
- `research/intercom-call-probe/variant2_whip/README.md` — runbook #2
- `research/intercom-call-probe/variant3_exec/README.md` — runbook #3
- `docs/decisions/0013-uplink-mic-transport.md` — ADR выбора #1
- `docs/features/intercom-two-way-audio/uplink-mic-design.md` §4 — каталог механизмов
- `research/intercom-call-probe/FINDINGS.md` — сюда записывать результаты live-тестов
