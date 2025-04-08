# Интеграция Home Assistant с Электронным Городом

Это кастомная интеграция для Home Assistant, которая позволяет интегрироваться с сервисом Электронный Город (Новотелеком).

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
4. Найдите "Elektronny Gorod" и выберите его.
5. Следуйте инструкциям на экране для завершения настройки интеграции.

## Возможности

- Просмотр доступных контрактов и добавление нужных в любом количестве.
- Запрос и ввод SMS-кода или пароля для аутентификации.
- Получение превью и потоков с камер.
- Управление открытием замков в реальном времени.

## Проблемы и вклад

Если вы столкнулись с проблемами или у вас есть предложения по улучшению, пожалуйста, [откройте issue](https://github.com/gentslava/elektronny-gorod/issues) на GitHub.

Не стесняйтесь вносить вклад в проект, форкнув репозиторий и создавая pull-запросы.

## Благодарности

Типы устройств Apple https://gist.github.com/adamawolf/3048717

## Лицензия

Эта интеграция лицензирована под лицензией MIT. См. файл [LICENSE](LICENSE) для подробностей.
