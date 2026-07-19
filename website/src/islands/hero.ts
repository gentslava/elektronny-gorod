// Hero: реальная карточка в одном выразительном состоянии — «разговор идёт».
// Карточка рендерится сразу в active (без флликера idle), живость даёт сам
// интерфейс: LIVE-бейдж и тикающий таймер. Полный путь звонка — в #scenario.

import { DemoHost } from "../demo/demo-host";

export async function initHero(): Promise<void> {
  const stage = document.getElementById("hero-stage");
  if (!stage) return;

  const host = new DemoHost(stage, {
    layout: "full",
    phase: "active",
    talkSec: 24,
  });
  await host.mount();
}
