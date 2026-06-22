[English](/README.en_EN.md) | [Русский](/README.md)

<p>
  <a href="https://hacs.xyz"><img src="https://img.shields.io/badge/HACS-Custom-41BDF5" alt="HACS Custom"/></a>
  <img src="https://img.shields.io/github/v/release/gentslava/elektronny-gorod?label=release&color=blue" alt="Release"/>
  <img src="https://img.shields.io/badge/Home%20Assistant-2024.10%2B-blue?logo=home-assistant" alt="Home Assistant"/>
  <img src="https://img.shields.io/github/license/gentslava/elektronny-gorod?color=green" alt="License"/>
  <img src="https://img.shields.io/badge/Custom%20Integration-orange" alt="Custom Integration"/>
  <img src="https://img.shields.io/badge/Elektronny%20Gorod-API-green" alt="Elektronny Gorod API"/>
  <img src="https://img.shields.io/badge/Dom.ru-API-red" alt="Dom.ru API"/>
  <img src="https://img.shields.io/badge/Intercoms,%20Cameras,%20Locks,%20Doorbell-lightgrey" alt="Devices"/>
  <img src="https://img.shields.io/badge/Русский%20язык-yes-blue" alt="Russian language"/>
  <a href="https://boosty.to/gentslava"><img src="https://img.shields.io/badge/Boosty-Поддержать-FF6F31" alt="Поддержать на Boosty"/></a>
  <a href="https://yoomoney.ru/to/410011558436973"><img src="https://img.shields.io/badge/YooMoney-Поддержать-8B3FFD" alt="Поддержать через YooMoney"/></a>
</p>

# Интеграция Home Assistant с Электронным Городом и Дом.ру

<table>
  <tr>
    <td align="center">
      <a href="https://2090000.ru/domofony/"><img src="https://domconnect.ru/uploads/2434555b0__domconnect.ru.png" alt="Электронный город (Новотелеком) лого" height="120"/></a>
    </td>
    <td align="center">
      <a href="https://play.google.com/store/apps/details?id=ru.inetra.intercom"><img src="https://play-lh.googleusercontent.com/eCp35NcuGq1V0igXhGrPE6tprf7wGg00dY6TuVvRrqRSiEMTS6yQePuWxEIx3G0EMJ0l=w240-h480-rw" alt="Приложение Мой дом лого" height="120"/></a>
    </td>
  </tr>
  <tr>
    <td align="center">
      <a href="https://dom.ru/domofon"><img src="https://internet-domru.ru/assets/images/logo.png" alt="Дом.ру лого" height="120"/></a>
    </td>
    <td align="center">
      <a href="https://play.google.com/store/apps/details?id=com.ertelecom.smarthome"><img src="https://play-lh.googleusercontent.com/dN4M3FlqpX9a_HacE8jx4QQpnYH8u869U6_SaTaCSY-oZFeI17Zw4ZNlpWxRbe4DxSM=w240-h480-rw" alt="Приложение Умный Дом.ру лого" height="120"/></a>
    </td>
  </tr>
</table>

Это кастомная интеграция для Home Assistant, которая позволяет интегрироваться с сервисами Электронный Город (Новотелеком) и Дом.ру, реализуя API приложений Мой Дом – Электронный город и Умный Дом.ру.

Добавьте в Home Assistant свои **домофоны, камеры и замки**: смотрите видео и слушайте звук, открывайте двери и — **в реальном времени** — получайте **события звонка в домофон** (FCM push) для уведомлений и автоматизаций.

> 🔔 **Новое:** теперь интеграция ловит **звонок в домофон** и отдаёт его как `event`-сущность — можно слать пуш с кадром камеры и кнопкой «Открыть дверь». См. раздел [Событие звонка в домофон](#-событие-звонка-в-домофон-fcm-push).

## Содержание

- [Установка](#установка)
- [Конфигурация](#конфигурация)
- [Возможности](#возможности)
- [Подключение камер через go2rtc](#подключение-камер-через-go2rtc)
- [🔔 Событие звонка в домофон (FCM push)](#-событие-звонка-в-домофон-fcm-push)
- [Пример автоматизации: баланс](#пример-автоматизации-баланс)
- [Проблемы и вклад](#проблемы-и-вклад)
- [Лицензия](#лицензия)

## Установка

### Вручную

Скопируйте директорию `custom_components/elektronny_gorod` в директорию `config/custom_components` вашего Home Assistant.

```bash
git clone https://github.com/gentslava/elektronny-gorod.git
cp -r elektronny-gorod/custom_components/elektronny_gorod YOUR_HASS_CONFIG_DIR/custom_components/
```

Перезапустите Home Assistant.


### Через [HACS](https://hacs.xyz/)
<a href="https://my.home-assistant.io/redirect/hacs_repository/?owner=gentslava&repository=elektronny-gorod&category=integration" target="_blank"><img src="https://my.home-assistant.io/badges/hacs_repository.svg" alt="Откройте ваш экземпляр Home Assistant и откройте репозиторий в магазине Home Assistant Community." /></a>

## Конфигурация
<a href="https://my.home-assistant.io/redirect/config_flow_start/?domain=elektronny_gorod" target="_blank"><img src="https://my.home-assistant.io/badges/config_flow_start.svg" alt="Откройте ваш экземпляр Home Assistant и начните настройку новой интеграции." /></a>

или вручную:

1. Перейдите в интерфейс Home Assistant.
2. Перейдите в Конфигурация -> Интеграции.
3. Нажмите кнопку "+" для добавления новой интеграции.
4. Найдите "Электронный город" и выберите его.
5. Следуйте инструкциям на экране для завершения настройки интеграции.

## Возможности

- Интеграция с сервисами Электронный Город и Дом.ру (работает с приложениями Мой Дом и Умный Дом.ру).
- Просмотр доступных договоров и добавление нужных в любом количестве.
- Запрос и ввод SMS-кода или пароля для аутентификации.
- Добавление доступных домофонов, камер и замков.
- Получение превью и потоков с домофонов и камер.
- Управление открытием замков в реальном времени.
- **Событие звонка в домофон в реальном времени** (FCM push) — `event`-сущность для уведомлений и автоматизаций (показать камеру, открыть дверь).
- Просматривайте баланс аккаунта.

Создаваемые типы сущностей: `camera` (видео/превью), `lock` (открытие двери), `event` (звонок домофона), `sensor` (баланс и др.), `binary_sensor`, `switch`.

> **Новое:** Теперь поддерживается подключение камер через [go2rtc](https://github.com/AlexxIT/go2rtc) — этот способ позволяет получать звук с камер, а также обеспечивает более быструю и стабильную работу видеопотока.

## Подключение камер через go2rtc

Поддерживается интеграция с [go2rtc](https://github.com/AlexxIT/go2rtc) для камер Электронного города и Дом.ру. Этот способ позволяет:
- Получать аудиопоток с камер (звук).
- Получать более быстрый и стабильный видеопоток (низкая задержка, меньше обрывов).

### Как подключить

1. Установите и настройте [go2rtc](https://github.com/AlexxIT/go2rtc) в Home Assistant (через HACS или вручную).
2. В настройках интеграции Электронный Город/Дом.ру выберите способ передачи потока через go2rtc (или укажите ссылку на go2rtc в настройках камеры).
3. После этого камеры будут автоматически отображаться в Home Assistant с поддержкой аудио и улучшенным видео.

#### Использование с уже настроенными интеграциями

Если у вас уже настроены камеры через стандартную интеграцию, просто включите поддержку go2rtc в настройках интеграции или камеры — повторное добавление устройств не требуется.

**Примечание:** Для работы аудио и низкой задержки убедитесь, что ваша версия go2rtc и Home Assistant актуальны.

## 🔔 Событие звонка в домофон (FCM push)

Интеграция получает **звонок в домофон в реальном времени** через FCM-push — так же, как мобильное приложение, без облачного опроса. На каждый домофон создаётся сущность `event` с классом устройства `doorbell`:

- **`event.<домофон>_doorbell_call`** — стреляет `ring` при входящем вызове и `ended` при завершении (приняли на другом устройстве или истёк таймаут ожидания).
- Атрибуты события: `event_type` (`ring`/`ended`), `gate_name` (домофон), `apartment` (квартира), `call_id`, `allow_open`, `reason`.

На этом строятся автоматизации: пуш с кадром камеры и кнопкой «Открыть дверь», показ видео, открытие замка.

> Канал — приватный FCM-приём (зависимость `firebase-messaging` ставится автоматически). Весь FCM-флоу под graceful degradation: при сбое остальная интеграция (камеры, замки, баланс) продолжает работать.
>
> В примерах замените `YOUR_INTERCOM` / `YOUR_PHONE` на свои сущности (Инструменты разработчика → Состояния, фильтры `event.` / `notify.mobile_app`). Кадр в пуше и кнопки действий работают через приложение **Home Assistant Companion** (Android/iOS).

### Пример 1. Пуш при звонке

```yaml
automation:
  - alias: "Домофон: уведомление о звонке"
    mode: parallel
    triggers:
      - trigger: state
        entity_id: event.YOUR_INTERCOM_doorbell_call
    conditions:
      - "{{ trigger.to_state.attributes.event_type == 'ring' }}"
    actions:
      - action: notify.mobile_app_YOUR_PHONE
        data:
          title: "🔔 Звонок в домофон"
          message: "{{ trigger.to_state.attributes.gate_name }} · кв. {{ trigger.to_state.attributes.apartment }}"
```

### Пример 2. Пуш с кадром камеры и кнопкой «Открыть дверь»

```yaml
automation:
  # 1) Уведомление с превью камеры и кнопкой действия
  - alias: "Домофон: пуш с камерой и открытием"
    mode: parallel
    triggers:
      - trigger: state
        entity_id: event.YOUR_INTERCOM_doorbell_call
    conditions:
      - "{{ trigger.to_state.attributes.event_type == 'ring' }}"
    actions:
      - action: notify.mobile_app_YOUR_PHONE
        data:
          title: "🔔 Звонок в домофон"
          message: "{{ trigger.to_state.attributes.gate_name }}"
          data:
            image: "/api/camera_proxy/camera.YOUR_INTERCOM"
            tag: "doorbell"
            actions:
              - action: "OPEN_DOOR"
                title: "🔓 Открыть дверь"

  # 2) Обработчик кнопки: открыть замок домофона
  - alias: "Домофон: открыть дверь по кнопке пуша"
    triggers:
      - trigger: event
        event_type: mobile_app_notification_action
        event_data:
          action: "OPEN_DOOR"
    actions:
      - action: lock.unlock
        target:
          entity_id: lock.YOUR_INTERCOM
```

## Пример автоматизации: баланс
Вот пример автоматизации для уведомления о низком балансе:

```yaml
automation:
  - alias: "Уведомление о низком балансе"
    trigger:
      - platform: numeric_state
        entity_id: sensor.elektronny_gorod_balance
        below: 100
    action:
      - service: notify.notify
        data:
          message: "Баланс вашего счета в Электронном городе ниже 100 рублей."
```

## Проблемы и вклад

Если вы столкнулись с проблемами или у вас есть предложения по улучшению, пожалуйста, [откройте issue](https://github.com/gentslava/elektronny-gorod/issues) на GitHub.

Не стесняйтесь вносить вклад в проект, форкнув репозиторий и создавая pull-запросы.

## Благодарности

❤️ **Спасибо всем донатерам**, поддержавшим интеграцию рублём — ваша поддержка мотивирует развивать проект дальше.

Поддержать разработку: [![Boosty](https://img.shields.io/badge/Boosty-Поддержать%20проект-FF6F31)](https://boosty.to/gentslava) [![YooMoney](https://img.shields.io/badge/YooMoney-Перевести-8B3FFD)](https://yoomoney.ru/to/410011558436973)

Типы устройств Apple https://gist.github.com/adamawolf/3048717

[go2rtc](https://github.com/AlexxIT/go2rtc) — проект для работы с потоковым видео и аудио

## Лицензия

Эта интеграция лицензирована под лицензией MIT. См. файл [LICENSE](LICENSE) для подробностей.
