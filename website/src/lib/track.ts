// Абстракция продуктовых событий. По умолчанию — no-op (никаких трекеров
// и cookies). Чтобы подключить приватную аналитику (Plausible, self-hosted
// умами и т.п.) — замените реализацию send().

export type SiteEvent =
  | "cta_hacs"
  | "cta_watch_demo"
  | "wizard_start"
  | "wizard_complete"
  | "automation_copy"
  | "open_github"
  | "open_releases"
  | "open_support";

export function track(event: SiteEvent, props?: Record<string, string>): void {
  send(event, props);
}

function send(event: SiteEvent, props?: Record<string, string>): void {
  if (import.meta.env.DEV) {
    console.debug("[track]", event, props ?? {});
  }
  // Продакшен: намеренно ничего не отправляем.
}
