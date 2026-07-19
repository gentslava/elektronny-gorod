import { describe, expect, it } from "vitest";

import { AUTOMATIONS } from "../src/data/automations";

// Сервисы, которые реально существуют: core-домены HA + сервисы интеграции.
const ALLOWED_SERVICE_DOMAINS = new Set([
  "notify",
  "lock",
  "light",
  "media_player",
  "switch",
  "logbook",
  "camera",
  "elektronny_gorod",
]);

// Плейсхолдеры в стиле README — без реальных адресов/договоров.
const PLACEHOLDER = /YOUR_[A-Z_]+/;

describe("библиотека автоматизаций", () => {
  it("не пуста и без дубликатов id", () => {
    expect(AUTOMATIONS.length).toBeGreaterThanOrEqual(8);
    const ids = AUTOMATIONS.map((a) => a.id);
    expect(new Set(ids).size).toBe(ids.length);
  });

  for (const recipe of AUTOMATIONS) {
    describe(recipe.id, () => {
      it("использует только существующие сервисы", () => {
        if (recipe.kind === "dashboard") {
          // Рецепт вкладки Lovelace: сервисов нет, должны быть карточки.
          expect(recipe.yaml).toContain("cards:");
          return;
        }
        const actions = [...recipe.yaml.matchAll(/action:\s*"?([a-z_]+)\.([a-z_]+)"?/g)];
        expect(actions.length).toBeGreaterThan(0);
        for (const [, domain] of actions) {
          if (domain === "OPEN_DOOR") continue;
          expect(
            ALLOWED_SERVICE_DOMAINS.has(domain ?? ""),
            `неизвестный домен сервиса «${domain}» в ${recipe.id}`,
          ).toBe(true);
        }
      });

      it("ссылается на сущности через плейсхолдеры, без PII", () => {
        for (const entity of recipe.entities) {
          expect(entity).toMatch(/^[a-z_]+\.[A-Za-z0-9_]+$/);
        }
        // Ни одного «реального» номера договора/квартиры в YAML.
        expect(recipe.yaml).not.toMatch(/apartment:\s*\d+/);
        expect(
          PLACEHOLDER.test(recipe.yaml) || recipe.id === "low-balance",
          `в ${recipe.id} нет плейсхолдеров YOUR_*`,
        ).toBe(true);
      });

      it("объяснение и YAML согласованы", () => {
        expect(recipe.story.length).toBeGreaterThan(20);
        expect(recipe.yaml).toContain(
          recipe.kind === "dashboard" ? "cards:" : "alias:",
        );
        const first = recipe.entities[0];
        expect(first).toBeDefined();
        if (first) expect(recipe.yaml).toContain(first);
      });
    });
  }
});
