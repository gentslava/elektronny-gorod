import { describe, expect, it } from "vitest";

import { micBannerReason, shouldAutoStartMic } from "../src/components/mic-controller.js";

describe("shouldAutoStartMic", () => {
  it("авто-старт только при granted + secure", () => {
    expect(shouldAutoStartMic("granted", true)).toBe(true);
  });

  it("не авто-стартует, если permission не granted (и раньше не разрешали)", () => {
    expect(shouldAutoStartMic("prompt", true)).toBe(false);
    expect(shouldAutoStartMic("denied", true)).toBe(false);
    expect(shouldAutoStartMic("unknown", true)).toBe(false);
  });

  it("не авто-стартует на insecure origin (нет HTTPS)", () => {
    expect(shouldAutoStartMic("granted", false)).toBe(false);
  });

  it("авто-стартует на prompt/unknown, если раньше уже разрешали (grantedBefore)", () => {
    // Ключевой фикс: Permissions API отдаёт prompt даже когда origin разрешён —
    // persisted-флаг снимает ручной тап на каждый звонок.
    expect(shouldAutoStartMic("prompt", true, true)).toBe(true);
    expect(shouldAutoStartMic("unknown", true, true)).toBe(true);
  });

  it("НЕ авто-стартует при denied даже с grantedBefore (доступ реально снят)", () => {
    expect(shouldAutoStartMic("denied", true, true)).toBe(false);
  });

  it("НЕ авто-стартует на insecure даже с grantedBefore", () => {
    expect(shouldAutoStartMic("prompt", false, true)).toBe(false);
  });
});

describe("micBannerReason", () => {
  it("no_https на insecure origin (независимо от perm)", () => {
    expect(micBannerReason(false, "granted", true)).toBe("no_https");
    expect(micBannerReason(false, "prompt", false)).toBe("no_https");
  });

  it("denied → denied", () => {
    expect(micBannerReason(true, "denied", false)).toBe("denied");
  });

  it("prompt без grantedBefore → prompt (нужен разовый запрос)", () => {
    expect(micBannerReason(true, "prompt", false)).toBe("prompt");
  });

  it("prompt С grantedBefore → none (авто-старт молча, баннер не нужен)", () => {
    expect(micBannerReason(true, "prompt", true)).toBe("none");
  });

  it("granted → none", () => {
    expect(micBannerReason(true, "granted", false)).toBe("none");
  });
});
