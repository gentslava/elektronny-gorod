# Синхронизация данных сайта с репозиторием

Сайт не дублирует репозиторий автоматически — этот документ фиксирует, **что** и **когда** нужно синхронизировать вручную (или заскриптовать позже).

## При каждом релизе интеграции

| Что | Где на сайте | Источник правды |
|---|---|---|
| Версия интеграции | `src/data/project.ts: version`, `index.html` (JSON-LD `softwareVersion` и чип в шапке) | `custom_components/elektronny_gorod/manifest.json` |
| Release notes | `src/data/project.ts: releaseNotesLatest` | последний файл `docs/releases/X.Y.Z.md` |
| Мин. версия HA | `src/data/project.ts: minHomeAssistant`, тексты compat/бейджей (`2026.8+`) | `hacs.json: homeassistant` |
| Ответы FAQ про прошлые релизы | не синхронизируются: это исторические записи о конкретном переходе, а не заявление о текущей версии | — |
| Бандл карточки | пересборка сайта (`npm run build`) — бандл импортируется по пути | `custom_components/elektronny_gorod/www/eg-intercom-call-card.js` |

## При изменении функциональности

| Что | Где на сайте | Источник правды |
|---|---|---|
| Имена сервисов | `src/data/project.ts: services`, YAML в `src/data/automations.ts` | `services.yaml` |
| Имена/паттерны сущностей | `src/data/project.ts: entities`, `automations.ts`, advanced-таблица в `index.html` | `event.py`, `sensor.py`, `switch.py`, `strings.json` |
| Возможности / ограничения | `src/data/compatibility.ts` (вердикты и ноты), секция features, FAQ | `README.md`, `docs/releases/*` |
| Шаги установки | `src/data/wizard.ts` | `README.md`, `docs/features/**/call-screen-setup.md` |
| Deep links | `src/data/project.ts` и CTA в `index.html` | `README.md` (my.home-assistant.io) |

## При смене домена публикации

`index.html`: `canonical`, `og:url`, `og:image`, JSON-LD `url`. Сейчас указан `https://gentslava.github.io/elektronny-gorod/`.

## Демо-контент

- Фото гостя: `public/assets/guest.jpg` ← `pencil/images/generated-*.png` (сгенерировано, PII нет). Название дома/адрес в демо — «Подъезд 2, ул. Примерная, 1» (как в `frontend/demo`). Реальные адреса и договоры в демо запрещены (см. memory: api-docs-universal-tone).
- Скриншоты: `public/assets/{wall-panel.jpg,history.png}` ← `docs/features/**/screenshots/`.

## Проверка после синхронизации

```bash
npm run typecheck && npm test && npm run build
```

Тест `automations.test.ts` упадёт, если YAML использует несуществующие домены сервисов; `wizard`/`compat` — если сломалась логика ветвления; `sync.test.ts` — если версия или минимальная HA на сайте разъехались с `manifest.json` и `hacs.json`, а также если ссылка на release notes ведёт на несуществующий файл.
