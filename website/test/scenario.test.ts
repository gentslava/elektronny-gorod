import { describe, expect, it } from "vitest";

import { DEMO_PHASES } from "../src/demo/scenario";

// Контракт с карточкой: фазы демо = значения sensor.*_call_state из
// state-machine интеграции (frontend/src/state-machine.ts).
const CARD_PHASES = ["idle", "ringing", "connecting", "active", "ended", "error"];

describe("фазы демо", () => {
  it("совпадают с фазами state-machine карточки", () => {
    expect([...DEMO_PHASES].sort()).toEqual([...CARD_PHASES].sort());
  });
});
