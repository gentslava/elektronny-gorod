// Скролл-повествование «Что происходит при звонке»: шаги слева управляют
// липкой сценой с реальной карточкой. Активен шаг, чья середина ближе всего
// к центру вьюпорта — карточка всегда синхронна с читаемым текстом.

import { DemoHost } from "../demo/demo-host";
import type { DemoPhase } from "../demo/scenario";

export async function initScenario(): Promise<void> {
  const stage = document.getElementById("sc-stage");
  const stepsRoot = document.getElementById("sc-steps");
  const section = document.getElementById("scenario");
  if (!stage || !stepsRoot || !section) return;

  const host = new DemoHost(stage, { layout: "full", phase: "idle" });
  await host.mount();

  const steps = [...stepsRoot.querySelectorAll<HTMLElement>(".sc-step")];
  if (!steps.length) return;
  let current: HTMLElement | null = null;

  const shell = document.getElementById("sc-shell");
  const push = document.getElementById("sc-push");

  const apply = (el: HTMLElement): void => {
    if (el === current) return;
    current = el;
    steps.forEach((s) => s.classList.toggle("current", s === el));
    const phase = (el.dataset.phase ?? "idle") as DemoPhase;
    const doorOpen = el.dataset.open === "true";
    const showPush = el.dataset.push === "true";
    host.setPhase(phase, {
      doorOpen,
      talkSec: phase === "active" ? (doorOpen ? 31 : 3) : 0,
    });
    if (push) push.hidden = !showPush;
    shell?.classList.toggle("push-on", showPush);
  };

  const pick = (): void => {
    const mid = window.innerHeight / 2;
    let best: HTMLElement | null = null;
    let bestDist = Infinity;
    for (const s of steps) {
      const r = s.getBoundingClientRect();
      const d = Math.abs((r.top + r.bottom) / 2 - mid);
      if (d < bestDist) {
        bestDist = d;
        best = s;
      }
    }
    if (best) apply(best);
  };

  // Считаем только пока секция видима; scroll — с rAF-троттлингом.
  let ticking = false;
  const onScroll = (): void => {
    if (ticking) return;
    ticking = true;
    requestAnimationFrame(() => {
      ticking = false;
      pick();
    });
  };

  const io = new IntersectionObserver(
    (entries) => {
      for (const e of entries) {
        if (e.isIntersecting) {
          window.addEventListener("scroll", onScroll, { passive: true });
          pick();
        } else {
          window.removeEventListener("scroll", onScroll);
        }
      }
    },
    { rootMargin: "10% 0px 10% 0px" },
  );
  io.observe(section);
  pick();
}
