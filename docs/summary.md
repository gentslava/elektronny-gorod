Status: Active
Owner: Lead Architect Agent
Last reviewed: 2026-05-22

Source files:
- весь репозиторий — это сжатый обзор

Related docs:
- `index.md`
- `project/project-map.md`
- `audit/project-audit.md`
- `roadmap.md`

Used by agents:
- Любой агент при старте — первое чтение

Quality gates:
- AUDIT_DONE

---

# Summary — быстрый обзор

Двухминутное введение в проект. Все детали — по ссылкам.

## Что это

Home Assistant **custom integration** [`elektronny_gorod`](../custom_components/elektronny_gorod/manifest.json) для российских операторов «Электронный город» (Новотелеком) и «Дом.ру».

- **Платформы:** `camera`, `lock` (домофоны), `sensor` (баланс ЛС).
- **Дистрибуция:** HACS (`hacs.json`, GitHub Releases zip).
- **API:** `myhome.proptech.ru` (закрытое API мобильного приложения «Мой дом», эмуляция Android-клиента).
- **Опция:** прокси видео через [go2rtc](https://github.com/AlexxIT/go2rtc) для получения звука и RTSP, с Basic Auth (username/password) для go2rtc API.
- **Версия:** см. [`manifest.json`](../custom_components/elektronny_gorod/manifest.json).
- **Codeowner:** [@gentslava](https://github.com/gentslava).
- **PR pre-release:** workflow [`prerelease.yaml`](../.github/workflows/prerelease.yaml) выкатывает pre-release zip для каждого открытого PR.

## Состояние

| Аспект | Статус |
|---|---|
| Работает у пользователей | ✅ да (релизится через HACS) |
| HA hassfest CI | ✅ зелёный |
| HACS validation CI | ✅ зелёный |
| pytest CI | 🔴 отсутствует |
| Реальные тесты | 🔴 нет (есть stub из шаблона HA) |
| Integration Quality Scale | 🔴 ниже Bronze |
| Документация для пользователя | ⚠️ есть, но с битыми ссылками |
| AIDD документация для агентов | ✅ только что заложена |

## Главные сильные стороны

- Полноценный 3-веточный config_flow: phone+SMS / phone+password / advanced (access_token).
- Корректные миграции `async_migrate_entry` v1→2→3.
- Опциональная интеграция go2rtc с real-валидацией (GET /api + PUT /api/streams + DELETE cleanup).
- Reauth по совпадению `account+subscriber+name`.
- Локализация ru/en.
- Автоматизированный release workflow (zip + автокоммит версии).

## Что улучшилось в 3.0.5 (по сравнению с 3.0.4)

- Camera: `_attr_available`/`_attr_is_on` теперь устанавливаются по факту наличия stream_url ([`camera.py:197-225`](../custom_components/elektronny_gorod/camera.py#L197-L225)). Частично закрывает «available default» для камеры.
- go2rtc: добавлена поддержка Basic Auth (username/password) — новые поля в config/options flow.
- CI: PR pre-release workflow.

Новые замечания, появившиеся вместе с этими изменениями:
- `import base64` **внутри метода** [`camera.py:167`](../custom_components/elektronny_gorod/camera.py#L167) — антипаттерн.
- В [`camera.py:215-225`](../custom_components/elektronny_gorod/camera.py#L215-L225) `async_update` делает **два запроса** (`update_camera_state` + `get_camera_stream`) — лишняя нагрузка.
- `go2rtc_username` / `go2rtc_password` хранятся в `entry.data` в plaintext, без миграции для существующих v3 entries — security-sensitive.

## Главные риски

### P0 — критичные (заслуживают hotfix-релиза)

1. **Утечка access_token в логи** — [`config_flow.py:77`](../custom_components/elektronny_gorod/config_flow.py#L77), [`http.py:13`](../custom_components/elektronny_gorod/http.py#L13), [`http.py:22-25`](../custom_components/elektronny_gorod/http.py#L22-L25), [`config_flow.py:283`](../custom_components/elektronny_gorod/config_flow.py#L283), [`config_flow.py:291`](../custom_components/elektronny_gorod/config_flow.py#L291). При `debug` уровне любой пользователь может прочитать чужой bearer-токен в `home-assistant.log`.
2. **Bug в [`coordinator.py:182`](../custom_components/elektronny_gorod/coordinator.py#L182)** — поиск камеры по `c.get("ID")` (верхний регистр) при реальном ключе `id`. Тихая ошибка, `update_camera_state` всегда падает.
3. **`aiohttp.ClientSession()` per-request** в [`http.py:56`](../custom_components/elektronny_gorod/http.py#L56) — антипаттерн для HA, должен использоваться `async_get_clientsession(hass)`.
4. **Тесты — нерабочий stub** в [`tests/test_config_flow.py`](../tests/test_config_flow.py) — импортирует несуществующие сущности. Coverage 0%.
5. **`go2rtc_password` в plaintext в `entry.data`** ([`config_flow.py:362`](../custom_components/elektronny_gorod/config_flow.py#L362), [`config_flow.py:419`](../custom_components/elektronny_gorod/config_flow.py#L419)) — должен redact-иться в diagnostics; рассмотреть HA `auth_storage`.

### P1 — важные

- Coordinator без `update_interval` — данные не обновляются после старта.
- Entity не используют `CoordinatorEntity`.
- `iot_class: cloud_polling` не соответствует реальности (нет polling).
- ✅ `hacs.json` минимальная HA = 2024.10.4 (LockState enum появился в 2024.10).
- Sensor баланса: unit `"₽"` вместо `"RUB"`, нет `device_class`/`state_class`.
- `unique_id` для Camera/Lock содержит локализованное `name`.
- Нет `diagnostics.py` с redaction.
- Camera `async_update` делает доп. запрос для проверки stream — лишний трафик; должно идти через coordinator.

Полный список — в [`audit/project-audit.md`](audit/project-audit.md).

## Первое, что нужно сделать

P0-фикс одним PR (< 1 дня), завершить hotfix-релизом:

1. Удалить лог токена в [`config_flow.py:77`](../custom_components/elektronny_gorod/config_flow.py#L77).
2. Маскировать headers и не логировать `data` в [`http.py:11-13`](../custom_components/elektronny_gorod/http.py#L11-L13).
3. Не логировать тело auth-ответов в [`http.py:22-25`](../custom_components/elektronny_gorod/http.py#L22-L25).
4. Заменить `entry.data` → `entry.entry_id` в [`config_flow.py:283,291`](../custom_components/elektronny_gorod/config_flow.py#L283).
5. Исправить `c.get("ID")` → `c.get("id")` в [`coordinator.py:182`](../custom_components/elektronny_gorod/coordinator.py#L182).
6. Удалить или skip-нуть нерабочий `tests/test_config_flow.py`.
7. Поднять `import base64` на top of file в [`camera.py:167`](../custom_components/elektronny_gorod/camera.py#L167).
8. Hotfix-релиз с changelog «security: redact tokens in logs».

## AIDD-структура

Развёрнут **Full AIDD**: docs/ + `.claude/*` + `.cursor/*` + `.github/copilot-instructions.md` + ADR + templates + runbooks. Подробности — в [`index.md`](index.md).

```
AGENTS.md / CLAUDE.md / conventions.md / workflow.md  ← корневые контракты
docs/
├── index.md                       ← точка входа
├── summary.md                     ← это
├── roadmap.md
├── project/                       ← про проект (карта, источники правды)
├── architecture/                  ← архитектура + HA-чеклист + IQS
├── audit/                         ← все findings + security
├── testing/                       ← test plan
└── aidd/                          ← агентская методология (gates, sources, contributing)
```

## Куда дальше

- Если задача — **понять проект**: [`project/project-map.md`](project/project-map.md) → [`architecture/overview.md`](architecture/overview.md).
- Если задача — **исправить security**: [`audit/security.md`](audit/security.md).
- Если задача — **добавить тесты**: [`testing/strategy.md`](testing/strategy.md).
- Если задача — **планировать**: [`roadmap.md`](roadmap.md).
- Если задача — **внести вклад через AI**: [`aidd/contributing.md`](aidd/contributing.md).

## Next reading

- For full map: `project/project-map.md`
- For architecture: `architecture/overview.md`
- For findings: `audit/project-audit.md`
- For roadmap: `roadmap.md`
- For agent workflow: `../workflow.md`
