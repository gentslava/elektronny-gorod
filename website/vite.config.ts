import { defineConfig } from "vitest/config";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

// Реальный production-бандл карточки вызова из интеграции (Lit вшит).
// Сайт демонстрирует именно shipped-артефакт, а не копию интерфейса.
const CARD_BUNDLE = fileURLToPath(
  new URL(
    "../custom_components/elektronny_gorod/www/eg-intercom-call-card.js",
    import.meta.url,
  ),
);

// Версия и минимум HA живут в manifest.json и hacs.json. Разметка берёт их
// оттуда при сборке: раньше строки правились руками и отставали от релиза.
const repoJson = (relative: string) =>
  JSON.parse(
    readFileSync(fileURLToPath(new URL(relative, import.meta.url)), "utf8"),
  );

const versionPlaceholders = () => ({
  name: "eg-version-placeholders",
  transformIndexHtml(html: string) {
    const manifest = repoJson(
      "../custom_components/elektronny_gorod/manifest.json",
    );
    const hacs = repoJson("../hacs.json");

    return html
      .replaceAll("%APP_VERSION%", manifest.version)
      .replaceAll("%MIN_HA%", hacs.homeassistant);
  },
});

export default defineConfig({
  // Относительная база: сайт работает и на своём домене, и в подпапке
  // GitHub Pages (gentslava.github.io/elektronny-gorod/).
  base: "./",
  plugins: [versionPlaceholders()],
  resolve: {
    alias: { "@card-bundle": CARD_BUNDLE },
  },
  server: {
    fs: { allow: [".", ".."] },
  },
  build: {
    target: "es2022",
    // Бандл карточки минифицирован — предупреждение о размере не информативно.
    chunkSizeWarningLimit: 700,
  },
  test: {
    environment: "node",
    include: ["test/**/*.test.ts"],
  },
});
