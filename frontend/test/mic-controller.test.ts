import { describe, expect, it } from "vitest";

import { shouldAutoStartMic } from "../src/components/mic-controller.js";

describe("shouldAutoStartMic", () => {
  it("авто-старт только при granted + secure", () => {
    expect(shouldAutoStartMic("granted", true)).toBe(true);
  });

  it("не авто-стартует, если permission не granted", () => {
    expect(shouldAutoStartMic("prompt", true)).toBe(false);
    expect(shouldAutoStartMic("denied", true)).toBe(false);
    expect(shouldAutoStartMic("unknown", true)).toBe(false);
  });

  it("не авто-стартует на insecure origin (нет HTTPS)", () => {
    expect(shouldAutoStartMic("granted", false)).toBe(false);
  });
});
