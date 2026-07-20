import { describe, expect, it } from "vitest";

import { DemoHost } from "../src/demo/demo-host";
import { DEMO_PHASES } from "../src/demo/scenario";

// Контракт с карточкой: фазы демо = значения sensor.*_call_state из
// state-machine интеграции (frontend/src/state-machine.ts).
const CARD_PHASES = ["idle", "ringing", "connecting", "active", "ended", "error"];

describe("фазы демо", () => {
  it("совпадают с фазами state-machine карточки", () => {
    expect([...DEMO_PHASES].sort()).toEqual([...CARD_PHASES].sort());
  });

  it("сбрасывает удерживаемый ended при переходе обратно в idle", () => {
    const host = new DemoHost({} as HTMLElement, { phase: "ended" });
    const card = {
      _endedEntity: "sensor.intercom_call_state",
      _clearEnded() {
        this._endedEntity = "";
      },
      updateComplete: Promise.resolve(),
      requestUpdate() {},
    };
    (host as unknown as { card: typeof card }).card = card;

    host.setPhase("idle");

    expect(card._endedEntity).toBe("");
  });
});
