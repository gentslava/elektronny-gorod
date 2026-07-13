# ADR-0012: Register-on-ring (held-short-window) для приёма вызова

- **Status:** accepted
- **Date:** 2026-06-23
- **Owner:** SIP / two-way audio

## Context

Приём вызова домофона работает по модели **register-on-answer** (ADR ранее,
[`call-answer-model.md`](../features/intercom-two-way-audio/call-answer-model.md)):
регистрируемся в SIP **только** когда пользователь жмёт «Ответить» → REGISTER →
forked INVITE → `200 OK`. До этого SIP-присутствия нет — экран вызова в HA ведётся
по FCM-пушу `CALL_INCOMING`, а закрывается по **таймеру** `CallInvalidated` (~30с).

**Проблема (запрос пользователя):** когда звонок **сбрасывают с панели** до ответа,
приложение «Электронный город» гасит экран **мгновенно** (<1с), а HA держит мёртвый
экран до истечения 30с-таймера. Экран без живого вызова бесполезен — ответить уже
нельзя.

**Diagnostic evidence (pcap реального приложения, `captures/panel_drop.pcap`,
2026-06-23):** оператор отдельного end-FCM на сброс с панели **не шлёт** (подтверждает
[`research/.../FINDINGS.md`](../../research/intercom-call-probe/FINDINGS.md)). Приложение
узнаёт о сбросе по **SIP `CANCEL`**:

```
[ 0.49s] SRV → APP   INVITE (forked, SDP)        ← «звонит» по SIP
[ 0.52s] APP → SRV   100 Trying                  ← держит, без 180/200
   … ~11с не отвечаю …
[11.33s] SRV → APP   CANCEL                       ← СБРОС С ПАНЕЛИ
[11.35s] APP → SRV   200 OK (CANCEL) + 487 Request Terminated (INVITE)
```

Приложение SIP-зарегистрировано во время ring (held/push-wake), получает forked
INVITE и на сброс — `CANCEL`→`487` → мгновенный dismiss. Мы этого не получаем, т.к.
регистрируемся только на ответ.

**Повторная верификация 2026-07-13:** полный PCAP штатного Android-приложения
устранил прежнюю неоднозначность. Во всех трёх вызовах приложение выполняло
`REGISTER → INVITE → 100 Trying`; два неотвеченных INVITE держались около 24 секунд,
третий был принят `200 OK` через 4.27 секунды. Значит register-on-ring — не только
способ получить `CANCEL`, а точная pre-answer модель приложения.

## Decision

Перейти на **register-on-ring (held-short-window)** — зеркало приложения:

1. На FCM `CALL_INCOMING` (ring) сразу `mint → REGISTER → принять forked INVITE →
   100 Trying`, **держать** (НЕ `200 OK`).
2. «Ответить» → `200 OK` на уже держимый INVITE (быстро, без round-trip
   mint→register) → RTP/мост — как раньше.
3. Приём `CANCEL` (сброс с панели) → `200 OK` (CANCEL) + `487` (INVITE) →
   событие dismiss → экран гаснет мгновенно.
4. Истёк `CallInvalidated` / ответ на другом устройстве → release held-сессии.

### Расщепление `SipManager.async_answer` (монолит → фазы)

- `register_and_hold(mint_creds) -> bool` — REGISTER → INVITE → `100 Trying`, hold.
- `accept(on_downlink) -> bool` — `200 OK` на held-INVITE → RTP latching.
- `_on_cancel` (новый колбэк, отдельно от `on_bye`) — `487` + уведомление контроллера.

`sip/protocol.py`: разделить `CANCEL` и `BYE` (сейчас оба → `_respond_200`+`on_bye`);
на `CANCEL` дополнительно слать `487` на held-INVITE; добавить `send_trying` (100).

### Fallback-безопасность (не регрессировать проверенный приём)

Сервис `answer` сперва пробует `accept` held-INVITE; если held **не поднялся /
истёк** → откат на текущий `register-on-answer`. Так приём вызова не ломается, даже
если held-фаза не сработала. Register-on-ring — **усиление**, не замена с разрывом.

### Surface assumptions (утверждены, проверяем live)

1. Провизорный ответ — **`100 Trying`** (зеркало pcap), не `180` (без ринбэка).
2. **Один held-вызов за раз** (фикс-порты SIP/RTP) — 2-й параллельный ring → игнор+лог.
3. mint+REGISTER на **каждый** ring — зеркало приложения, приемлемо.

## Consequences

**Плюсы:**
- Мгновенный dismiss экрана при сбросе с панели (главная цель).
- Бонус: «ответ на другом устройстве» тоже приходит как `CANCEL` → тот же dismiss.
- Бонус: ответ быстрее (INVITE уже на руках, без mint→register на клике).

**Минусы / риски:**
- Держим SIP-сессию ~30с на каждый звонок (даже игнорируемый) → release по
  cancel/accept/таймауту. Фикс-порт — без «кладбища» регистраций.
- Меняем проверенный core приёма → митигировано fallback (#fallback) + поэтапным
  live-тестом.
- На некоторых связанных панелях held-вызов отображается как «Занято» до
  `CANCEL`/таймаута. Поведение воспроизводится штатным приложением при полностью
  отключённой HA-интеграции; это не побочный эффект уникальной SIP-механики HA.
  Точная логика группировки панелей остаётся операторской/аппаратной деталью.

## Alternatives rejected

- **Поллинг статуса вызова оператора во время ring** — нет известного endpoint, не
  зеркало приложения, грязно.
- **Оставить 30с-таймер** — текущее поведение, бесполезный мёртвый экран (отвергнуто
  пользователем).

## Связь

- [`call-answer-model.md`](../features/intercom-two-way-audio/call-answer-model.md) — модель приёма.
- [`research-spike.md`](../features/intercom-two-way-audio/research-spike.md) — held viable (тест 2).
- pcap `captures/panel_drop.pcap` — `CANCEL`→`487` evidence (gitignored).
- ADR-0006 mirror-app-behavior — register-on-ring зеркалит приложение.
- ADR-0011 doorbell-fcm-channel — FCM ring остаётся триггером (now → REGISTER).
