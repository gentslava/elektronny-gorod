# website/ — продуктовый сайт интеграции

Одностраничный продуктовый хаб «Электронный город и Дом.ру для Home Assistant»:
живая демонстрация настоящей карточки вызова, интерактивный сценарий звонка,
playground, библиотека автоматизаций, мастер установки, проверка совместимости,
FAQ и блок доверия.

Сайт **изолирован от интеграции**: не трогает `custom_components/`, manifest,
HACS-конфигурацию и CI. Единственная связь — импорт production-бандла карточки
`custom_components/elektronny_gorod/www/eg-intercom-call-card.js` (сайт
демонстрирует именно shipped-артефакт, а не копию интерфейса).

Концепция и арт-дирекшн — [`docs/concept.md`](docs/concept.md).
Синхронизация данных с репозиторием — [`docs/sync.md`](docs/sync.md).
Публикация — [`docs/deploy.md`](docs/deploy.md).

## Локальный запуск

```bash
cd website
npm install
npm run dev        # http://localhost:5173
```

## Проверки

```bash
npm run typecheck  # tsc --noEmit
npm test           # vitest: compat / wizard / scenario / automations
npm run build      # прод-сборка в dist/
npm run preview    # http://localhost:4173 — сборка как в проде
```

Тесты покрывают критическую интерактивную логику: движок совместимости,
ветвление мастера установки, timeline hero-сценария и валидацию библиотеки
автоматизаций (реальные сервисы, плейсхолдеры без PII).

## Структура

```
website/
├── index.html            # весь статичный контент (SEO) + разметка секций
├── public/               # шрифты, favicon, og.jpg, изображения демо
├── src/
│   ├── main.ts           # подключение «островов»; сбой демо не ломает страницу
│   ├── styles/           # tokens.css (дизайн-токены, темы) + site.css
│   ├── data/             # единственный источник данных сайта:
│   │   ├── project.ts        #   ссылки, версии, entity/сервисы
│   │   ├── compatibility.ts  #   правила проверки совместимости
│   │   ├── wizard.ts         #   вопросы и логика мастера установки
│   │   └── automations.ts    #   библиотека YAML-сценариев
│   ├── demo/             # DemoHost: реальная карточка + mock hass (как frontend/demo)
│   ├── islands/          # hero, scenario, playground, automations, wizard, compat
│   └── lib/              # theme, reveal, copy, track (no-op аналитика)
├── test/                 # vitest
└── docs/                 # concept / sync / deploy / design-audit
```

## Принципы

- **Реальный интерфейс** — карточка в hero/демо это production-бандл интеграции;
  никаких «перерисованных» версий.
- **Симуляция без секретов** — сайт статический, не запрашивает пароли, SMS,
  токены и адреса HA; все данные аккаунта вводятся только в Home Assistant.
- **Один источник данных** — совместимость, мастер и автоматизации живут в
  `src/data/*` и покрыты тестами.
- **Доступность** — семантика, клавиатурная навигация, видимый фокус,
  `prefers-reduced-motion`, тексты не полагаются только на цвет.
- **Без трекеров** — `src/lib/track.ts` по умолчанию no-op; cookies не используются.
