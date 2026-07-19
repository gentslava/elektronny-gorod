// Код-блок с иконкой копирования в углу — единый паттерн для всех YAML
// на сайте (библиотека сценариев, конфигуратор карточки).

import { copyText } from "./copy";
import { track } from "./track";

export const IC_COPY =
  `<svg class="ic-copy" viewBox="0 0 16 16" aria-hidden="true"><path d="M0 6.75C0 5.784.784 5 1.75 5h1.5a.75.75 0 0 1 0 1.5h-1.5a.25.25 0 0 0-.25.25v7.5c0 .138.112.25.25.25h7.5a.25.25 0 0 0 .25-.25v-1.5a.75.75 0 0 1 1.5 0v1.5A1.75 1.75 0 0 1 9.25 16h-7.5A1.75 1.75 0 0 1 0 14.25Z"/><path d="M5 1.75C5 .784 5.784 0 6.75 0h7.5C15.216 0 16 .784 16 1.75v7.5A1.75 1.75 0 0 1 14.25 11h-7.5A1.75 1.75 0 0 1 5 9.25Zm1.75-.25a.25.25 0 0 0-.25.25v7.5c0 .138.112.25.25.25h7.5a.25.25 0 0 0 .25-.25v-7.5a.25.25 0 0 0-.25-.25Z"/></svg>`;

export const IC_CHECK =
  `<svg class="ic-check" viewBox="0 0 16 16" aria-hidden="true"><path d="M13.78 4.22a.75.75 0 0 1 0 1.06l-7.25 7.25a.75.75 0 0 1-1.06 0L2.22 9.28a.751.751 0 0 1 .018-1.042.751.751 0 0 1 1.042-.018L6 10.94l6.72-6.72a.75.75 0 0 1 1.06 0Z"/></svg>`;

/** Привязать копирование к кнопке-иконке: смена иконки на ✓ + возврат. */
export function bindCopyButton(
  btn: HTMLButtonElement,
  getText: () => string,
  trackId: string,
): void {
  btn.addEventListener("click", async () => {
    track("automation_copy", { id: trackId });
    const ok = await copyText(getText());
    btn.classList.add(ok ? "ok" : "fail");
    btn.setAttribute("aria-label", ok ? "Скопировано" : "Не удалось скопировать");
    setTimeout(() => {
      btn.classList.remove("ok", "fail");
      btn.setAttribute("aria-label", "Скопировать YAML");
    }, 1800);
  });
}

/** Готовый блок: <pre><code>…</code></pre> + иконка копирования в углу. */
export function codeBlock(text: string, trackId: string): HTMLElement {
  const wrap = document.createElement("div");
  wrap.className = "code-wrap";

  const pre = document.createElement("pre");
  const code = document.createElement("code");
  code.textContent = text;
  pre.appendChild(code);

  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "code-copy";
  btn.setAttribute("aria-label", "Скопировать YAML");
  btn.title = "Скопировать";
  btn.innerHTML = IC_COPY + IC_CHECK;
  bindCopyButton(btn, () => text, trackId);

  wrap.append(pre, btn);
  return wrap;
}
