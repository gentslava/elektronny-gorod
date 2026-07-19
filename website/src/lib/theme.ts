// Светлая/тёмная тема: prefers-color-scheme по умолчанию + ручной тумблер
// с сохранением в localStorage (не cookie).

const KEY = "eg-site-theme";

export type Theme = "light" | "dark";

export function currentTheme(): Theme {
  const saved = localStorage.getItem(KEY);
  if (saved === "light" || saved === "dark") return saved;
  return matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function applyTheme(theme: Theme): void {
  document.documentElement.dataset.theme = theme;
}

export function initTheme(toggle: HTMLButtonElement | null): void {
  applyTheme(currentTheme());
  toggle?.addEventListener("click", () => {
    const next: Theme = currentTheme() === "dark" ? "light" : "dark";
    localStorage.setItem(KEY, next);
    applyTheme(next);
  });
  // Следуем за системой, пока пользователь не выбрал тему вручную.
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {
    if (!localStorage.getItem(KEY)) applyTheme(currentTheme());
  });
}
