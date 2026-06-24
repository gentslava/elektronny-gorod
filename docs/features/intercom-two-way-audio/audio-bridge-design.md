# Дизайн: аудио-мост two-way (sip.py ↔ go2rtc ↔ браузер)

- **Date:** 2026-06-23
- **Owner:** Vyacheslav Scherbinin
- **Status:** Approved (brainstorming 2026-06-23)
- **Предшествует:** [design.md](design.md) §3.2/§4/§6, [call-answer-model.md](call-answer-model.md)
- **Триггер:** SIP-приём вызова доказан live (домофон «Говорите», RTP-latching).
  Не хватает только аудио-эндпоинтов: гость не слышен, микрофон не доходит.

## 1. Цель и scope

Подключить аудио к уже работающему SIP-приёму: **гость слышен в браузере HA, а
микрофон браузера слышен в домофоне**. Переиспользуем go2rtc (транскод + WebRTC) и
`Advanced Camera Card` как «трубку». Строим **инкрементально**: Slice 1 — downlink
(слышать гостя), Slice 2 — uplink (говорить).

**Non-goals:** своя WebRTC-реализация (aiortc отвергнут — design §3.5), 2-way
домашней камеры, конференция/barge-in.

## 2. Контекст (подтверждено на прод-HA 2026-06-23)

- **go2rtc — отдельный контейнер** (standalone 1.9.4, свой `go2rtc.yaml`), не
  bundled-в-HA → риск design §6.6 («bundled блокирует exec через REST») **снят**:
  exec-источники доступны.
- **Карта 2-way уже стоит:** `Advanced Camera Card` (dermotduffy, v7.27.4) — умеет
  go2rtc-live с микрофоном. Внешняя зависимость AlexxIT/WebRTC (design §6.5) **не
  нужна**.
- **HA по HTTPS** (домен) → браузерный микрофон доступен (hard-gate для uplink).
- `SipManager` уже отдаёт `on_downlink(frame)` (G.711-кадры гостя) и зовёт
  `uplink_provider()` каждые 20мс (сейчас → тишина-keepalive).
- go2rtc-интеграция (`go2rtc.py`) уже делает upsert стримов через REST
  (`_go2rtc_upsert_stream`, PATCH→PUT fallback) — реюзаем.

## 3. Архитектура

```
Домофон ↔ SipManager (SIP/RTP G.711 — готово)
            │ on_downlink (кадры гостя)   ▲ uplink_provider (кадры микрофона)
            ▼                             │
     sip/bridge.py (новый, тонкий)  ←───→  go2rtc (standalone, транскод G.711↔Opus)
                                           │ WebRTC
                                           ▼
                 Advanced Camera Card (динамик + микрофон) = трубка

   Параллельно (есть, не трогаем): видео → go2rtc RTSP; сигнал → FCM event; дверь → lock.
```

go2rtc и карта уже есть — новое только тонкий **мост** между `SipManager` и go2rtc.

## 4. Компоненты и границы

| Компонент | Ответственность | Зависит от |
|---|---|---|
| `SipManager` (готов) | SIP/RTP G.711; `on_downlink(frame)`, `uplink_provider()` | — |
| **`sip/bridge.py`** (новый) | мост: downlink-кадры → go2rtc-источник; go2rtc-backchannel → uplink-кадры. Владеет локальным аудио-эндпоинтом (exec-pipe / RTP — финал на PoC). Буфер + пейсинг 20мс. Жизненный цикл = активный вызов | SipManager, go2rtc.py |
| `go2rtc.py` (расширить) | upsert/remove аудио-стрима вызова через REST (реюз `_go2rtc_upsert_stream`) | go2rtc REST |
| Advanced Camera Card (docs) | трубка: динамик + микрофон на go2rtc-стрим вызова | go2rtc, HTTPS |

`bridge.py` проектируется **изолированно**: чистые границы `feed_downlink(frame)` /
`next_uplink_frame()`, без знания SIP-деталей — тестируемо и переносимо (референс
для будущего go2rtc-порта на Go).

> **Примечание (P1-консолидация):** `go2rtc.py` становится **единым go2rtc-клиентом** —
> upsert/src/auth/url-логика консолидируется из `camera.py` (вынос
> `_go2rtc_upsert_stream` / `_build_go2rtc_src` + единые `_go2rtc_auth_header` /
> `_streams_url`; см. [plan-audio-downlink.md Task 2](plan-audio-downlink.md)).
> Аудио-методы (`upsert_audio_stream` / `remove_audio_stream`) строятся **поверх**
> этого клиента — без дублирования auth/url/security-guard. Дальнейший вынос
> go2rtc-transport из `camera.py` — backlog A-82 (см.
> [project-audit.md](../../audit/project-audit.md)).

## 5. Поток данных

- **Downlink:** домофон RTP → `SipManager.on_downlink` (G.711 PCMU) →
  `bridge.feed_downlink` → go2rtc-источник → WebRTC (Opus или passthrough) →
  динамик карты.
- **Uplink:** микрофон карты → WebRTC → go2rtc backchannel → `bridge` →
  `SipManager.uplink_provider` → домофон RTP (вместо тишины-keepalive).

## 6. Слайсы и acceptance

| Slice | Что | Проверяемый результат |
|---|---|---|
| **1 — downlink** | PoC **A(exec)** vs **B(нативный RTP)** на standalone go2rtc → выбрать тот, что чище заводится → мост кормит downlink в go2rtc → карта играет | ✅ **слышим гостя** в браузере |
| **2 — uplink** | PoC go2rtc backchannel (§6.5 риск) → мост кормит микрофон в `uplink_provider` | ✅ **полный разговор** |

**Механизм моста** (решение делегировано инженерному суждению): основной — **A
(go2rtc `exec`-источник**, проверенный паттерн aqara-doorbell/dahua-vto), **B
(нативный RTP/UDP-пиринг** sip.py⇄go2rtc) — fallback. Финал — по PoC Slice 1.

**Fallback uplink:** если exec-backchannel сломан (§6.5 send-only баг на этой версии
go2rtc) — задокументировать альтернативный путь подачи uplink (отдельный RTP-сокет,
который мост слушает, минуя exec-stdin) и решить в Slice 2.

## 6.1 PoC-результаты (D-audio-1, прод 2026-06-23)

Механизм downlink **валидирован на проде** (не теория):

- **Целевой go2rtc — Frigate-овский (`1984`)** — тот же, что интеграция уже
  использует для камер (создаёт там `ffmpeg:`-стримы через REST). Аудио туда же =
  единый go2rtc видео+звук, без дубля. Standalone go2rtc — исторический, не трогаем.
- 🔴 `exec:` через REST **заблокирован** (`insecure producer`) → exec отпадает
  (иначе рестарт Frigate). RTSP-publish в go2rtc — не принимается.
- ✅ `ffmpeg:<url>` через REST **разрешён** (камеры так и работают).
- Frigate-go2rtc в bridge-сети контейнера → мост в HA (host-net) для него **не на
  `127.0.0.1`**, а на **host-LAN-IP** (go2rtc уже ходит в LAN — eufy на .212).

**Выбранный механизм (вместо A-exec / B-RTP): `ffmpeg:http`-источник.**
Мост поднимает в HA **ffmpeg-субпроцесс** (муксинг отдаём ffmpeg, не хендроллим):
`ffmpeg -f mulaw -ar 8000 -ac 1 -i pipe:0 -c:a aac -f mpegts -listen 1
-multiple_requests 1 http://0.0.0.0:<port>`. SipManager `on_downlink` → пишет
G.711-кадры в stdin ffmpeg. На answer REST-создаём go2rtc-стрим
`src=ffmpeg:http://<host-lan-ip>:<port>#audio=opus`. go2rtc тянет, транскодит в
Opus, отдаёт в WebRTC → Advanced Camera Card.

**Доказано:** тон → ffmpeg-HTTP(host:9101) → go2rtc REST `ffmpeg:http://192.168.1.100:9101`
→ `Audio: opus, 48000 Hz` сквозь go2rtc (ffprobe). Цепочка работает на go2rtc интеграции.

**Качество/заметки:** двойной транскод G.711→AAC→Opus — для 8кГц-телефонии
перцептивно прозрачен, выбран ради робастности (mpegts не несёт G.711). Опция
оптимизации (одинарный транскод: ffmpeg→Opus/ogg passthrough) — если понадобится.
Адрес `host-lan-ip` (go2rtc→HA) — авто-детект primary LAN IP моста (как
`_outbound_ip` к публичному IP), не хардкод.

## 7. Жизненный цикл и обработка ошибок

- Мост + go2rtc-стрим создаются на `answer`, сносятся на `hangup`/BYE (**один
  активный вызов** — как сейчас в контроллере). Стрим — фикс-имя `eg_intercom_talk`.
- Сбой upsert go2rtc → log + **graceful degrade**: SIP-разговор на уровне транспорта
  живёт (latching, как сейчас), просто нет звука в браузере. Не валим приём вызова.
- Teardown моста на завершении — освобождает локальные сокеты/процесс, удаляет
  go2rtc-стрим (best-effort, как `cleanup_go2rtc_stream`).

## 8. Безопасность / приватность

- В go2rtc-конфиг **SIP-креды не попадают** — мост гоняет сырой G.711, не креды.
- Аудио идёт через go2rtc (уже доверенный для видео). Новых секретов нет.
- HTTPS уже есть (микрофон). go2rtc-креды уже в `SENSITIVE_KEYS`.

## 9. Тестирование

- **Unit:** пейсинг/буфер моста (чистая логика — джиттер-буфер, 20мс-такт);
  go2rtc audio-upsert/remove (mock REST — как `test_go2rtc_validate`/`_upsert`).
- **PoC/live:** звонок → слышим гостя (S1); говорим (S2). Сетевой мост — live, как
  `SipManager` (не юнит).
- Bug fix → тест (test-coverage rule).

## 10. Открытые PoC-вопросы (решаются в слайсах, не сейчас)

1. Точный механизм моста **A(exec) vs B(RTP)** — PoC Slice 1.
2. Cross-container сеть go2rtc↔HA (exec в go2rtc-контейнере должен дотянуться до
   sip.py / обмен RTP по UDP между контейнерами) — PoC Slice 1.
3. Жизнеспособность **exec-backchannel** на go2rtc 1.9.4 (§6.5) — PoC Slice 2.
4. Нужен ли транскод: go2rtc несёт PCMU/PCMA в WebRTC **нативно** — возможно
   passthrough без Opus (меньше CPU, меньше задержка) — проверить в PoC.

## 11. Влияние

- Новый модуль `sip/bridge.py`; расширение `go2rtc.py` (audio-stream upsert).
- `SipManager` wiring: на answer подключить `on_downlink`/`uplink_provider` к мосту.
- Docs: Advanced Camera Card config в README фичи; CHANGELOG; ADR-0012 (big change,
  на финале фичи).
- Existing entries / config-entry VERSION — не трогаем.

## Quality gate

`SPEC_READY` ✅ — переходим к плану (writing-plans).

## Связь

- [design.md](design.md) — целевая архитектура (§3.2 трубка, §4 flow, §6 развилки).
- [call-answer-model.md](call-answer-model.md) — модель приёма (готова, live 2026-06-23).
- [README.md](README.md) — статус фичи и слайсы.
