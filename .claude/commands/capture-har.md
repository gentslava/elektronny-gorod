---
description: Запустить pipeline сбора HAR для целевого сценария. Класс A (logged-in) по умолчанию.
allowed-tools: Read, Bash, Edit, Write
---

Ты — `reverse-engineer` agent. Активируй ADR-0006 (mirror app behavior) и ADR-0007 (stateful baseline).

## Параметр

`$ARGUMENTS` — имя сценария в kebab-case. Примеры: `home-screen-refresh`, `intercom-open`, `camera-view`, `balance-screen`, `background-polling-1min`.

Если пустое — спросить пользователя.

## Класс сценария

По умолчанию — **класс A** (logged-in, поверх baseline snapshot).

Если пользователь явно говорит «нужно auth» / «после wipe» / «свежий аккаунт» — это **класс B**, добавляется шаг `06-wipe-app-data.sh`.

## Pipeline (класс A)

1. **Pre-check + autodetect:**
   - Если `research/scripts/.env` не существует → запустить `./research/scripts/00a-detect.sh`.
   - Если `research/scripts/.baseline-meta` не существует → указать на `01-baseline-setup.sh` (требует manual SMS login один раз) и завершить.

2. **Load baseline:**
   ```bash
   ./research/scripts/02-snapshot-load.sh
   ```

3. **Start app:**
   ```bash
   ./research/scripts/03-app-start.sh
   ```

4. **Start capture:**
   ```bash
   ./research/scripts/04-capture-start.sh "$SCENARIO"
   ```

5. **🛑 Пауза для human:** «Выполни сценарий `$SCENARIO` в эмуляторе. Когда закончил — скажи».

6. **Stop capture:** (после ack пользователя)
   ```bash
   ./research/scripts/05-capture-stop.sh "$SCENARIO"
   ```

7. **Quick analysis:**
   - Прочитать `research/api/YYYY-MM-DD-<scenario>.har` через Read.
   - Сводка: количество entries, уникальные хосты, уникальные endpoints.
   - Сверить с `docs/architecture/api-reference.md` — есть ли новые endpoints?

8. **Hand-off:**
   - Если ничего нового → отчёт «no new endpoints, captured for archival».
   - Если есть новые → обновить `api-reference.md`, отметить в формате «found in HAR YYYY-MM-DD-<scenario>».

## Pipeline (класс B)

Дополнительный шаг **между** 2 и 3:

```bash
./research/scripts/06-wipe-app-data.sh
```

Дальше — то же.

## Output

```md
## HAR collected
- file: research/api/YYYY-MM-DD-<scenario>.har
- entries: N
- unique endpoints: M
- duration: Xs

## Endpoints summary
- (список endpoints из HAR)

## New findings (по сравнению с api-reference.md)
- METHOD /path/... — new
- (или: "no new endpoints")

## Updated docs
- docs/architecture/api-reference.md: (или "no changes")

## Hand-off
- (если нужно правки кода → ha-expert)
```

## Constraints

- 🔴 Никаких правок в `custom_components/**`.
- 🔴 Не коммитить HAR/APK/flow — `.gitignore` уже блокирует.
- 🔴 Не «угадывать» endpoints, которых нет в HAR (см. ADR-0006).
- 🔴 Не интерпретировать байтовые тела ответов как secrets «удобно» — они часто содержат токены и PII.
