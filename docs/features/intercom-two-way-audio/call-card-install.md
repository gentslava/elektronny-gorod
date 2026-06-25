# Установка карточки `eg-intercom-call-card`

Готовая Lovelace-карточка экрана вызова домофона (Slice 3b). Источник —
`frontend/src/`, собранный бандл — `custom_components/elektronny_gorod/www/eg-intercom-call-card.js`
(раздаётся интеграцией как статика, как `eg-intercom-mic-card`).

## 1. Подключить как Lovelace-ресурс

Settings → Dashboards → ⋮ → Resources → **Add resource**:

- URL: `/elektronny_gorod_static/eg-intercom-call-card.js`
- Type: **JavaScript Module**

(или в YAML-режиме dashboards: `resources: [{ url: /elektronny_gorod_static/eg-intercom-call-card.js, type: module }]`)

## 2. Добавить карточку на дашборд

```yaml
type: custom:eg-intercom-call-card
call_state: sensor.podyezd_2_call_state   # обязательно — фаза вызова (Slice 3a)
camera: camera.intercom_call               # видео+звук активного вызова
doorbell_camera: camera.podyezd_2          # видео в фазе ringing (без звука)
lock: lock.podyezd_2                        # открытие двери (lock.unlock)
# опционально:
open_action: auto                          # auto|slide|hold|tap (auto: тач→slide, мышь→hold)
mic: true                                  # показывать микрофон
mic_autostart: true                        # авто-захват при active, если разрешение выдано
timer: auto                                # auto|stopwatch|off
name: "Подъезд 2"                          # переопределить имя (иначе из sensor)
```

Карточка **сама скрывается**, когда вызова нет (`call_state = idle/ended`), и
показывается при `ringing`/`connecting`/`active`/`error`.

## Требования и ограничения

- **HTTPS-origin** — обязателен для микрофона (`getUserMedia`) и надёжного автозвука.
  По HTTP микрофон недоступен (карточка покажет «Нет HTTPS»).
- **Видео+звук** — через HA-native `ha-camera-stream`. Если в вашей версии HA его нет,
  карточка использует `webrtc-camera` (если установлена) или покажет подсказку.
- **Автозвук**: браузер может заблокировать автозапуск со звуком — снимается одним
  тапом по кнопке звука (это пользовательский жест). Тап «Принять» тоже считается жестом.
- **Микрофон по умолчанию**: захватывается на `active` только если разрешение уже
  выдано; иначе кнопка «Разрешить» (один тап → запрос браузера).

## Fullscreen на настенной панели (опционально)

Вне коробки. Базово — автоматизация по `sensor.*_call_state == ringing` →
переход (`navigate`) на выделенный fullscreen-view с этой карточкой. Расширенно —
`browser_mod.popup` поверх любого экрана (доп. интеграция). См.
[`plan-call-card-ui.md`](plan-call-card-ui.md) Slice 3c.

## Сборка (для разработки)

```bash
cd frontend
npm install
npm run build      # → ../custom_components/elektronny_gorod/www/eg-intercom-call-card.js
npm test           # vitest (чистая логика)
npm run typecheck
```

Бандл коммитится в репозиторий (HACS не собирает фронтенд).
