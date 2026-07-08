// Единый токен-слой карточки вызова: значения из макетов (pencil/design.pen) →
// theme-переменные Home Assistant с fallback. CSS custom properties наследуются
// сквозь shadow DOM — задаём `--eg-*` на :host карточки, дочерние компоненты
// (call-stage, open-control) берут `var(--eg-*)`. Никаких хардкод-hex в UI, кроме
// scrim и красного LIVE-бейджа. См. call-card-ux-production.md §12 + plan §Global Constraints.
import { css, type CSSResult } from "lit";

import type { CallPhase } from "../state-machine.js";

/** Токен-слой для `static styles`. Подключать первым: `styles = [egTokens, css\`…\`]`. */
export const egTokens: CSSResult = css`
  :host {
    --eg-primary: var(--primary-color, #03a9f4);
    --eg-success: var(--success-color, #4caf50);
    --eg-error: var(--error-color, #ef5350);
    --eg-warning: var(--warning-color, #ffb300);
    --eg-text: var(--primary-text-color, #e8e8e8);
    --eg-text-2: var(--secondary-text-color, #a6a6a6);
    --eg-text-3: var(--disabled-text-color, #787878);
    --eg-elevated: var(--secondary-background-color, #2a2a2a);
    --eg-card: var(--ha-card-background, var(--card-background-color, #1c1c1c));
    --eg-divider: var(--divider-color, #2e2e2e);
    --eg-on-fill: var(--text-primary-color, #ffffff);
    --eg-scrim: rgba(0, 0, 0, 0.72);
    --eg-r-card: 16px;
    --eg-r-md: 12px;
    --eg-r-full: 999px;
    --eg-mono: "Roboto Mono", ui-monospace, monospace;
    /* Тинты бейджей/баннеров = роль-цвет @ ~18% (эквивалент alpha 2E/1A из макета). */
    --eg-primary-bg: color-mix(in srgb, var(--eg-primary) 18%, transparent);
    --eg-success-bg: color-mix(in srgb, var(--eg-success) 18%, transparent);
    --eg-error-bg: color-mix(in srgb, var(--eg-error) 18%, transparent);
    --eg-warning-bg: color-mix(in srgb, var(--eg-warning) 18%, transparent);
  }
`;

/** Цвет статус-бейджа по фазе вызова (роль-переменная токен-слоя). */
const STATUS_COLOR: Record<CallPhase, string> = {
  idle: "var(--eg-text-2)",
  ringing: "var(--eg-warning)",
  connecting: "var(--eg-primary)",
  active: "var(--eg-success)",
  ended: "var(--eg-text-2)",
  error: "var(--eg-error)",
};

export function statusColor(phase: CallPhase): string {
  return STATUS_COLOR[phase] ?? "var(--eg-text-2)";
}
