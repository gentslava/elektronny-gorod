Status: Active Owner: Developer Experience / QA Agent Last reviewed: 2026-08-11 (current test baseline and redacted diagnostics)

Source files:
- `custom_components/elektronny_gorod/**`
- `tests/**`
- `hacs.json`
- `.github/workflows/**`

Related docs:
- `../../testing/strategy.md`
- `testing.md`
- `debugging.md`
- `../../audit/security.md`

Used by agents:
- Implementer, QA Agent, Validator

Quality gates:
- TESTS_PASS
- SECURITY_PRECHECK_OK

---

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

### 5. Запустить тесты

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements_test.txt
PYTHONPATH=. .venv/bin/pytest tests/ -q
```

Точный текущий baseline, состав suite и известные gaps находятся только в [`testing/strategy.md`](../../testing/strategy.md). Дополнительные команды и mock-стратегия — в [`testing.md`](testing.md).

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
| Config flow показывает форму, но submit падает | собрать diagnostics и релевантный фрагмент лога с debug только для `custom_components.elektronny_gorod`; см. [`debugging.md`](debugging.md). |
| Snapshot 404 / камера недоступна | проверить доступность API оператора и состояние coordinator/камер в diagnostics; затем собрать короткий релевантный фрагмент лога. |

## Не забыть

- Для issue предпочитать встроенную diagnostics-выгрузку: интеграция редактирует известные секреты и персональные поля.
- Перед публикацией всё равно проверить diagnostics и лог вручную. Не передавать токены, пароли, SMS-коды, заголовки авторизации и персональные данные: сторонние зависимости могут писать собственные сообщения.
- Не публиковать полный `home-assistant.log`; достаточно короткого фрагмента с debug только для нужного модуля.

## Next reading

- [`testing.md`](testing.md) — как запускать тесты
- [`debugging.md`](debugging.md) — как искать root cause
- [`../../audit/security.md`](../../audit/security.md) — что не логировать
