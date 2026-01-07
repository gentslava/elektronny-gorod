[English](/README.md) | [Русский](/README.ru_RU.md)

<p>
  <img src="https://img.shields.io/badge/Home%20Assistant-2023.x-blue?logo=home-assistant" alt="Home Assistant"/>
  <img src="https://img.shields.io/badge/Custom%20Integration-orange" alt="Custom Integration"/>
  <img src="https://img.shields.io/badge/Elektronny%20Gorod-API-green" alt="Elektronny Gorod API"/>
  <img src="https://img.shields.io/badge/Dom.ru-API-red" alt="Dom.ru API"/>
  <img src="https://img.shields.io/badge/Intercoms,%20Cameras,%20Locks-lightgrey" alt="Devices"/>
  <img src="https://img.shields.io/badge/Русский%20язык-yes-blue" alt="Russian language"/>
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

Добавьте свои домофоны, камеры и замки в Home Assistant.

## Установка

### Вручную

Скопируйте директорию `custom_components/electronic_city` в директорию `config/custom_components` вашего Home Assistant.

```bash
git clone https://github.com/gentslava/elektronny-gorod.git
cp -r elektronny-gorod YOUR_HASS_CONFIG_DIR/custom_components/
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
- Просматривайте баланс аккаунта.

## Пример автоматизации
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

Типы устройств Apple https://gist.github.com/adamawolf/3048717

## Лицензия

Эта интеграция лицензирована под лицензией MIT. См. файл [LICENSE](LICENSE) для подробностей.
