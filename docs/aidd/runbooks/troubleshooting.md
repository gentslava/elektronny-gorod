# Runbook: Troubleshooting

Когда пользователь приходит с проблемой — что спрашивать, что подсказать.

## Шаг 0: Запросить базовую информацию

В issue или discord:

1. Версия HA Core: Settings → About.
2. Версия интеграции: из HACS / `manifest.json`.
3. Что пытались сделать.
4. Что произошло.
5. Релевантный лог с уровнем `debug` (см. [`debugging.md`](debugging.md)).
6. Если возможно — diagnostics (когда появится — см. A-23).

🔴 **Не просить** debug-лог пользователя до hotfix-релиза security-фиксов: в логах сейчас утечка токена. Альтернатива — попросить *anonymized* фрагмент.

## Частые проблемы

### «Интеграция не появляется в списке после установки»

- HACS не подхватил релиз → restart HA после установки через HACS.
- Файлы попали не в тот `custom_components/`.

### «Config flow зависает / ошибка `unknown_status`»

- API оператора недоступен временно.
- Сменился ToS / API — нужен update.
- Проверить логи: какой endpoint возвращает 500/502.

### «`invalid_phone` несмотря на корректный номер»

- Формат: должен быть с `+7` или `8` (зависит от оператора).
- В будущем — формализовать в config_flow validation.

### «`limit_exceeded` при запросе SMS»

- Оператор лимитирует SMS. Подождать 5-15 минут.
- Использовать **password** или **access_token** ветку config_flow вместо SMS.

### «Камера показывает `unavailable` всегда»

- Stream URL пуст (см. [`camera.py:200-205`](../../../custom_components/elektronny_gorod/camera.py#L200-L205)).
- Может быть связано с A-06 (баг `c.get("ID")` в `update_camera_state`).
- Проверить: `update_camera_state` падает с `UpdateFailed` → entity получает старое состояние.

### «Снимок камеры не обновляется»

- `async_camera_image` использует `self._image` cache. После 3.0.5 — возвращает None при unavailable.
- Возможные причины: API возвращает 401 (нужен refresh token) или stream истёк.

### «Открытие замка отрабатывает, но lock остаётся `locked`»

- Это by design: `fake_timer_lock` через `asyncio.sleep(5)` (см. [`lock.py:112-115`](../../../custom_components/elektronny_gorod/lock.py#L112-L115)).
- Будет исправлено в ADR-0005 (lock → button).

### «Низкий баланс не вызывает автоматизацию»

- Баланс **не обновляется** автоматически без `update_interval` (A-08).
- Workaround: ручной reload integration через UI.
- Постоянный fix — в Итерации 2 (coordinator pattern).

### «go2rtc валидация падает с `go2rtc_unreachable`»

- Проверить URL: должен быть `http://HOST:PORT` без trailing slash.
- Проверить network: HA должен иметь доступ к go2rtc.
- Если go2rtc требует Basic Auth — указать username/password (новое в 3.0.5).
- Логи go2rtc на той стороне.

### «После рестарта HA — entity disappeared»

- `_subscriber_places` не загрузились (`_async_update_data` упал).
- Проверить лог: `Integration start failed`.
- Возможные причины: 401 (токен истёк), 500 (API проблемы).
- Workaround: reauth через UI (повторное прохождение config flow с тем же телефоном).

## Когда эскалировать

- Если симптом не покрыт выше — issue в [GitHub](https://github.com/gentslava/HA-ElektronnyGorod/issues).
- Перед открытием issue — поискать существующие открытые.

## Что не помогает пользователю

- ❌ «Переустановите HACS» (редко помогает, маскирует проблему).
- ❌ «Удалите и пересоздайте entry» (теряется история).
- ❌ «Обновите HA до самой свежей» (часто не относится).

## Что обычно помогает

- ✅ Перезапустить именно интеграцию (Reload через UI).
- ✅ Проверить лог конкретно за `custom_components.elektronny_gorod`.
- ✅ Reauth через config_flow с тем же номером.
- ✅ Скачать pre-release из PR с фиксом (через HACS Custom repository), если фикс готов.

## Next reading

- [`debugging.md`](debugging.md) — systematic подход
- [`../../audit/project-audit.md`](../../audit/project-audit.md) — известные проблемы
- [`release.md`](release.md) — как выкатить hotfix
