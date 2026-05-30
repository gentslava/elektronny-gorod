# Rule: Constants locality

**Применимо к:** `custom_components/elektronny_gorod/const.py` + любой модуль,
который добавляет module-level `Final` / `=` константу.

## Правило

🔴 **`const.py` — для shared / identity констант. Domain-specific timing,
policy и tuning остаётся в модуле, который их использует.**

Правило кодифицирует уже сложившуюся convention (см. прецеденты ниже)
и предотвращает «свалку» в `const.py`, где разнородные значения
загромождают diff'ы и create cross-module coupling без причины.

## Что выносить в `const.py`

Константа попадает в `const.py` если **выполнено любое** из условий:

1. **Identity** проекта/интеграции — `DOMAIN`, `LOGGER`, `BASE_API_URL`.
2. **Config-flow key** — все `CONF_*` (используются между config_flow ↔
   coordinator ↔ camera ↔ __init__ для миграций).
3. **Cross-module shared default или enum-like value** — `DEFAULT_GO2RTC_*`,
   `GO2RTC_RTSP_PORT` (camera.py + go2rtc.py), `AREA_*` (camera.py + lock.py),
   `APP_VERSION`, `ANDROID_*` (user_agent ↔ config_flow).
4. **Контрактное значение бэкенда** — `BASE_API_URL`, app-version (mirror app).

## Что остаётся локально в модуле

Константа **остаётся в модуле**, если **выполнено любое** из условий:

1. **Single callsite / single module** — никто другой её не импортирует.
2. **Timing / policy / tuning** конкретного domain — cooldown, poll interval,
   refresh budget, timeout-окно.
3. **Magic value impl-детали** — внутренний counter threshold, retry-кол-во.
4. **Возможно изменится через A/B / ADR без impact на другие модули.**

## Прецеденты (на момент 2026-05)

```
# Cross-module shared — в const.py:
GO2RTC_RTSP_PORT     = 8554            # camera.py + go2rtc.py
DEFAULT_GO2RTC_*     = …               # config_flow + __init__ migration
AREA_*               = "Домофоны"…     # camera.py + lock.py

# Domain-specific timing — остаются в модуле:
camera.py:
    STREAM_RECOVERY_COOLDOWN              = 30.0
    GO2RTC_HEALTH_POLL_INTERVAL           = timedelta(seconds=30)
    GO2RTC_PROACTIVE_REFRESH_INTERVAL     = timedelta(minutes=28, seconds=30)
coordinator.py:
    UPDATE_INTERVAL                       = timedelta(minutes=5)
go2rtc.py:
    RTSP_PROBE_TIMEOUT_SEC                = 3.0
```

## Что НЕ делать

- 🔴 **НЕ выносить single-callsite timing/tuning в `const.py`** «на будущее».
  Это создаёт ложное впечатление cross-module контракта и тянет в diff'ы
  модули, которые менять не нужно. При появлении 2-го callsite — тогда
  и выносить (с обновлением references).
- 🔴 **НЕ дублировать**: одна константа = одно место объявления.
- 🔴 **НЕ создавать `const_<module>.py` модули**. Если константа shared
  но logically `tightly-coupled` к одному модулю — оставить в этом
  модуле и импортировать оттуда (как `GO2RTC_RTSP_PORT` мог бы жить
  в `go2rtc.py`, но раз он реально shared с camera.py — он в `const.py`).

## Когда применять

- **При добавлении** новой константы: пройти чек-лист «что выносить» выше,
  default — module-local.
- **При code-review**: P3 note «вынести X в const.py» допустим **только
  если** X уже используется ≥2 модулях или есть конкретный план на 2-й
  callsite.

## Связь

- [`const.py`](../../custom_components/elektronny_gorod/const.py) — единственный
  файл shared/identity констант.
- Прецеденты — module-headers `camera.py:48-72`, `go2rtc.py:13-19`,
  `coordinator.py:47-50`.
