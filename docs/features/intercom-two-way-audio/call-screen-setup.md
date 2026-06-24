# Сборка экрана вызова домофона (пуш → экран `/doorbell-call/call`)

Пошаговая инструкция, как собрать полноценный **экран вызова** домофона
«Электронный город»: пуш на телефон открывает в Home Assistant экран, где видно
гостя, слышно его и можно ответить, говорить и открыть дверь.

- **Date:** 2026-06-25
- **Связь:** [call-screen-display-design.md](call-screen-display-design.md) (архитектура `camera.intercom_call`),
  [uplink-card-install.md](uplink-card-install.md) (карта микрофона),
  [call-answer-model.md](call-answer-model.md) (модель приёма вызова, окно ~30с).

## Модель UX

«Лёгкий пуш → экран в HA». Пуш не несёт весь UX — он будит телефон и одним тапом
открывает экран `/doorbell-call/call`, где живёт видео, звук и управление. Это
надёжнее, чем тащить ответ/звук в само уведомление.

```
FCM ring ─► [blueprint notify] ─► пуш (снимок + «Открыть дверь» + clickAction)
                  │                        │
                  ▼                        ▼ тап
        input_text = активная дверь    экран /doorbell-call/call
                                           ├─ ringing: видео двери + «Ответить»/«Открыть»
                                           └─ in-call: видео+звук вызова + 🎤 + «Сбросить»/«Открыть»
```

Два состояния экрана переключаются хелперами, которые ведут blueprint-ы:

| Хелпер | Что значит | Кто ведёт |
|---|---|---|
| `input_text.eg_doorbell_active_lock` | какой замок звонит (пусто = нет вызова) | `doorbell_call_notify` (ring/ended) + контроллер (SIP-end/start) |
| `input_boolean.eg_doorbell_sip_active` | идёт ли SIP-разговор | `doorbell_screen_controller` (событие `elektronny_gorod_sip_call`) |

## Компоненты

| Что | Файл | Сколько |
|---|---|---|
| Хелперы | [`examples/doorbell-screen-helpers.yaml`](examples/doorbell-screen-helpers.yaml) | 1× на систему |
| Blueprint — пуш+экран на дверь | [`doorbell_call_notify.yaml`](../../../blueprints/automation/elektronny_gorod/doorbell_call_notify.yaml) | по 1× на дверь |
| Blueprint — контроллер (SIP/открыть/старт) | [`doorbell_screen_controller.yaml`](../../../blueprints/automation/elektronny_gorod/doorbell_screen_controller.yaml) | 1× на систему |
| Дашборд экрана | [`examples/doorbell-call-dashboard.yaml`](examples/doorbell-call-dashboard.yaml) | 1× на систему |
| Карта микрофона | `custom:eg-intercom-mic-card` (раздаётся интеграцией) | — |
| Pro-tip видео (опц.) | `custom:advanced-camera-card` (HACS) | — |

## Шаг 1. Хелперы

Создайте два хелпера — через UI (Настройки → Устройства и службы → Вспомогательные →
«Текст» `eg_doorbell_active_lock` + «Переключатель» `eg_doorbell_sip_active`) или
пакетом [`examples/doorbell-screen-helpers.yaml`](examples/doorbell-screen-helpers.yaml).
Имена менять можно — главное согласовать их в blueprint-ах и на дашборде.

## Шаг 2. Blueprint-ы

Импортируйте оба (Настройки → Автоматизации → Blueprints → Import Blueprint, raw-URL
файла, либо скопируйте в `config/blueprints/automation/elektronny_gorod/`):

1. **`doorbell_call_notify`** — создайте автоматизацию **по разу на каждую дверь**.
   Укажите: сущность вызова двери, её камеру, её замок, оба хелпера и телефон.
2. **`doorbell_screen_controller`** — создайте автоматизацию **один раз**. Укажите
   оба хелпера.

## Шаг 3. Дашборд экрана

Создайте дашборд (Настройки → Панели → Добавить панель), путь — `doorbell-call`
(чтобы clickAction `/doorbell-call/call` открывал его). Откройте Raw configuration
editor и вставьте `views:` из [`examples/doorbell-call-dashboard.yaml`](examples/doorbell-call-dashboard.yaml),
подставив свои `entity_id`. Для нескольких дверей — скопируйте conditional-блок
двери и поменяйте замок/камеру.

## Шаг 4. Карта микрофона

Добавьте Lovelace-ресурс `/elektronny_gorod_static/eg-intercom-mic-card.js`
(тип — JavaScript-модуль) — подробно в [uplink-card-install.md](uplink-card-install.md).
В дашборде она уже встроена в in-call-блок (`custom:eg-intercom-mic-card`).

> Браузер отдаёт микрофон только на **HTTPS-origin** (или `localhost`).

## Шаг 5 (pro-tip). Звук сразу — `advanced-camera-card`

In-call по умолчанию использует `picture-entity`. **Инлайн picture-entity глушит
звук** — это политика автоплея браузера (не интеграции): звук появляется после
одного тапа по видео. Если хочется звук сразу, поставьте через HACS
**`advanced-camera-card`** и замените in-call-карту на закомментированный блок из
[`examples/doorbell-call-dashboard.yaml`](examples/doorbell-call-dashboard.yaml):
он тянет поток из go2rtc по WebRTC/MSE и включает `auto_unmute` — быстрее грузится
и не требует тапа.

## Как это работает (поток состояний)

1. **Вызов** (FCM `ring`) → `doorbell_call_notify`: пишет активный замок в
   `input_text`, шлёт двухэтапный пуш (мгновенный + снимок) с `clickAction` на экран
   и кнопкой «Открыть».
2. **Тап по пушу** → открывается `/doorbell-call/call`; пока `sip_active=off` —
   ringing-блок (видео двери, «Ответить»/«Открыть»).
3. **«Ответить»** (`elektronny_gorod.answer`) → интеграция шлёт `elektronny_gorod_sip_call`
   `active:true` → контроллер ставит `sip_active=on` → экран → in-call (видео+звук
   вызова, 🎤, «Сбросить»/«Открыть»).
4. **«Открыть»** — кнопкой на экране или `OPEN_<lock>` из пуша (контроллер →
   `lock.unlock`).
5. **Завершение** — по SIP (`elektronny_gorod_sip_call active:false`) контроллер
   гасит `sip_active` и чистит `input_text`; по FCM `ended` `doorbell_call_notify`
   чистит `input_text` и снимает пуш. Экран → «Нет активного вызова».
6. **Старт HA** — контроллер сбрасывает зависшее состояние.

## Известные ограничения

- **Звук in-call по умолчанию выключен** (picture-entity + автоплей браузера) — тап
  по видео или pro-tip `advanced-camera-card` (Шаг 5).
- **Окно ответа ~30с** (`CallInvalidated`) — иначе домофон сбросит вызов сам.
- **Несколько телефонов** — `doorbell_call_notify` шлёт на одно устройство; для
  нескольких используйте notify-группу или по инстансу blueprint на телефон.
- **Один одновременный разговор** (ограничение SIP-слайса).
