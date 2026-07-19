import { defineConfig } from "vitest/config";
import { fileURLToPath } from "node:url";

// Реальный production-бандл карточки вызова из интеграции (Lit вшит).
// Сайт демонстрирует именно shipped-артефакт, а не копию интерфейса.
const CARD_BUNDLE = fileURLToPath(
  new URL(
    "../custom_components/elektronny_gorod/www/eg-intercom-call-card.js",
    import.meta.url,
  ),
);

export default defineConfig({
  // Относительная база: сайт работает и на своём домене, и в подпапке
  // GitHub Pages (gentslava.github.io/elektronny-gorod/).
  base: "./",
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
