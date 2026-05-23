# research/api/

Локальная папка для HAR-снимков трафика мобильного приложения «Мой Дом» / «Умный Дом.ру». Используется для reverse engineering API по принципу [ADR-0006: Mirror application behavior](../../docs/decisions/0006-mirror-app-behavior.md).

🔴 **Эта папка НЕ коммитится** (см. [`.gitignore`](../../.gitignore)). HAR содержит реальные токены, account_id, адреса, балансы.

## Что класть сюда

- `.har` файлы из Charles / mitmproxy / Proxyman.
- Заметки анализа в `notes/` (опционально).
- Свои черновые скрипты для разбора (`*.py`, `*.sh`).

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
