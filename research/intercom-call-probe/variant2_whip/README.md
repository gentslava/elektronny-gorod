# Variant #2: WHIP-pull (go2rtc-хоп проверен 2026-06-24)

> **ЭКСПЕРИМЕНТ** — scaffolding для сравнения с выбранным вариантом #1 (WS-binary).
> **Обновление 2026-06-24:** go2rtc-хоп (WHIP-ingest → RTSP-out) **проверен на живом
> изолированном тестовом go2rtc — РАБОТАЕТ** (тон дошёл, mean −24 dB). Полный путь с
> домофоном на 4G всё ещё требует TURN + проброс 8555. См. эмпирику и сводку в
> [`../FINDINGS.md`](../FINDINGS.md) §«D-audio-variants». Продакшн-go2rtc не трогать.

## Принцип

```
[браузер]  getUserMedia → RTCPeerConnection (audio sendonly, Opus)
               → POST go2rtc/api/webrtc?dst=<stream>   (WHIP-publish)
[go2rtc]   принимает Opus как producer → раздаёт по RTSP
[probe_mic_whip.py]  ffmpeg rtsp://go2rtc:8554/<stream> → PCM 8кГц
               → _Sink (lin2ulaw/alaw) → UPLINK_PROVIDER hook
[probe_push_answer]  uplink-кадры → RTP G.711 → домофон
```

**Чем отличается от #1 (WS-binary):**
- Источник кадров: `go2rtc RTSP-pull` (не HA-WebSocket).
- Микрофон идёт через go2rtc WebRTC-producer → RTSP-consumer path.
- Требует TURN-сервер на 4G (WHIP ICE traversal не через HA-WS).
- Требует существующий стрим-таргет в go2rtc.

## Файлы

| Файл | Назначение |
|---|---|
| `probe_mic_whip.py` | Основная проба: ffmpeg RTSP-pull → sink → UPLINK_PROVIDER |
| `mic_whip.html` | Браузерная страница: getUserMedia → WHIP-publish в go2rtc |
| `README.md` | Этот файл: runbook + процедура live-теста |

## Предварительные требования (блокеры)

### 1. Существующий стрим go2rtc (критический блокер)

`go2rtc ?dst=<stream>` НЕ создаёт стрим автоматически — `streams.Get` вернёт 404
если стрима нет. Нужен один из вариантов:

**Вариант A (рекомендуется): использовать стрим камеры домофона из Frigate**
```
# Проверить доступные стримы:
curl http://go2rtc:1984/api/streams
# Взять имя стрима камеры домофона (напр. doorbell_front)
export GO2RTC_STREAM=doorbell_front
```

**Вариант B: добавить 1 строку в go2rtc.yaml (требует доступа к yaml)**
```yaml
# go2rtc.yaml (фрагмент)
streams:
  doorbell_mic: {}   # пустой стрим — producer зарегистрирует браузер
```
После правки yaml go2rtc перезапустить (или reload через API).

### 2. TURN-сервер для 4G

WHIP ICE negotiation требует TURN при NAT (4G телефон → go2rtc за firewall).
В `mic_whip.html` закомментирован блок `iceServers` — раскомментировать и вставить
TURN-адрес перед тестом с телефона:
```js
iceServers: [{ urls: 'turn:your.turn.server:3478', username: 'u', credential: 'p' }],
```

### 3. go2rtc доступен из браузера

Браузер делает `fetch(go2rtcUrl + '/api/webrtc?dst=...')` — go2rtc должен быть
доступен по HTTP(S) из браузера. Если go2rtc за Traefik/auth — нужен токен (GO2RTC_TOKEN).

## Процедура live-теста

> Выполнять только при наличии всех предварительных требований. НЕ в рабочее время
> (go2rtc общий, добавление producer в стрим камеры — временное, но видно другим).

### Шаг 1: Проверить стрим

```bash
curl http://<go2rtc-host>:1984/api/streams
# → убедиться что <GO2RTC_STREAM> есть в списке
```

### Шаг 2: Запустить probe

```bash
cd research/intercom-call-probe
export GO2RTC_HOST=<go2rtc-host>    # напр. home.server
export GO2RTC_PORT=8554              # RTSP-порт go2rtc
export GO2RTC_STREAM=doorbell_front  # существующий стрим
export GO2RTC_TOKEN=                 # Bearer если auth
export WHIP_PORT=8766
# harness env (см. probe_push_answer.py):
export ANSWER=1 MIRROR_APP=1 RTP_EARLY=1
export INTERCOM_AC=<ac>              # ID домофона

pip install aiohttp  # если не установлено
python variant2_whip/probe_mic_whip.py
```

Лог пишется в `logs/push_answer.log`.

### Шаг 3: Открыть браузерную страницу

- Локально (хост): `http://localhost:8766/`
- Публично с 4G: через cloudflared или ngrok (HTTPS = secure origin для getUserMedia):
  ```bash
  docker run --rm --network host cloudflare/cloudflared:latest tunnel --url http://localhost:8766
  ```

### Шаг 4: Проверить WHIP-publish

1. Ввести go2rtc URL и имя стрима в `mic_whip.html`.
2. Нажать «Publish mic to go2rtc» — браузер отправит WHIP-offer.
3. Ожидаемый ответ: `200 OK` + SDP answer от go2rtc.
4. Проверить в логе probe: `ffmpeg | ...` строки с RTSP.

**Если 404:** стрим не существует → создай (см. Блокер 1).  
**Если ICE failed:** нет TURN → проверь TURN-конфиг (Блокер 2).

### Шаг 5: Позвонить в домофон

После успешного WHIP-publish: позвонить в домофон.
Probe ответит (FCM → SIP → 200 OK → RTP uplink).
В логе искать: `RTP[+Ns]: downlink=N` + отсутствие underrun-спайков.

### Шаг 6: Оценить (критерии сравнения с #1)

| Метрика | #1 WS-binary (baseline) | #2 WHIP-pull (ожидание) |
|---|---|---|
| Латентность mic→дверь | ~ TBD (live) | доп. hop ffmpeg+RTSP, ожидаем +100–300мс |
| Underrun / 10с | < 5 (D-audio-2) | TBD |
| Сложность инфры | нет go2rtc/TURN | стрим-таргет + TURN на 4G |
| Надёжность 4G | высокая (HA-WS) | зависит от TURN |

Записать результат в `FINDINGS.md` (секция D-audio-variant2).

## Известные ограничения / вопросы

1. **Микс downlink + uplink в RTSP**: при WHIP-publish браузер становится producer
   к существующему стриму камеры. Не ясно, добавляет ли go2rtc аудио-producer к
   видео-consumer или создаёт отдельный audio-track. Нужно проверить SDP от go2rtc.

2. **go2rtc bag #2084 (send-only)**: актуален для exec-backchannel (#3), не для #2.
   Но общий вопрос go2rtc audio-routing применим.

3. **Кодек в RTSP**: ffmpeg декодирует что есть. Если go2rtc раздаёт Opus в RTSP —
   ffmpeg перекодирует в PCM s16le (норм). Если PCMU — audioop тоже справится.

4. **WHIP ICE на 4G**: без TURN ICE не пройдёт через симметричный NAT 4G-оператора.
   #1 этой проблемы не имеет (HA-WS через 443/WSS).

5. **Авторизация WHIP**: go2rtc принимает WHIP без токена если auth выключен.
   Если включён — нужен Bearer, передаётся из mic_whip.html.

## Связь

- `docs/decisions/0013-uplink-mic-transport.md` — выбор #1, #2 отвергнут
- `docs/features/intercom-two-way-audio/uplink-mic-design.md` §4 — каталог механизмов
- `research/intercom-call-probe/probe_mic_uplink.py` — рабочий вариант #1
- `research/intercom-call-probe/variant3_exec/` — вариант #3 (exec-backchannel)
- `docs/features/intercom-two-way-audio/variants-2-3-plan.md` — общий план сравнения
