// Фазы вызова — общий тип demo-слоя. Соответствует state-machine карточки
// (frontend/src/state-machine.ts интеграции): значения sensor.*_call_state.

export type DemoPhase =
  | "idle"
  | "ringing"
  | "connecting"
  | "active"
  | "ended"
  | "error";

export const DEMO_PHASES: readonly DemoPhase[] = [
  "idle",
  "ringing",
  "connecting",
  "active",
  "ended",
  "error",
];
