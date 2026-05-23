# research/scripts/

Pipeline для сбора HAR-трафика мобильного приложения «Мой Дом» / «Умный Дом.ру». Реализация [ADR-0006](../../docs/decisions/0006-mirror-app-behavior.md) и [ADR-0007](../../docs/decisions/0007-stateful-emulator-baseline.md).

## Дизайн

```
┌────────────────────────────────────────────────────────────────┐
│  One-time setup                                                │
│  ─────────────                                                 │
│  00a-detect.sh             ← автодетект AVD + package          │
│                              → research/scripts/.env           │
│  00-patch-apk.sh           ← apk-mitm + sign. На каждую        │
│                              новую версию APK.                 │
│  01-baseline-setup.sh      ← полу-автомат: ставит cert,        │
│                              APK, помогает с login, сохраняет  │
│                              snapshot. На каждую новую версию  │
│                              приложения / истечение access.    │
└────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────┐
│  Per-capture (любой сценарий)                                  │
│  ───────────────────────────                                   │
│  02-snapshot-load.sh       ← восстановить baseline snapshot    │
│  03-app-start.sh           ← запустить приложение              │
│  04-capture-start.sh       ← mitmdump в фоне → research/api/   │
│  ─── human interaction (или агент через UI tools) ───          │
│  05-capture-stop.sh        ← остановить mitmdump, конвертация  │
└────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────┐
│  Дополнительно (для auth-сценариев класса B)                   │
│  ────────────────────────────────────────                      │
│  06-wipe-app-data.sh       ← очистить data приложения          │
│                              перед запуском auth flow          │
└────────────────────────────────────────────────────────────────┘
```

См. также детальный workflow в [`docs/aidd/runbooks/har-collection.md`](../../docs/aidd/runbooks/har-collection.md).

## Зависимости (для разработчика)

| Инструмент | Установка |
|---|---|
| Android SDK + AVD | https://developer.android.com/studio/ |
| `apk-mitm` | `npm install -g apk-mitm` |
| `mitmproxy` (mitmdump) | `brew install mitmproxy` |
| `adb` | в составе Android SDK |
| `apksigner` | в составе Android SDK build-tools |

Для AI-агента `reverse-engineer` все инструменты должны быть в `$PATH`.

## Конфигурация

`.env` создаётся **автоматически** скриптом `00a-detect.sh`. Вручную править не нужно.

```bash
# Запустить автодетект (один раз)
./research/scripts/00a-detect.sh
```

Скрипт обнаруживает:
- `AVD_NAME` — через `avdmanager list avd`. Если AVD один — берёт его; если несколько — спросит.
- `APP_PACKAGE` / `APP_MAIN_ACTIVITY` — через `aapt dump badging` из APK (требует, чтобы APK уже был на месте).
- Остальное — defaults из `lib.sh`.

Результат — `research/scripts/.env` (gitignored). Если уже существует — спросит подтверждение overwrite.

### Что внутри `.env`

| Параметр | Default / source | Когда менять |
|---|---|---|
| `AVD_NAME` | autodetect | если хотите конкретный AVD из нескольких |
| `BASELINE_SNAPSHOT` | `logged-in-baseline` | не нужно |
| `APP_PACKAGE` | autodetect из APK | если меняете оператора (Мой Дом ↔ Дом.ру) |
| `APP_MAIN_ACTIVITY` | autodetect из APK | вместе с APP_PACKAGE |
| `ORIGINAL_APK` / `PATCHED_APK` | `research/apk/myhome-{original,patched}.apk` | если используете другие пути |
| `MITM_PORT` | `8080` | если порт занят |
| `MITM_DUMP_DIR` | `research/api` | не нужно |
| `BASELINE_META` | `research/scripts/.baseline-meta` | не нужно |

Никаких секретов. Только локальные пути и выбор приложения.

### Альтернатива — env vars

`.env` — не обязателен. Можно передать переменные через окружение:

```bash
AVD_NAME=Pixel_8_API_34 APP_PACKAGE=ru.inetra.intercom \
  ./research/scripts/02-snapshot-load.sh
```

Приоритет: env vars > `.env` > defaults в `lib.sh`.

## Шаблон сценария — класс A (logged-in)

```bash
# Загрузить baseline + запустить app + начать capture
./research/scripts/02-snapshot-load.sh
./research/scripts/03-app-start.sh
./research/scripts/04-capture-start.sh "home-screen-refresh"

# ... выполнить сценарий (вручную или через adb input) ...

# Остановить capture
./research/scripts/05-capture-stop.sh
# → research/api/2026-05-23-home-screen-refresh.har
```

## Шаблон сценария — класс B (auth)

```bash
./research/scripts/02-snapshot-load.sh     # baseline grunde — потом сбросим data
./research/scripts/06-wipe-app-data.sh
./research/scripts/03-app-start.sh
./research/scripts/04-capture-start.sh "login-sms-flow"

# ... пройти login руками (SMS приходит на физ номер) ...

./research/scripts/05-capture-stop.sh
```

## Anti-checklist

- 🔴 НЕ запускать на production-устройстве владельца — только AVD.
- 🔴 НЕ коммитить `.env` (содержит package + paths; не секреты, но шум).
- 🔴 НЕ коммитить `*.apk` (`.gitignore` это блокирует).
- 🔴 НЕ коммитить `*.har` (`.gitignore` это блокирует).
- 🔴 НЕ запускать MITM-capture на чужих аккаунтах без явного согласия.
- 🔴 НЕ использовать данные из захваченного HAR вне отладки.

## Связь

- [ADR-0006](../../docs/decisions/0006-mirror-app-behavior.md) — почему вообще зеркалим приложение.
- [ADR-0007](../../docs/decisions/0007-stateful-emulator-baseline.md) — почему stateful baseline.
- [`runbooks/har-collection.md`](../../docs/aidd/runbooks/har-collection.md) — пошаговая инструкция.
- [`.claude/agents/reverse-engineer.md`](../../.claude/agents/reverse-engineer.md) — кто запускает это от лица AI.
- [`.claude/commands/capture-har.md`](../../.claude/commands/capture-har.md) — slash-команда оркестратор.
