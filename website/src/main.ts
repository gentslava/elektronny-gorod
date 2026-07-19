// Точка входа: статичный HTML оживляют независимые «острова».
// Каждый остров изолирован try/catch — сбой демо не ломает страницу.

import { initTheme } from "./lib/theme";
import { initReveal } from "./lib/reveal";
import { track, type SiteEvent } from "./lib/track";
import { initAutomations } from "./islands/automations";
import { initWizard } from "./islands/wizard";
import { initCompat } from "./islands/compat";
import { initHero } from "./islands/hero";
import { initScenario } from "./islands/scenario";
import { initPlayground } from "./islands/playground";

function safe(name: string, fn: () => void | Promise<void>): void {
  try {
    const r = fn();
    if (r instanceof Promise) {
      r.catch((err) => console.warn(`[site] ${name} failed`, err));
    }
  } catch (err) {
    console.warn(`[site] ${name} failed`, err);
  }
}

safe("theme", () =>
  initTheme(document.getElementById("theme-toggle") as HTMLButtonElement | null),
);
safe("reveal", initReveal);
safe("automations", initAutomations);
safe("wizard", initWizard);
safe("compat", initCompat);

// Живые демо тяжелее — не блокируем первый рендер.
queueMicrotask(() => {
  safe("hero", initHero);
  safe("scenario", initScenario);
  safe("playground", initPlayground);
});

// Продуктовые события: клики по элементам с data-track.
document.addEventListener("click", (e) => {
  const el = (e.target as HTMLElement).closest<HTMLElement>("[data-track]");
  if (el?.dataset.track) track(el.dataset.track as SiteEvent);
});

// Плавный скролл включаем только после загрузки: иначе восстановление
// позиции скролла при релоаде проигрывается как видимая анимация.
const enableSmooth = (): void => {
  requestAnimationFrame(() =>
    document.documentElement.classList.add("smooth"),
  );
};
if (document.readyState === "complete") enableSmooth();
else window.addEventListener("load", enableSmooth, { once: true });
