import { describe, expect, it } from "vitest";

import { resolveOpenAction } from "../src/util/open-action.js";

describe("resolveOpenAction", () => {
  it("явное значение возвращается как есть (независимо от ввода)", () => {
    expect(resolveOpenAction("slide", false)).toBe("slide");
    expect(resolveOpenAction("hold", true)).toBe("hold");
    expect(resolveOpenAction("tap", true)).toBe("tap");
  });

  it("auto на тач (coarse) → slide", () => {
    expect(resolveOpenAction("auto", true)).toBe("slide");
    expect(resolveOpenAction(undefined, true)).toBe("slide");
  });

  it("auto на десктопе (мышь) → hold (slide мышью неудобен)", () => {
    expect(resolveOpenAction("auto", false)).toBe("hold");
    expect(resolveOpenAction(undefined, false)).toBe("hold");
  });

  it("неизвестное значение трактуется как auto", () => {
    expect(resolveOpenAction("wiggle", true)).toBe("slide");
    expect(resolveOpenAction("wiggle", false)).toBe("hold");
  });
});
