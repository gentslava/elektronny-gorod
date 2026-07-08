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
  it("idle → карточка скрыта", () => {
    expect(deriveView("idle").visible).toBe(false);
  });

  it("ended → краткий экран «Вызов завершён» с [Закрыть]", () => {
    const v = deriveView("ended");
    expect(v.visible).toBe(true);
    expect(v.actions).toEqual(["close"]);
    expect(v.showOpen).toBe(true);
  });

  it("ringing → видео домофона + [Отклонить, Принять] + Открыть + окно ответа", () => {
    const v = deriveView("ringing");
    expect(v).toMatchObject({
      visible: true,
      video: "doorbell",
      actions: ["reject", "accept"],
      showOpen: true,
      showAnswerWindow: true,
      showTimer: false,
    });
  });

  it("connecting → busy + [Отменить, «Соединяем…»] + Открыть", () => {
    const v = deriveView("connecting");
    expect(v.busy).toBe(true);
    expect(v.actions).toEqual(["cancel", "connecting"]);
    expect(v.showOpen).toBe(true);
    expect(v.showAnswerWindow).toBe(false);
  });

  it("active → видео вызова + [Микрофон, Звук, Завершить] + Открыть + таймер", () => {
    const v = deriveView("active");
    expect(v).toMatchObject({
      visible: true,
      video: "call",
      actions: ["mic", "sound", "hangup"],
      showOpen: true,
      showTimer: true,
    });
  });

  it("error → видим, isError, [Повторить, Завершить] + Открыть", () => {
    const v = deriveView("error");
    expect(v.visible).toBe(true);
    expect(v.isError).toBe(true);
    expect(v.actions).toEqual(["retry", "hangup"]);
    expect(v.showOpen).toBe(true);
  });
});
