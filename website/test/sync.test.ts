// Сайт обещает пользователю минимальную версию HA — она обязана совпадать с
// той, что HACS проверяет при установке. Раньше эти значения разъезжались
// молча: сайт говорил «работает», HACS отказывал в установке (A-100).
import { existsSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

import { project } from "../src/data/project";

const repoRoot = fileURLToPath(new URL("../../", import.meta.url));

describe("синхронизация с репозиторием", () => {
  it("minHomeAssistant совпадает с hacs.json", () => {
    const hacs = JSON.parse(readFileSync(`${repoRoot}hacs.json`, "utf8"));

    expect(project.minHomeAssistant).toBe(hacs.homeassistant);
  });

  it("version совпадает с manifest.json интеграции", () => {
    const manifest = JSON.parse(
      readFileSync(
        `${repoRoot}custom_components/elektronny_gorod/manifest.json`,
        "utf8",
      ),
    );

    expect(project.version).toBe(manifest.version);
  });

  // project.ts не рендерится сам по себе: посетитель читает разметку. Без
  // этой проверки сверка версий сторожила бы константу, которую никто не
  // видит, пока страница показывает предыдущий релиз.
  it("страница показывает ту же версию, что и project.ts", () => {
    const html = readFileSync(`${repoRoot}website/index.html`, "utf8");
    const jsonLd = html.match(/"softwareVersion":\s*"([^"]+)"/);

    expect(jsonLd?.[1]).toBe(project.version);
    expect(html).toContain(`<span class="chip">${project.version} ·`);
  });

  it("ссылка на release notes ведёт на существующий файл текущей версии", () => {
    expect(project.releaseNotesLatest).toContain(`/${project.version}.md`);

    // Путь берём из самой ссылки, а не собираем рядом: иначе смена каталога
    // релизов оставила бы обе проверки зелёными, а ссылку — ведущей на 404.
    const repoPath = project.releaseNotesLatest.split("/blob/master/")[1];

    expect(repoPath).toBeDefined();
    expect(existsSync(`${repoRoot}${repoPath}`)).toBe(true);
  });

});
