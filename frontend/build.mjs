// Сборка карточки вызова в один ESM-бандл (Lit вшит). Артефакт коммитится в
// custom_components/.../www/ — HACS раздаёт его как Lovelace-ресурс, без сборки.
import { build, context } from "esbuild";
import { readFile, writeFile } from "node:fs/promises";
import process from "node:process";

const OUT = "../custom_components/elektronny_gorod/www/eg-intercom-call-card.js";

const trimGeneratedLineEnds = {
  name: "trim-generated-line-ends",
  setup(buildApi) {
    buildApi.onEnd(async (result) => {
      if (result.errors.length) return;
      const bundle = await readFile(OUT, "utf8");
      await writeFile(OUT, bundle.replace(/[ \t]+$/gm, ""), "utf8");
    });
  },
};

/** @type {import("esbuild").BuildOptions} */
const opts = {
  entryPoints: ["src/eg-intercom-call-card.ts"],
  bundle: true,
  format: "esm",
  target: "es2021",
  minify: true,
  sourcemap: false,
  legalComments: "none",
  plugins: [trimGeneratedLineEnds],
  // Lit production-режим (убирает dev-mode warnings в консоли HA).
  define: { "process.env.NODE_ENV": '"production"' },
  outfile: OUT,
  banner: {
    js: "/* eg-intercom-call-card — собранный бандл. Источник: frontend/src/. Не редактировать вручную. */",
  },
};

if (process.argv.includes("--watch")) {
  const ctx = await context(opts);
  await ctx.watch();
  console.log("watching frontend/src → " + OUT);
} else {
  await build(opts);
  console.log("built → " + OUT);
}
