# Runbook: Local development

Как запустить проект локально на dev-машине разработчика / AI-агента.

## Требования

- Python 3.12+
- Home Assistant (dev-инстанс) ≥ HA-min из `hacs.json`
- git
- (опционально) Docker / VS Code Dev Container

## Шаги

### 1. Клонировать репо

```bash
git clone https://github.com/gentslava/HA-ElektronnyGorod.git elektronny-gorod
cd elektronny-gorod
```

### 2. Установить интеграцию в HA dev-инстанс

#### Вариант А: симлинк

```bash
HA_CONFIG_DIR=~/.homeassistant  # или ваш путь
mkdir -p "$HA_CONFIG_DIR/custom_components"
ln -s "$(pwd)/custom_components/elektronny_gorod" \
      "$HA_CONFIG_DIR/custom_components/elektronny_gorod"
```

#### Вариант Б: копирование

```bash
cp -r custom_components/elektronny_gorod "$HA_CONFIG_DIR/custom_components/"
```

### 3. Запустить HA

```bash
hass -c "$HA_CONFIG_DIR" --debug
```

(или из Docker / `homeassistant.io/docs/installation/`)

### 4. Добавить интеграцию через UI

1. Settings → Devices & Services → Add Integration → «Электронный город».
2. Пройти SMS/password/token flow.
3. (опционально) настроить go2rtc.

### 5. Тесты (когда переписаны — см. [`testing.md`](testing.md))

```bash
pip install pytest pytest-asyncio pytest-homeassistant-custom-component aioresponses
pytest tests/ -v
```

### 6. Перезагрузить интеграцию после правок

В HA UI: Settings → Devices & Services → 3-dot → Reload.

Или через CLI:

```bash
# при необходимости перезапустить HA целиком
```

## Полезные команды

```bash
# Проверить manifest валидацию (как hassfest CI)
docker run --rm -v "$(pwd)":/github/workspace \
    ghcr.io/home-assistant/hassfest:latest

# Проверить HACS валидацию
docker run --rm -v "$(pwd)":/github/workspace ghcr.io/hacs/action:main \
    -e INPUT_CATEGORY=integration
```

## Проблемы

| Симптом | Решение |
|---|---|
| `ImportError: cannot import name X from homeassistant` | HA версия dev-инстанса ниже `hacs.json:homeassistant` — обновите HA. |
| Интеграция не появляется в списке | проверить `__init__.py`, `manifest.json`, перезапустить HA. |
| Config flow show form, но submit падает | смотрите логи; включить `default: debug` в `configuration.yaml` для домена `custom_components.elektronny_gorod`. |
| Snapshot 404 | пропал stream_url — проверить через `update_camera_state` в логах (после фикса A-06). |

## Не забыть

- 🔴 Никогда не делиться `home-assistant.log` с включённым `debug` — там утечки токенов (см. [`security.md`](../../audit/security.md)). До hotfix-релиза.
- При шаринге debug — обязательно проходить через diagnostics (когда появится).

## Next reading

- [`testing.md`](testing.md) — как запускать тесты
- [`debugging.md`](debugging.md) — как искать root cause
- [`../../audit/security.md`](../../audit/security.md) — что не логировать
