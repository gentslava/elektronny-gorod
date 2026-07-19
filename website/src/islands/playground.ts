// Конфигуратор карточки: живая карточка + панель выбора. Каждый выбор
// мгновенно отражается в карточке и в готовом Lovelace-YAML внизу.
// Перехваченные сервисы ведут себя как реальный бэкенд (answer → active).

import { DemoHost } from "../demo/demo-host";
import type { DemoPhase } from "../demo/scenario";
import { IC_CHECK, IC_COPY, bindCopyButton } from "../lib/code-block";

type PgPhase = "ringing" | "active" | "door" | "ended" | "error" | "idle";

interface PgState {
  layout: "full" | "compact";
  lang: "ru" | "en";
}

function buildYaml(state: PgState): string {
  const lines = ["type: custom:eg-intercom-call-card"];
  if (state.layout === "compact") lines.push("layout: compact");
  lines.push(
    "camera: camera.YOUR_INTERCOM_intercom_call",
    "doorbells:",
    "  - call_state: sensor.YOUR_INTERCOM_call_state",
    "    doorbell_camera: camera.YOUR_INTERCOM",
    "    lock: lock.YOUR_INTERCOM",
    state.lang === "en" ? "    name: Entrance" : "    name: Подъезд",
  );
  return lines.join("\n");
}

export async function initPlayground(): Promise<void> {
  const stage = document.getElementById("pg-stage");
  const frame = document.getElementById("pg-frame");
  const status = document.getElementById("pg-status");
  const controls = document.getElementById("pg-controls");
  const yamlCode = document.getElementById("pg-yaml-code");
  const yamlCopy = document.getElementById("pg-yaml-copy") as HTMLButtonElement | null;
  if (!stage || !frame || !status || !controls || !yamlCode || !yamlCopy) return;

  const state: PgState = { layout: "full", lang: "ru" };

  const say = (line: string): void => {
    status.textContent = line;
  };

  const renderYaml = (): void => {
    yamlCode.textContent = buildYaml(state);
  };

  let flowTimer: number | null = null;
  const cancelFlow = (): void => {
    if (flowTimer !== null) clearTimeout(flowTimer);
    flowTimer = null;
  };

  const setPhaseRadio = (value: PgPhase): void => {
    const input = controls.querySelector<HTMLInputElement>(
      `input[name="pg-phase"][value="${value}"]`,
    );
    if (input) input.checked = true;
  };

  const host = new DemoHost(stage, {
    layout: "full",
    phase: "ringing",
    onAction: ({ domain, service }) => {
      if (domain === "elektronny_gorod" && service === "answer") {
        say("→ elektronny_gorod.answer · соединяем…");
        host.setPhase("connecting");
        cancelFlow();
        flowTimer = window.setTimeout(() => {
          host.setPhase("active", { talkSec: 0 });
          setPhaseRadio("active");
          say("разговор начался: видео и звук гостя");
        }, 1200);
      } else if (domain === "elektronny_gorod" && service === "hangup") {
        cancelFlow();
        host.setPhase("ended");
        setPhaseRadio("ended");
        say("→ elektronny_gorod.hangup · вызов сохранён в историю");
      } else if (domain === "lock" && service === "unlock") {
        say("→ lock.unlock · дверь открыта");
        host.setPhase(host.getPhase(), { doorOpen: true, talkSec: 10 });
        cancelFlow();
        flowTimer = window.setTimeout(() => {
          host.setPhase(host.getPhase(), { talkSec: 14 });
        }, 3000);
      }
    },
  });

  try {
    await host.mount();
  } catch {
    stage.textContent = "";
    const fallback = document.createElement("img");
    fallback.src = `${import.meta.env.BASE_URL}assets/wall-panel.jpg`;
    fallback.alt = "Скриншот карточки вызова";
    stage.appendChild(fallback);
    say("не удалось загрузить живое демо — показан скриншот");
    renderYaml();
    return;
  }

  const applyPhase = (value: PgPhase): void => {
    cancelFlow();
    switch (value) {
      case "ringing":
        host.setPhase("ringing");
        say("входящий вызов: event = ring");
        break;
      case "active":
        host.setPhase("active", { talkSec: 24 });
        say("разговор идёт: видео и звук гостя");
        break;
      case "door":
        host.setPhase("active", { talkSec: 31, doorOpen: true });
        say("lock.unlock → дверь открыта");
        break;
      case "ended":
        host.setPhase("ended");
        say("вызов завершён → сохранён в историю");
        break;
      case "error":
        host.setPhase("error");
        say("ошибка соединения: камера недоступна");
        break;
      case "idle":
        host.setPhase("idle");
        say("ожидание — вне вызова карточку прячет conditional-обёртка");
        break;
    }
  };

  controls.addEventListener("change", (e) => {
    const input = e.target as HTMLInputElement;
    switch (input.name) {
      case "pg-phase":
        applyPhase(input.value as PgPhase);
        break;
      case "pg-theme":
        stage.classList.toggle("stage-theme-dark", input.value === "dark");
        stage.classList.toggle("stage-theme-light", input.value === "light");
        break;
      case "pg-device":
        frame.dataset.device = input.value;
        break;
      case "pg-layout":
        state.layout = input.value === "compact" ? "compact" : "full";
        stage.dataset.layout = state.layout;
        host.setLayout(state.layout);
        renderYaml();
        break;
      case "pg-lang":
        state.lang = input.value === "en" ? "en" : "ru";
        host.setLang(state.lang);
        renderYaml();
        break;
    }
  });

  yamlCopy.innerHTML = IC_COPY + IC_CHECK;
  bindCopyButton(yamlCopy, () => buildYaml(state), "card-config");

  applyPhase("ringing");
  renderYaml();
}
