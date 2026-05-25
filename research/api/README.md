# research/api/

Локальная папка для HAR-снимков трафика мобильного приложения «Мой Дом» / «Умный Дом.ру». Используется для reverse engineering API по принципу [ADR-0006: Mirror application behavior](../../docs/decisions/0006-mirror-app-behavior.md).

🔴 **Эта папка НЕ коммитится** (см. [`.gitignore`](../../.gitignore)). HAR содержит реальные токены, account_id, адреса, балансы.

## Что класть сюда

- `.har` файлы из Charles / mitmproxy / Proxyman.
- `.chlz` / `.chls` исходники из Charles (опционально — для архива; **агент их читать не может**, см. ниже).
- Заметки анализа в `notes/` (опционально).
- Свои черновые скрипты для разбора (`*.py`, `*.sh`).

## Форматы capture

| Расширение | Источник | Агент может читать? | Что делать |
|---|---|---|---|
| `.har` | mitmproxy/Charles/Proxyman/DevTools | ✅ да — JSON | основной формат для анализа |
| `.flow` | mitmproxy native | ⚠️ нет напрямую, но `mitmdump -nr file.flow --set hardump=file.har` конвертирует | конвертация перед анализом (есть в `05-capture-stop.sh`) |
| `.chlz` / `.chls` | Charles native (proprietary binary, gzip-of-XML) | ❌ нет | конвертировать в HAR через Charles GUI (см. ниже) |
| `.saz` | Fiddler | ❌ нет | конвертировать через Fiddler GUI |
| `.pcap` / `.pcapng` | Wireshark / tcpdump | ❌ нет (низкий уровень) | для проекта избыточно — TLS не расшифрован |

### Charles `.chlz` → HAR

В Charles:

1. Открыть `.chlz` (File → Open).
2. **File → Export Session…** (или `Cmd+Shift+E`).
3. Format: **HTTP Archive (.har)**.
4. Сохранить в `research/api/YYYY-MM-DD-<scenario>.har`.

После этого агент `reverse-engineer` читает HAR.

> Все `.chlz` файлы в `.gitignore`. Хранятся локально для archive — не нужно конвертировать, если планируете переоткрывать в Charles. Но для анализа агентом — нужен HAR.

## Naming convention

```
research/api/
├── README.md                                      ← этот файл (единственный коммитится)
├── YYYY-MM-DD-<scenario-kebab>.har                ← основной формат
├── YYYY-MM-DD-<scenario>-vN.har                   ← если переснимали тот же сценарий
└── notes/
    └── YYYY-MM-DD-<scenario>.md                   ← разбор по этому HAR
```

Сценарии (примеры):

- `login-sms-flow.har` — полный auth через SMS.
- `login-password-flow.har` — через пароль.
- `login-existing-token.har` — повторный запуск приложения с существующим токеном.
- `home-screen-cold-start.har` — первый запуск, главный экран.
- `home-screen-refresh.har` — pull-to-refresh главного экрана.
- `intercom-open.har` — открытие домофона.
- `camera-view.har` — открытие камеры + получение потока.
- `balance-payment.har` — экран баланса/оплаты.
- `events-history.har` — история звонков/событий, если есть в приложении.
- `background-polling-1min.har` — приложение свёрнуто, 1 минута фона.

## Workflow

См. [`docs/aidd/runbooks/har-collection.md`](../../docs/aidd/runbooks/har-collection.md).

Кратко:

1. Установить APK с MITM-патчем (`apk-mitm`).
2. Включить Charles + сертификат + proxy на устройстве.
3. Запустить нужный сценарий в приложении.
4. Сохранить сессию как HAR.
5. Положить файл сюда с правильным именем.
6. Передать имя файла агенту для анализа.

## Что агент делает с HAR

При получении HAR агент:

1. Читает через `Read` tool — структура JSON.
2. Извлекает endpoints, методы, headers, последовательность, тайминги.
3. Обновляет [`docs/architecture/api-reference.md`](../../docs/architecture/api-reference.md) **только на основе фактов из HAR**.
4. Идентифицирует gap-ы между поведением приложения и текущей реализацией в `custom_components/`.
5. **Не** придумывает endpoints, которых нет в HAR (см. [ADR-0006](../../docs/decisions/0006-mirror-app-behavior.md)).

## Анти-чек-лист

- 🔴 НЕ коммитить `.har` файлы (даже redacted — `.gitignore` блокирует).
- 🔴 НЕ записывать чужие сессии без явного согласия владельца аккаунта.
- 🔴 НЕ публиковать HAR за пределами своей машины и общения с агентом.
- 🔴 НЕ использовать данные из HAR (токены) для каких-либо действий вне отладки.

## Удаление

После завершения анализа можно очищать старые `.har`:

```bash
# удалить всё кроме README
find research/api -mindepth 1 -not -name README.md -delete
```

Однако имеет смысл хранить «эталонные» снимки для regression checking (сравнить трафик нашей интеграции с приложением).

## Локальный индекс снимков

Локальные `.har` / `.chlz` файлы — gitignored. Их содержимое (имена,
размеры, конкретные сценарии) **не документируется в публичных файлах**
(включая этот README). Сводное покрытие сценариев — в
[`docs/architecture/api-reference.md` §Source HAR](../../docs/architecture/api-reference.md)
в форме `(дата + аккаунт-плейсхолдер + бренд + сценарий)`, без имён
файлов и реальных идентификаторов.

См. [memory: har-sources-priority] и [ADR-0006](../../docs/decisions/0006-mirror-app-behavior.md).
