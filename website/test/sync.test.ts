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
    expect(html).toContain('<span class="chip">Home Assistant %MIN_HA%+</span>');

    const jsonLdBlock = html.slice(
      html.indexOf("application/ld+json"),
      html.indexOf("</script>", html.indexOf("application/ld+json")),
    );

    expect(jsonLdBlock).not.toMatch(/\d+\.\d+\.\d+/);
  });

  it("ссылка на release notes ведёт на файл текущей версии", () => {
    const repoPath = project.releaseNotesLatest.split("/blob/master/")[1];

    expect(repoPath).toBeDefined();
    // Симптом A-103 был именно такой: ссылка вела на прошлый релиз. Проверять
    // только существование файла мало — старый файл существует.
    expect(project.releaseNotesLatest).toContain(`/${project.version}.md`);
    expect(() => readRepo(repoPath as string)).not.toThrow();
  });

  it("сборка подставляет версию вместо плейсхолдеров", async () => {
    // Через сам конфиг, а не напрямую через функцию: иначе снятие плагина из
    // `plugins: [...]` оставляло проверку зелёной, а на сайт уезжал буквально
    // `%APP_VERSION%`.
    const config = (await import("../vite.config")).default;
    const plugins = (config as { plugins?: unknown[] }).plugins ?? [];
    const plugin = plugins.find(
      (p): p is { name: string; transformIndexHtml: (html: string) => string } =>
        typeof p === "object" &&
        p !== null &&
        (p as { name?: string }).name === "eg-version-placeholders",
    );

    expect(plugin, "плагин подстановки не подключён в vite.config").toBeDefined();

    const html = readRepo("website/index.html");
    const rendered = plugin!.transformIndexHtml(html);

    // Без этой проверки снятие плагина оставляло тесты и сборку зелёными, а на
    // сайт уезжал буквально `%APP_VERSION%` — хуже, чем прошлая версия.
    expect(rendered).not.toContain("%APP_VERSION%");
    expect(rendered).not.toContain("%MIN_HA%");
    expect(rendered).toContain(`"softwareVersion": "${project.version}"`);
    expect(rendered).toContain(
      `"operatingSystem": "Home Assistant ${project.minHomeAssistant}+"`,
    );
    expect(rendered).toContain(`<span class="chip">${project.version} ·`);
  });
});
