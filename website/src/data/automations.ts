// Библиотека автоматизаций. Только реальные сущности и сервисы проекта:
// плейсхолдеры YOUR_INTERCOM / YOUR_PHONE — в стиле README.
// Категории: "ring" — сценарии на событии звонка (рендерятся одним блоком
// с переключателем), "standalone" — самостоятельные сценарии.
// Каждая запись проверяется тестом (test/automations.test.ts).

export type Difficulty = "easy" | "medium";
export type RecipeCategory = "ring" | "standalone";

export interface AutomationRecipe {
  id: string;
  category: RecipeCategory;
  /** dashboard — рецепт вкладки Lovelace, а не автоматизации. */
  kind?: "automation" | "dashboard";
  /** Короткая метка для переключателя ring-блока. */
  tab?: string;
  title: string;
  /** Человеческое объяснение — зачем это в жизни. */
  story: string;
  /** Цепочка «триггер → действия» для визуальной подачи. */
  chain: string[];
  difficulty: Difficulty;
  entities: string[];
  /** Дополнительные компоненты, без которых сценарий не заработает. */
  requires: string[];
  yaml: string;
}

export const AUTOMATIONS: AutomationRecipe[] = [
  /* ---------- Сценарии на событии звонка (event: ring / ended) ---------- */
  {
    id: "push-with-camera",
    category: "ring",
    tab: "Пуш с кадром и кнопкой",
    title: "Пуш с кадром камеры и кнопкой «Открыть дверь»",
    story:
      "В уведомлении сразу видно, кто пришёл, а кнопка открывает дверь — не открывая приложение.",
    chain: ["event: ring", "кадр камеры", "push с кнопкой", "lock.unlock"],
    difficulty: "medium",
    entities: [
      "event.YOUR_INTERCOM_doorbell_call",
      "camera.YOUR_INTERCOM",
      "lock.YOUR_INTERCOM",
      "notify.mobile_app_YOUR_PHONE",
    ],
    requires: ["Приложение Home Assistant Companion"],
    yaml: `automation:
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

  - alias: "Домофон: открыть дверь по кнопке пуша"
    triggers:
      - trigger: event
        event_type: mobile_app_notification_action
        event_data:
          action: "OPEN_DOOR"
    actions:
      - action: lock.unlock
        target:
          entity_id: lock.YOUR_INTERCOM`,
  },
  {
    id: "push-on-ring",
    category: "ring",
    tab: "Просто пуш",
    title: "Пуш при звонке в домофон",
    story:
      "Минимальный вариант: кто-то позвонил — телефон сразу сообщает, какой подъезд и какая квартира. Работает даже если вы не дома.",
    chain: ["event: ring", "notify → телефон"],
    difficulty: "easy",
    entities: ["event.YOUR_INTERCOM_doorbell_call", "notify.mobile_app_YOUR_PHONE"],
    requires: ["Приложение Home Assistant Companion"],
    yaml: `automation:
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
          message: "{{ trigger.to_state.attributes.gate_name }} · кв. {{ trigger.to_state.attributes.apartment }}"`,
  },
  {
    id: "missed-call",
    category: "ring",
    tab: "Пропущенный вызов",
    title: "Пуш о пропущенном звонке",
    story:
      "Никто не успел ответить — придёт отдельное уведомление. Вы узнаете, что кто-то приходил, даже если все были заняты.",
    chain: ["event: ended", "reason: timeout", "notify → телефон"],
    difficulty: "easy",
    entities: ["event.YOUR_INTERCOM_doorbell_call", "notify.mobile_app_YOUR_PHONE"],
    requires: ["Приложение Home Assistant Companion"],
    yaml: `automation:
  - alias: "Домофон: пропущенный звонок"
    mode: queued
    triggers:
      - trigger: state
        entity_id: event.YOUR_INTERCOM_doorbell_call
    conditions:
      - "{{ trigger.to_state.attributes.event_type == 'ended' }}"
      - "{{ trigger.to_state.attributes.reason == 'timeout' }}"
    actions:
      - action: notify.mobile_app_YOUR_PHONE
        data:
          title: "📵 Пропущенный звонок в домофон"
          message: "{{ trigger.to_state.attributes.gate_name }} — никто не ответил"`,
  },
  {
    id: "hallway-light",
    category: "ring",
    tab: "Свет в прихожей",
    title: "Свет в прихожей при вечернем звонке",
    story:
      "После заката звонок в домофон включает свет в прихожей — удобно встречать гостей и не искать выключатель.",
    chain: ["event: ring", "после заката", "light.turn_on"],
    difficulty: "easy",
    entities: ["event.YOUR_INTERCOM_doorbell_call", "light.YOUR_HALLWAY"],
    requires: [],
    yaml: `automation:
  - alias: "Домофон: свет в прихожей вечером"
    triggers:
      - trigger: state
        entity_id: event.YOUR_INTERCOM_doorbell_call
    conditions:
      - "{{ trigger.to_state.attributes.event_type == 'ring' }}"
      - condition: sun
        after: sunset
    actions:
      - action: light.turn_on
        target:
          entity_id: light.YOUR_HALLWAY`,
  },
  {
    id: "mute-media",
    category: "ring",
    tab: "Тише медиа",
    title: "Приглушить музыку и телевизор",
    story:
      "Звонок в дверь — колонки и телевизор тихонько убавляются, чтобы вы его точно услышали.",
    chain: ["event: ring", "volume → 20%"],
    difficulty: "easy",
    entities: ["event.YOUR_INTERCOM_doorbell_call", "media_player.YOUR_SPEAKER"],
    requires: [],
    yaml: `automation:
  - alias: "Домофон: приглушить медиа при звонке"
    triggers:
      - trigger: state
        entity_id: event.YOUR_INTERCOM_doorbell_call
    conditions:
      - "{{ trigger.to_state.attributes.event_type == 'ring' }}"
    actions:
      - action: media_player.volume_set
        target:
          entity_id: media_player.YOUR_SPEAKER
        data:
          volume_level: 0.2`,
  },
  {
    id: "family-notify",
    category: "ring",
    tab: "Вся семья",
    title: "Уведомить всех членов семьи",
    story:
      "Звонок приходит каждому: кто первый свободен — тот и ответил. Никто не бежит через всю квартиру.",
    chain: ["event: ring", "notify × вся семья"],
    difficulty: "easy",
    entities: [
      "event.YOUR_INTERCOM_doorbell_call",
      "notify.mobile_app_YOUR_PHONE",
      "notify.mobile_app_FAMILY_PHONE",
    ],
    requires: ["Приложение Home Assistant Companion у каждого"],
    yaml: `automation:
  - alias: "Домофон: уведомить всю семью"
    mode: parallel
    triggers:
      - trigger: state
        entity_id: event.YOUR_INTERCOM_doorbell_call
    conditions:
      - "{{ trigger.to_state.attributes.event_type == 'ring' }}"
    actions:
      - parallel:
          - action: notify.mobile_app_YOUR_PHONE
            data:
              title: "🔔 Звонок в домофон"
              message: "{{ trigger.to_state.attributes.gate_name }}"
          - action: notify.mobile_app_FAMILY_PHONE
            data:
              title: "🔔 Звонок в домофон"
              message: "{{ trigger.to_state.attributes.gate_name }}"`,
  },
  {
    id: "logbook-entry",
    category: "ring",
    tab: "Журнал",
    title: "Записывать звонки в журнал",
    story:
      "Каждый звонок остаётся в журнале Home Assistant: удобно посмотреть, когда приходил курьер, пока вас не было.",
    chain: ["event: ring", "logbook.log"],
    difficulty: "easy",
    entities: ["event.YOUR_INTERCOM_doorbell_call"],
    requires: [],
    yaml: `automation:
  - alias: "Домофон: запись в журнал"
    mode: queued
    triggers:
      - trigger: state
        entity_id: event.YOUR_INTERCOM_doorbell_call
    conditions:
      - "{{ trigger.to_state.attributes.event_type == 'ring' }}"
    actions:
      - action: logbook.log
        data:
          name: "Домофон"
          message: >-
            Звонок: {{ trigger.to_state.attributes.gate_name }},
            кв. {{ trigger.to_state.attributes.apartment }}`,
  },
  {
    id: "tablet-call-screen",
    category: "ring",
    tab: "Настенный планшет",
    title: "Экран вызова на настенном планшете",
    story:
      "Планшет в коридоре сам открывает экран вызова с видео и кнопками — как настоящая видеопанель домофона.",
    chain: ["event: ring", "экран /doorbell-call/call"],
    difficulty: "medium",
    entities: ["event.YOUR_INTERCOM_doorbell_call"],
    requires: [
      "Готовые blueprint-ы интеграции (doorbell_screen_controller)",
      "Дашборд /doorbell-call/call из инструкции по экрану вызова",
    ],
    yaml: `# Рекомендуемый способ — готовый blueprint doorbell_screen_controller:
# он сам ведёт экран вызова по состоянию звонка и обрабатывает открытие
# двери из пуша. Импорт и настройка — в docs/features/intercom-two-way-audio/
# call-screen-setup.md. Вариант вручную (Companion-приложение планшета):
automation:
  - alias: "Домофон: экран вызова на планшете"
    triggers:
      - trigger: state
        entity_id: event.YOUR_INTERCOM_doorbell_call
    conditions:
      - "{{ trigger.to_state.attributes.event_type == 'ring' }}"
    actions:
      - action: notify.mobile_app_YOUR_TABLET
        data:
          message: "command_webview"
          data:
            command: "/doorbell-call/call"`,
  },

  /* ---------- Самостоятельные сценарии ---------- */
  {
    id: "camera-panel",
    category: "standalone",
    kind: "dashboard",
    title: "Панель всех камер дома",
    story:
      "Калитки, подъезд, двор и лифты — одной вкладкой дашборда. На превью калитки и подъезда — иконка замка: открыть можно прямо с панели.",
    chain: ["камеры интеграции", "вкладка «Камеры»", "замок прямо на превью"],
    difficulty: "easy",
    entities: [
      "camera.YOUR_GATE_CAMERA",
      "camera.YOUR_INTERCOM",
      "camera.YOUR_ELEVATOR_CAMERA",
      "lock.YOUR_INTERCOM",
    ],
    requires: [],
    yaml: `# Это вкладка дашборда, а не автоматизация: Настройки → Панели →
# карандаш → «Добавить вкладку» → ⋮ → «Редактировать в YAML».
title: Камеры
path: cameras
icon: mdi:cctv
cards:
  - type: picture-glance
    title: Внешняя калитка
    camera_image: camera.YOUR_GATE_CAMERA
    camera_view: auto
    entities:
      - lock.YOUR_GATE
  - type: picture-glance
    title: Подъезд
    camera_image: camera.YOUR_INTERCOM
    camera_view: auto
    entities:
      - lock.YOUR_INTERCOM
  - type: picture-entity
    entity: camera.YOUR_YARD_CAMERA
    name: Двор
    camera_view: auto
  - type: picture-entity
    entity: camera.YOUR_ELEVATOR_CAMERA
    name: Лифт
    camera_view: auto`,
  },
  {
    id: "locks-panel",
    category: "standalone",
    kind: "dashboard",
    title: "Панель замков «Безопасность дома»",
    story:
      "Все двери дома — калитки, подъезд — одной колонкой: видно, что закрыто, и каждую можно открыть одним нажатием.",
    chain: ["замки интеграции", "tile-карточки", "открытие одним нажатием"],
    difficulty: "easy",
    entities: ["lock.YOUR_GATE", "lock.YOUR_INNER_GATE", "lock.YOUR_INTERCOM"],
    requires: [],
    yaml: `# Вкладка или секция дашборда: Настройки → Панели → «Добавить вкладку»
# → ⋮ → «Редактировать в YAML».
title: Безопасность
path: security
icon: mdi:shield-home
cards:
  - type: tile
    entity: lock.YOUR_GATE
    name: Внешняя калитка
    features:
      - type: lock-commands
  - type: tile
    entity: lock.YOUR_INNER_GATE
    name: Внутренняя калитка
    features:
      - type: lock-commands
  - type: tile
    entity: lock.YOUR_INTERCOM
    name: Подъезд
    features:
      - type: lock-commands`,
  },
  {
    id: "face-known",
    category: "standalone",
    title: "Распознавание лиц у подъезда",
    story:
      "RTSP-поток камеры уходит в Frigate + Double Take: дом узнаёт своих и шлёт пуш с именем. Дальше — на ваш вкус: включить свет, показать панель, а открывать дверь автоматически — только осознанно: фото может обмануть камеру.",
    chain: ["RTSP → Frigate", "лицо: свои", "notify → телефон"],
    difficulty: "medium",
    entities: ["notify.mobile_app_YOUR_PHONE", "camera.YOUR_INTERCOM"],
    requires: [
      "Включённая публикация внешнего RTSP (настройки интеграции)",
      "Frigate + Double Take (или другой распознаватель) и MQTT",
    ],
    yaml: `automation:
  - alias: "Подъезд: знакомое лицо у двери"
    mode: queued
    triggers:
      - trigger: mqtt
        topic: double-take/matches/YOUR_NAME
    actions:
      - action: notify.mobile_app_YOUR_PHONE
        data:
          title: "👋 У подъезда — свои"
          message: "Камера подъезда узнала: YOUR_NAME"`,
  },
  {
    id: "night-dnd",
    category: "standalone",
    title: "«Не беспокоить» по ночам",
    story:
      "С 23:00 до 7:00 домофон не звонит в квартиру — а утром режим выключается сам. Пуши при этом продолжают приходить.",
    chain: ["23:00 · 07:00", "switch: не беспокоить"],
    difficulty: "easy",
    entities: ["switch.YOUR_PLACE_dnd_intercom_calls"],
    requires: [],
    yaml: `automation:
  - alias: "Домофон: тихие часы включить"
    triggers:
      - trigger: time
        at: "23:00:00"
    actions:
      - action: switch.turn_on
        target:
          entity_id: switch.YOUR_PLACE_dnd_intercom_calls

  - alias: "Домофон: тихие часы выключить"
    triggers:
      - trigger: time
        at: "07:00:00"
    actions:
      - action: switch.turn_off
        target:
          entity_id: switch.YOUR_PLACE_dnd_intercom_calls`,
  },
  {
    id: "bedside-button",
    category: "standalone",
    title: "Открыть дверь кнопкой у кровати",
    story:
      "Курьер рано утром? Любая физическая кнопка умного дома открывает подъезд — телефон можно не искать.",
    chain: ["кнопка: нажата", "lock.unlock"],
    difficulty: "easy",
    entities: ["binary_sensor.YOUR_BUTTON", "lock.YOUR_INTERCOM"],
    requires: ["Любая кнопка или выключатель, добавленные в Home Assistant"],
    yaml: `automation:
  - alias: "Домофон: открыть дверь кнопкой"
    triggers:
      - trigger: state
        entity_id: binary_sensor.YOUR_BUTTON
        to: "on"
    actions:
      - action: lock.unlock
        target:
          entity_id: lock.YOUR_INTERCOM`,
  },
  {
    id: "low-balance",
    category: "standalone",
    title: "Предупреждение о низком балансе",
    story:
      "Баланс договора опустился ниже 100 ₽ — приходит напоминание пополнить, пока домофон и камеры не отключились.",
    chain: ["balance < 100 ₽", "notify → телефон"],
    difficulty: "easy",
    entities: ["sensor.elektronny_gorod_balance", "notify.mobile_app_YOUR_PHONE"],
    requires: [],
    yaml: `automation:
  - alias: "Уведомление о низком балансе"
    triggers:
      - trigger: numeric_state
        entity_id: sensor.elektronny_gorod_balance
        below: 100
    actions:
      - action: notify.mobile_app_YOUR_PHONE
        data:
          title: "💳 Электронный город"
          message: "Баланс ниже 100 ₽ — пора пополнить счёт."`,
  },
  {
    id: "days-to-block",
    category: "standalone",
    title: "За три дня до блокировки",
    story:
      "Интеграция знает, сколько дней осталось до отключения договора, — напоминание придёт заранее, а не когда домофон уже замолчал.",
    chain: ["days_to_block < 3", "notify → телефон"],
    difficulty: "easy",
    entities: ["sensor.YOUR_PLACE_days_to_block", "notify.mobile_app_YOUR_PHONE"],
    requires: [],
    yaml: `automation:
  - alias: "Электронный город: скоро блокировка"
    triggers:
      - trigger: numeric_state
        entity_id: sensor.YOUR_PLACE_days_to_block
        below: 3
    actions:
      - action: notify.mobile_app_YOUR_PHONE
        data:
          title: "⚠️ Договор скоро заблокируют"
          message: "Осталось {{ states('sensor.YOUR_PLACE_days_to_block') }} дн. — пополните счёт."`,
  },
  {
    id: "evening-snapshot",
    category: "standalone",
    title: "Вечерний снимок двора в медиатеку",
    story:
      "Каждый вечер — кадр дворовой камеры в медиатеку Home Assistant: неделю у дома можно пролистать за минуту.",
    chain: ["21:00", "camera.snapshot → /media"],
    difficulty: "easy",
    entities: ["camera.YOUR_YARD_CAMERA"],
    requires: ["Папка /media, доступная Home Assistant для записи"],
    yaml: `automation:
  - alias: "Двор: вечерний снимок в медиатеку"
    triggers:
      - trigger: time
        at: "21:00:00"
    actions:
      - action: camera.snapshot
        target:
          entity_id: camera.YOUR_YARD_CAMERA
        data:
          filename: "/media/yard/{{ now().strftime('%Y-%m-%d') }}.jpg"`,
  },
];

export const DIFFICULTY_LABELS: Record<Difficulty, string> = {
  easy: "Просто",
  medium: "Средне",
};
