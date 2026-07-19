// Единый источник ссылок и констант сайта. Значения, которые обязаны
// совпадать с репозиторием, перечислены в docs/sync.md.

export const project = {
  name: "Электронный город и Дом.ру для Home Assistant",
  shortName: "elektronny-gorod",
  version: "4.0.0",
  minHomeAssistant: "2024.10.4",
  license: "MIT",
  domain: "elektronny_gorod",
  repo: "https://github.com/gentslava/elektronny-gorod",
  issues: "https://github.com/gentslava/elektronny-gorod/issues",
  releases: "https://github.com/gentslava/elektronny-gorod/releases",
  changelog:
    "https://github.com/gentslava/elektronny-gorod/blob/master/CHANGELOG.md",
  readme:
    "https://github.com/gentslava/elektronny-gorod/blob/master/README.md",
  callScreenDocs:
    "https://github.com/gentslava/elektronny-gorod/blob/master/docs/features/intercom-two-way-audio/call-screen-setup.md",
  historyCardDocs:
    "https://github.com/gentslava/elektronny-gorod/blob/master/docs/features/mobile-app-parity/history-card.md",
  releaseNotes400:
    "https://github.com/gentslava/elektronny-gorod/blob/master/docs/releases/4.0.0.md",
  // Официальные deep links my.home-assistant.io — уже используются в README.
  hacsDeepLink:
    "https://my.home-assistant.io/redirect/hacs_repository/?owner=gentslava&repository=elektronny-gorod&category=integration",
  configFlowDeepLink:
    "https://my.home-assistant.io/redirect/config_flow_start/?domain=elektronny_gorod",
  boosty: "https://boosty.to/gentslava",
  yoomoney: "https://yoomoney.ru/to/410011558436973",
  hacsDocs: "https://hacs.xyz/docs/use/",
  haInstallDocs: "https://www.home-assistant.io/installation/",
  go2rtc: "https://github.com/AlexxIT/go2rtc",
} as const;

/** Реальные имена сервисов интеграции (services.yaml). */
export const services = {
  answer: "elektronny_gorod.answer",
  hangup: "elektronny_gorod.hangup",
} as const;

/**
 * Примеры entity_id в том же плейсхолдер-стиле, что README
 * (`YOUR_INTERCOM` / `YOUR_PHONE`). Без реальных адресов и договоров.
 */
export const entities = {
  doorbellEvent: "event.YOUR_INTERCOM_doorbell_call",
  callCamera: "camera.YOUR_INTERCOM_intercom_call",
  doorbellCamera: "camera.YOUR_INTERCOM",
  lock: "lock.YOUR_INTERCOM",
  callState: "sensor.YOUR_INTERCOM_call_state",
  balance: "sensor.elektronny_gorod_balance",
  history: "event.YOUR_ACCOUNT_place_YOUR_PLACE_event_history",
  notify: "notify.mobile_app_YOUR_PHONE",
} as const;

/** Lovelace-ресурсы, которые интеграция раздаёт статикой. */
export const lovelace = {
  callCardResource: "/elektronny_gorod_static/eg-intercom-call-card.js",
  micCardResource: "/elektronny_gorod_static/eg-intercom-mic-card.js",
  callCardType: "custom:eg-intercom-call-card",
  historyCardType: "custom:eg-event-history-card",
  micCardType: "custom:eg-intercom-mic-card",
} as const;
