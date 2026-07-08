import { describe, expect, it } from "vitest";

import { langOf, t } from "../src/i18n.js";

describe("langOf", () => {
  it("en* из hass.locale.language → en", () => {
    expect(langOf({ locale: { language: "en" } })).toBe("en");
    expect(langOf({ locale: { language: "en-GB" } })).toBe("en");
    expect(langOf({ locale: { language: "EN" } })).toBe("en");
  });

  it("русский/прочие → ru", () => {
    expect(langOf({ locale: { language: "ru" } })).toBe("ru");
    expect(langOf({ locale: { language: "de" } })).toBe("ru");
  });

  it("fallback на hass.language, затем ru", () => {
    expect(langOf({ language: "en" })).toBe("en");
    expect(langOf({ language: "ru" })).toBe("ru");
    expect(langOf(undefined)).toBe("ru");
    expect(langOf({})).toBe("ru");
  });

  it("locale приоритетнее language", () => {
    expect(langOf({ locale: { language: "en" }, language: "ru" })).toBe("en");
  });
});

describe("t", () => {
  it("возвращает нужную таблицу", () => {
    expect(t("ru").status.active).toBe("Разговор");
    expect(t("en").status.active).toBe("In call");
  });

  it("ключевые UI-строки отличаются по языку", () => {
    expect(t("ru").action.accept).toBe("Принять");
    expect(t("en").action.accept).toBe("Answer");
    expect(t("ru").idle.title).toBe("Нет активного вызова");
    expect(t("en").idle.title).toBe("No active call");
    expect(t("ru").open.slide).toBe("Открыть");
    expect(t("en").open.slide).toBe("Open");
  });

  it("ru и en покрывают одинаковый набор ключей (нет пропусков)", () => {
    const keys = (o: unknown, p = ""): string[] =>
      o && typeof o === "object"
        ? Object.entries(o as Record<string, unknown>).flatMap(([k, v]) =>
            typeof v === "object" && v !== null ? keys(v, `${p}${k}.`) : [`${p}${k}`])
        : [];
    expect(keys(t("en")).sort()).toEqual(keys(t("ru")).sort());
  });
});
