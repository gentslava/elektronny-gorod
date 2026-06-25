import { describe, expect, it } from "vitest";

import { deriveView, toPhase } from "../src/state-machine.js";

describe("toPhase", () => {
  it("известные фазы проходят как есть", () => {
    for (const p of ["idle", "ringing", "connecting", "active", "ended", "error"]) {
      expect(toPhase(p)).toBe(p);
    }
  });

  it("unknown/unavailable/пусто → idle", () => {
    expect(toPhase("unknown")).toBe("idle");
    expect(toPhase("unavailable")).toBe("idle");
    expect(toPhase(undefined)).toBe("idle");
    expect(toPhase(null)).toBe("idle");
  });
});

describe("deriveView", () => {
  it("idle / ended → карточка скрыта", () => {
    expect(deriveView("idle").visible).toBe(false);
    expect(deriveView("ended").visible).toBe(false);
  });

  it("ringing → видео домофона + Принять/Отклонить/Открыть, без Завершить/микрофона", () => {
    const v = deriveView("ringing");
    expect(v).toMatchObject({
      visible: true,
      video: "doorbell",
      showAccept: true,
      showReject: true,
      showOpen: true,
      showHangup: false,
      showMic: false,
      showTimer: false,
    });
  });

  it("connecting → спиннер, Принять убран, Отклонить/Открыть есть", () => {
    const v = deriveView("connecting");
    expect(v.busy).toBe(true);
    expect(v.showAccept).toBe(false);
    expect(v.showReject).toBe(true);
    expect(v.showOpen).toBe(true);
  });

  it("active → видео вызова + Открыть/Микрофон/Завершить/таймер, без Принять", () => {
    const v = deriveView("active");
    expect(v).toMatchObject({
      visible: true,
      video: "call",
      showAccept: false,
      showHangup: true,
      showOpen: true,
      showMic: true,
      showTimer: true,
    });
  });

  it("error → видим, помечен isError, Завершить/Открыть доступны", () => {
    const v = deriveView("error");
    expect(v.visible).toBe(true);
    expect(v.isError).toBe(true);
    expect(v.showHangup).toBe(true);
    expect(v.showAccept).toBe(false);
  });
});
