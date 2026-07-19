// Проверка совместимости: форма + отчёт из единого движка
// src/data/compatibility.ts. Рендер формы — один раз, отчёт — на изменение.

import {
  DEVICES,
  FEATURES,
  VERDICT_LABELS,
  checkCompatibility,
  type CompatInput,
  type Device,
  type FeatureId,
  type HaVersion,
} from "../data/compatibility";
import { project } from "../data/project";

const HA_OPTIONS: { value: HaVersion; label: string }[] = [
  { value: "ok", label: "2024.10.4 или новее" },
  { value: "old", label: "Старее" },
  { value: "unknown", label: "Не знаю" },
];

const DEFAULT_FEATURES: FeatureId[] = ["video", "doorbell-event", "open-door", "talk"];

export function initCompat(): void {
  const form = document.getElementById("compat-form") as HTMLFormElement | null;
  const result = document.getElementById("compat-result");
  if (!form || !result) return;

  form.appendChild(group("Устройство", radios("c-dev", Object.entries(DEVICES), "intercom")));
  form.appendChild(
    group(
      "Версия Home Assistant",
      radios("c-ha", HA_OPTIONS.map((o) => [o.value, o.label]), "ok"),
    ),
  );
  form.appendChild(
    group(
      "Какие функции нужны",
      checks(
        "c-feat",
        (Object.entries(FEATURES) as [FeatureId, { label: string }][]).map(
          ([id, f]) => [id, f.label],
        ),
        DEFAULT_FEATURES,
      ),
    ),
  );

  const read = (): CompatInput => {
    const fd = new FormData(form);
    return {
      device: (fd.get("c-dev") as Device) ?? "intercom",
      haVersion: (fd.get("c-ha") as HaVersion) ?? "unknown",
      features: fd.getAll("c-feat") as FeatureId[],
    };
  };

  const render = (): void => {
    const report = checkCompatibility(read());
    result.textContent = "";

    const h = document.createElement("h3");
    h.textContent = "Результат";
    result.appendChild(h);

    const summary = document.createElement("p");
    summary.className = "compat-summary";
    summary.textContent = report.summary;
    result.appendChild(summary);

    if (report.items.length) {
      const ul = document.createElement("ul");
      ul.className = "verdicts";
      for (const item of report.items) {
        const li = document.createElement("li");
        const head = document.createElement("div");
        head.className = "v-head";
        const b = document.createElement("b");
        b.textContent = item.label;
        const badge = document.createElement("span");
        badge.className = `verdict v-${item.verdict}`;
        badge.textContent = VERDICT_LABELS[item.verdict];
        head.append(b, badge);
        const note = document.createElement("p");
        note.className = "note";
        note.textContent = item.note;
        li.append(head, note);
        ul.appendChild(li);
      }
      result.appendChild(ul);
    }

    const issue = document.createElement("p");
    issue.className = "compat-summary";
    const a = document.createElement("a");
    a.href = project.issues;
    a.rel = "noopener";
    a.textContent = "откройте issue";
    issue.append("Сомневаетесь или устройство ведёт себя иначе — ", a, ".");
    result.appendChild(issue);
  };

  form.addEventListener("change", render);
  render();
}

/* ---------- мелкие фабрики разметки ---------- */

function group(title: string, seg: HTMLElement): HTMLFieldSetElement {
  const fs = document.createElement("fieldset");
  fs.className = "pg-group";
  const legend = document.createElement("legend");
  legend.textContent = title;
  fs.append(legend, seg);
  return fs;
}

function radios(
  name: string,
  options: [string, string][],
  checked: string,
): HTMLDivElement {
  const seg = document.createElement("div");
  seg.className = "seg";
  for (const [value, label] of options) {
    const l = document.createElement("label");
    const input = document.createElement("input");
    input.type = "radio";
    input.name = name;
    input.value = value;
    input.checked = value === checked;
    const span = document.createElement("span");
    span.textContent = label;
    l.append(input, span);
    seg.appendChild(l);
  }
  return seg;
}

function checks(
  name: string,
  options: [string, string][],
  checked: string[],
): HTMLDivElement {
  const seg = document.createElement("div");
  seg.className = "seg";
  for (const [value, label] of options) {
    const l = document.createElement("label");
    const input = document.createElement("input");
    input.type = "checkbox";
    input.name = name;
    input.value = value;
    input.checked = checked.includes(value);
    const span = document.createElement("span");
    span.textContent = label;
    l.append(input, span);
    seg.appendChild(l);
  }
  return seg;
}

