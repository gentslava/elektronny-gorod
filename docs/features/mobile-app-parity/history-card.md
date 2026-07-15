# Карточка истории вызовов

`custom:eg-event-history-card` показывает предыдущие принятые и пропущенные
вызовы домофона из журнала приложения 9.9.0. Это отдельный browse-интерфейс:
открытие карточки не изменяет EventEntity и не запускает автоматизации.

## Подключение

Добавьте один Lovelace resource типа **JavaScript Module**:

```text
/elektronny_gorod_static/eg-intercom-call-card.js
```

Тот же bundle содержит и экран активного вызова, и карточку истории. После
обновления ресурса может потребоваться hard refresh браузера.

Найдите у устройства домофона entity «История вызовов домофона» и добавьте
карточку вручную:

```yaml
type: custom:eg-event-history-card
entity: event.podezd_1_istoriya_vyzovov_domofona
```

Необязательный заголовок:

```yaml
type: custom:eg-event-history-card
entity: event.podezd_1_istoriya_vyzovov_domofona
title: События у двери
```

Нужна именно history entity домофона с типами `call_accepted` и
`call_missed`, а не realtime entity активного звонка и не camera-motion
history entity.

## Поведение

- первая страница загружается при открытии карточки;
- «Показать ещё» читает следующую backend-страницу и убирает дубли по opaque
  event ID;
- «Обновить» заново читает page 0;
- даты и время форматируются в локали Home Assistant;
- backend-текст `message`, subscriber/account data и другие поля в браузер не
  передаются.

WebSocket-команда проверяет право текущего HA-пользователя на чтение указанной
EventEntity и жёстко связывает запрос с её config entry, place и домофоном.
Администратор HA не получает доступ к другому аккаунту через произвольный ID.

## Ограничения

- отображаются только подтверждённые capture-ом типы: принятый и пропущенный
  вызов;
- UI ограничивает запрос страниц диапазоном `0..100`;
- воспроизведение архивного видео по строке события пока не реализовано — это
  отдельный Media Source slice.
