#!/usr/bin/env node
/**
 * Пакетный захват README-скриншотов карточки вызова из demo-харнесса.
 * Требует: python3 -m http.server 8777 из корня репо.
 * Запуск: node frontend/demo/capture-screenshots.mjs
 */
import { chromium } from "playwright";
import { execSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.resolve(__dirname, "../..");
const BASE = "http://localhost:8777/frontend/demo/index.html";
const OUT_RU = path.join(
  REPO,
  "docs/features/intercom-two-way-audio/screenshots",
);
const OUT_EN = path.join(OUT_RU, "en");
const TMP = path.join(REPO, "tmp/screenshots-2x");

const FRAMES = [
  { file: "incoming", q: "state=ringing&w=390&h=800", vw: 420, vh: 860, tw: 390 },
  { file: "active", q: "state=active&w=390&h=800", vw: 420, vh: 860, tw: 390 },
  {
    file: "light-theme",
    q: "state=active&theme=light&w=390&h=800",
    vw: 420,
    vh: 860,
    tw: 390,
  },
  { file: "mic-permission", q: "state=mic&w=390&h=800", vw: 420, vh: 860, tw: 390 },
  {
    file: "connection-lost",
    q: "state=error&w=390&h=800",
    vw: 420,
    vh: 860,
    tw: 390,
  },
  { file: "idle", q: "state=idle&w=390&h=560", vw: 420, vh: 620, tw: 390 },
  {
    file: "wall-panel",
    q: "state=active&w=1000&h=620",
    vw: 1020,
    vh: 660,
    tw: 1000,
  },
  { file: "compact", q: "state=ringing&layout=compact&w=412", vw: 440, vh: 120, tw: 412 },
];

fs.mkdirSync(TMP, { recursive: true });
fs.mkdirSync(OUT_EN, { recursive: true });

const browser = await chromium.launch({ channel: "chrome" });
const context = await browser.newContext({ deviceScaleFactor: 2 });

for (const lang of ["ru", "en"]) {
  const outDir = lang === "en" ? OUT_EN : OUT_RU;
  for (const { file, q, vw, vh, tw } of FRAMES) {
    const langQ = lang === "en" ? `${q}&lang=en` : q;
    const url = `${BASE}?${langQ}`;
    const page = await context.newPage();
    await page.setViewportSize({ width: vw, height: vh });
    await page.goto(url, { waitUntil: "networkidle" });
    await page.waitForFunction(() => window.__egReady === true, null, {
      timeout: 10000,
    });
    await page.waitForTimeout(file === "mic-permission" ? 400 : 200);

    const tmp2x = path.join(TMP, `${lang}-${file}@2x.png`);
    const stage = page.locator("#stage");
    await stage.screenshot({ path: tmp2x, type: "png", omitBackground: false });

    const out = path.join(outDir, `${file}.png`);
    execSync(`sips --resampleWidth ${tw} "${tmp2x}" --out "${out}"`, {
      stdio: "pipe",
    });

    console.log(`${lang}/${file}.png → ${out}`);
    await page.close();
  }
}

await browser.close();
console.log("done");
