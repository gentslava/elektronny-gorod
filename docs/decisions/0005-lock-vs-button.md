# ADR-0005: Lock vs Button для домофона

- **Status:** proposed
- **Date:** 2026-05-22
- **Owner:** HA Expert Agent

## Context

Сейчас домофон представлен как [`lock` entity](../../custom_components/elektronny_gorod/lock.py). Это создаёт несколько концептуальных и технических проблем:

1. **Физически домофон не закрывается.** После открытия он автоматически защёлкивается через несколько секунд — никаких lock/unlock операций со стороны клиента.
2. **`fake_timer_lock` через `asyncio.sleep`** — синтетическое состояние LOCKED через 5 секунд (см. [`lock.py:113-120`](../../custom_components/elektronny_gorod/lock.py#L113-L120)). Это вводит пользователя в заблуждение.
3. **`async_lock` ничего не делает** ([`lock.py:93-96`](../../custom_components/elektronny_gorod/lock.py#L93-L96)) — только пишет `LOGGER.info("Not supported")`. Но HA UI показывает кнопку «lock», которая молча игнорируется.
4. **`available = self._openable`** ([`lock.py:56-58`](../../custom_components/elektronny_gorod/lock.py#L56-L58)) может вернуть None.

Концептуально домофон ближе к **button** или **action**: «нажми, чтобы открыть».

## Decision

В **Итерации 3** добавить `button` entity для каждого домофона, **сохранив** `lock` entity на 1-2 minor релиза в `disabled by default` для backwards compatibility:

1. Новая платформа `button`:
   - `ElektronnyGorodOpenDomofonButton(ButtonEntity)`.
   - `_attr_device_class = ButtonDeviceClass.IDENTIFY` (или None — нет полного match в HA).
   - `async_press` → `coordinator.open_lock(...)`.
   - Никакого state — `button` event-only.
2. Существующая `lock` entity:
   - `_attr_entity_registry_enabled_default = False`.
   - Логировать deprecation warning при unlock.
3. CHANGELOG entry: «Добавлен `button.*_open` (рекомендуется); `lock.*` помечен как deprecated, отключён по умолчанию для новых установок».
4. ADR-0005a (будущий) — финальное удаление `lock` через N релизов.

## Consequences

### Positive

- Корректная модель: «открыть» — это действие, не состояние.
- Убираем `fake_timer_lock` и `async_lock`-stub.
- `async_press` идиоматичен для HA.
- Существующие автоматизации с `lock.unlock` продолжают работать (lock сохранён).

### Negative

- Пользователи увидят **новые** entity рядом со старыми → путаница в UI.
- Существующие автоматизации требуют миграции на `button.press`.
- Два набора entity = +N сущностей в реестре.

### Mitigation

- Подробная инструкция в README + CHANGELOG с примерами автоматизаций.
- Через 2 минорных релиза — окончательное удаление `lock` платформы (через отдельный ADR-0005a).

## Alternatives considered

1. **Только удалить `lock`.** Отклонено — breaking change без миграции.
2. **Оставить как есть.** Отклонено — `fake_timer_lock` дезинформирует пользователя; IQS Gold blocker.
3. **Использовать `switch` вместо `button`.** Отклонено — switch имеет state on/off, чего у домофона нет.

## Supersedes / Superseded by

— (новое)

## Notes

См. также:
- [`docs/audit/project-audit.md#A-15`](../audit/project-audit.md).
- [HA developer docs: button entity](https://developers.home-assistant.io/docs/core/entity/button).
