import { describe, expect, it } from "vitest";

import {
  FEATURES,
  checkCompatibility,
} from "../src/data/compatibility";

describe("compatibility engine", () => {
  it("блокирует старый Home Assistant с честным сообщением", () => {
    const r = checkCompatibility({
      device: "intercom",
      haVersion: "old",
      features: ["video"],
    });
    expect(r.blocked).toBe(true);
    expect(r.summary).toContain("2024.10.4");
    expect(r.items).toHaveLength(0);
  });

  it("звук камеры требует go2rtc", () => {
    const r = checkCompatibility({
      device: "camera",
      haVersion: "ok",
      features: ["audio"],
    });
    expect(r.items[0]?.verdict).toBe("ok-go2rtc");
  });

  it("разговор помечен как требующий HTTPS", () => {
    const r = checkCompatibility({
      device: "intercom",
      haVersion: "ok",
      features: ["talk"],
    });
    expect(r.items[0]?.verdict).toBe("needs-https");
  });

  it("событие звонка не обещается для дворовой камеры", () => {
    const r = checkCompatibility({
      device: "camera",
      haVersion: "ok",
      features: ["doorbell-event"],
    });
    expect(r.items[0]?.verdict).toBe("unsupported");
    expect(r.items[0]?.note.length).toBeGreaterThan(10);
  });

  it("история движения камеры — экспериментальная", () => {
    const r = checkCompatibility({
      device: "camera",
      haVersion: "ok",
      features: ["motion-history"],
    });
    expect(r.items[0]?.verdict).toBe("experimental");
  });

  it("пустой выбор функций разворачивается в полный список", () => {
    const r = checkCompatibility({
      device: "intercom",
      haVersion: "ok",
      features: [],
    });
    expect(r.items.length).toBe(Object.keys(FEATURES).length);
  });

  it("неизвестная версия HA даёт подсказку в summary", () => {
    const r = checkCompatibility({
      device: "intercom",
      haVersion: "unknown",
      features: ["video"],
    });
    expect(r.summary).toContain("Настройки");
  });

  it("summary объясняет, что операторы равнозначны", () => {
    const r = checkCompatibility({
      device: "intercom",
      haVersion: "ok",
      features: ["video"],
    });
    expect(r.summary).toContain("одно API");
  });
});
