# Runbook: HAR collection

Процесс сбора HTTPS-трафика мобильного приложения «Мой Дом» / «Умный Дом.ру». Реализация [ADR-0006: Mirror application behavior](../../decisions/0006-mirror-app-behavior.md) поверх [ADR-0007: Stateful emulator baseline](../../decisions/0007-stateful-emulator-baseline.md).

> **Альтернатива через Charles** (если вы уже работаете в Charles вручную): соберите `.chlz` → File → Export Session… → HAR → положите `.har` в `research/api/`. Pipeline скриптов ниже — для **mitmproxy** (агент может им управлять). Charles остаётся для ручной работы пользователя.

## Когда применять

- Перед началом любой новой фичи, которая трогает API.
- При обновлении версии приложения (проверить, не изменились ли API-контракты).
- При расследовании bug-а, связанного с серверной стороной.
- Периодически (раз в N месяцев) — проверка, что наше поведение соответствует приложению.

## Что понадобится

- **macOS / Linux** (скрипты на bash).
- **Android SDK + AVD** — https://developer.android.com/studio/. Эмулятор Pixel API 34 рекомендован.
- **mitmproxy** — `brew install mitmproxy` (macOS) или `apt install mitmproxy` (Linux).
- **apk-mitm** — `npm install -g apk-mitm`.
- **APK** оригинального приложения — скачать вручную (см. [`research/apk/README.md`](../../../research/apk/README.md)).
- **Действующий аккаунт оператора** — свой (не чужой без согласия).
- **Один реальный SIM с активной услугой** — для прохождения SMS-кода один раз при создании baseline.

## Два класса сценариев

| Класс | Когда | Старт |
|---|---|---|
| **A — logged-in** | 95% сбора | загрузить baseline snapshot → app start |
| **B — auth** | работа над auth flow | wipe app data → app start → manual SMS login |

Cм. [ADR-0007](../../decisions/0007-stateful-emulator-baseline.md).

## Полный pipeline

### Часть 1: One-time setup

#### Шаг 1.1. Скачать APK

Скачать оригинальный APK с APKMirror / APKPure / своего телефона. Положить в `research/apk/myhome-original.apk`. См. [`research/apk/README.md`](../../../research/apk/README.md).

> Это **единственный** ручной шаг, который нельзя автоматизировать (Google Play не имеет публичного API для скачивания).

#### Шаг 1.2. Автодетект окружения

```bash
./research/scripts/00a-detect.sh
```

Создаёт `research/scripts/.env` с обнаруженными AVD_NAME, APP_PACKAGE, APP_MAIN_ACTIVITY. **Не нужно редактировать вручную** — никаких секретов, только локальные пути и выбор приложения. Агент `reverse-engineer` запускает это сам.

#### Шаг 1.3. Запатчить APK

```bash
./research/scripts/00-patch-apk.sh
```

Использует `apk-mitm`: отключает certificate pinning, добавляет user-cert trust, переподписывает.

#### Шаг 1.4. Создать baseline snapshot

```bash
./research/scripts/01-baseline-setup.sh
```

Скрипт — полу-автомат:
- стартует AVD с writable system;
- ставит mitmproxy CA как system cert;
- ставит пропатченный APK;
- настраивает proxy;
- **🛑 пауза:** ты вручную проходишь SMS-login в эмуляторе, доходишь до главного экрана;
- сохраняет AVD snapshot `logged-in-baseline`.

После этого момента — большинство сценариев не требует human action.

### Часть 2: Per-capture (любой сценарий)

#### Через slash-команду (рекомендуется)

В Claude Code:

```
/capture-har home-screen-refresh
```

Агент `reverse-engineer` выполнит весь pipeline + анализ.

#### Вручную

```bash
# 1. Загрузить baseline
./research/scripts/02-snapshot-load.sh

# 2. Запустить приложение
./research/scripts/03-app-start.sh

# 3. Начать capture
./research/scripts/04-capture-start.sh home-screen-refresh

# 4. Выполнить сценарий в приложении (вручную или через adb input)

# 5. Остановить capture
./research/scripts/05-capture-stop.sh home-screen-refresh
```

Результат: `research/api/YYYY-MM-DD-home-screen-refresh.har`.

### Часть 3: Class B (auth) — wipe + manual SMS

Между шагом 2.2 и 2.3 добавь:

```bash
./research/scripts/06-wipe-app-data.sh
```

Дальше — `03-app-start.sh` → `04-capture-start.sh login-sms-flow` → **manual SMS login** → `05-capture-stop.sh`.

После этого baseline (snapshot) **не повреждён** — он восстановит залогиненное состояние при следующем `02-snapshot-load.sh`.

## Naming convention для HAR

```
research/api/YYYY-MM-DD-<scenario>.har
```

Примеры сценариев:
- `home-screen-cold-start` — первый запуск приложения (после `am force-stop`).
- `home-screen-refresh` — pull-to-refresh главного экрана.
- `intercom-open` — открытие домофона.
- `camera-view` — открытие экрана камеры + stream.
- `balance-screen` — экран баланса.
- `events-history` — история звонков/событий (если есть).
- `background-polling-1min` — приложение свёрнуто, 1 минута фоновой активности.
- `login-sms-flow` — full SMS login (класс B).
- `login-password-flow` — password login (класс B).

## Update baseline (при обновлении APK)

1. Скачать новый APK → `research/apk/myhome-original.apk` (overwrite).
2. `./research/scripts/00-patch-apk.sh` — переподписать.
3. `./research/scripts/01-baseline-setup.sh` — пересоздать baseline.
4. Файл `research/scripts/.baseline-meta` обновится автоматически.

## Анти-чек-лист

- 🔴 НЕ записывать сессии чужих аккаунтов без явного согласия владельца.
- 🔴 НЕ коммитить `.har`, `.apk`, `.flow`, `.env`, `.baseline-meta` (всё в `.gitignore`).
- 🔴 НЕ публиковать HAR в issue / Discord / Gist даже после redaction.
- 🔴 НЕ использовать данные из HAR (токены) для каких-либо действий вне отладки.
- 🔴 НЕ экспериментировать с endpoints, которых нет в HAR — нарушает [ADR-0006](../../decisions/0006-mirror-app-behavior.md).
- 🔴 НЕ распространять пропатченный APK третьим лицам.

## Verification

После сбора HAR:

```bash
# Сколько entries?
jq '.log.entries | length' research/api/<file>.har

# Уникальные хосты?
jq -r '.log.entries[].request.url' research/api/<file>.har | awk -F/ '{print $3}' | sort -u

# Auth-related запросы?
jq -r '.log.entries[].request.url' research/api/<file>.har | grep -E '/auth/'

# Ответы со статусом != 2xx?
jq -r '.log.entries[] | select(.response.status >= 400) | "\(.response.status) \(.request.url)"' research/api/<file>.har
```

## Связь

- [ADR-0006](../../decisions/0006-mirror-app-behavior.md) — обязательность зеркалирования.
- [ADR-0007](../../decisions/0007-stateful-emulator-baseline.md) — почему baseline-based.
- [`research/scripts/README.md`](../../../research/scripts/README.md) — pipeline.
- [`research/apk/README.md`](../../../research/apk/README.md) — где брать APK.
- [`research/api/README.md`](../../../research/api/README.md) — naming + storage.
- [`api-reference.md`](../../architecture/api-reference.md) — куда вливаются результаты анализа.
- [`.claude/agents/reverse-engineer.md`](../../../.claude/agents/reverse-engineer.md) — кто запускает.
- [`.claude/commands/capture-har.md`](../../../.claude/commands/capture-har.md) — slash-команда.

## Next reading

- [`api-reference.md`](../../architecture/api-reference.md)
- [ADR-0007](../../decisions/0007-stateful-emulator-baseline.md)
