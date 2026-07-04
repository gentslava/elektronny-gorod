import { describe, expect, it } from "vitest";

import { egTokens, statusColor } from "../src/theme/tokens.js";

describe("tokens", () => {
  it("статус-цвет по фазе — роль-переменная", () => {
    expect(statusColor("ringing")).toBe("var(--eg-warning)");
    expect(statusColor("connecting")).toBe("var(--eg-primary)");
    expect(statusColor("active")).toBe("var(--eg-success)");
    expect(statusColor("error")).toBe("var(--eg-error)");
    expect(statusColor("ended")).toBe("var(--eg-text-2)");
    expect(statusColor("idle")).toBe("var(--eg-text-2)");
  });

  it("egTokens содержит маппинг primary на HA-переменную и радиусы", () => {
    expect(egTokens.cssText).toContain("--eg-primary: var(--primary-color");
    expect(egTokens.cssText).toContain("--eg-r-full: 999px");
  });
});
