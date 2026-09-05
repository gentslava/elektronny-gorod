// Версия и минимальная HA больше не дублируются в сайте: `project.ts` читает
// их из `manifest.json` и `hacs.json`, а разметку заполняет Vite при сборке.
// Поэтому сверять значения бессмысленно — они равны по построению. Стеречь
// нужно другое: чтобы никто не вернул захардкоженную константу обратно.
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

import { project } from "../src/data/project";

const repoRoot = fileURLToPath(new URL("../../", import.meta.url));
const readRepo = (relative: string) =>
  readFileSync(`${repoRoot}${relative}`, "utf8");

describe("синхронизация с репозиторием", () => {
  it("значения выводятся из источников, а не копируются", () => {
    const manifest = JSON.parse(
      readRepo("custom_components/elektronny_gorod/manifest.json"),
    );
    const hacs = JSON.parse(readRepo("hacs.json"));

    expect(project.version).toBe(manifest.version);
    expect(project.minHomeAssistant).toBe(hacs.homeassistant);
  });

  it("разметка не содержит захардкоженных версий", () => {
    const html = readRepo("website/index.html");

    // Именно эти два места отставали от релиза раньше (A-100): JSON-LD и чип
    // в шапке. Плейсхолдер здесь — не косметика, а гарантия, что подстановка
    // при сборке остаётся единственным путём.
    expect(html).toContain('"softwareVersion": "%APP_VERSION%"');
    expect(html).toContain('<span class="chip">%APP_VERSION% ·');
    expect(html).toContain('"operatingSystem": "Home Assistant %MIN_HA%+"');

    const jsonLdBlock = html.slice(
      html.indexOf("application/ld+json"),
      html.indexOf("</script>", html.indexOf("application/ld+json")),
    );

    expect(jsonLdBlock).not.toMatch(/\d+\.\d+\.\d+/);
  });

  it("ссылка на release notes ведёт на существующий файл", () => {
    const repoPath = project.releaseNotesLatest.split("/blob/master/")[1];

    expect(repoPath).toBeDefined();
    // Ссылка собирается из версии манифеста, поэтому проверяем, что файл
    // релиза действительно написан — иначе сайт уводит на 404.
    expect(() => readRepo(repoPath as string)).not.toThrow();
  });
});
