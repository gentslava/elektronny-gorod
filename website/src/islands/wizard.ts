// Мастер установки: рендер вопросов из src/data/wizard.ts, план — при
// полном наборе ответов. Вопросы рендерятся один раз, видимость условных —
// через hidden (не теряем фокус при выборе).

import {
  QUESTIONS,
  buildPlan,
  isComplete,
  visibleQuestions,
  type WizardAnswers,
} from "../data/wizard";
import { track } from "../lib/track";

export function initWizard(): void {
  const qRoot = document.getElementById("wiz-questions");
  const planRoot = document.getElementById("wiz-plan");
  if (!qRoot || !planRoot) return;

  const answers: WizardAnswers = {};
  let started = false;

  for (const q of QUESTIONS) {
    const fs = document.createElement("fieldset");
    fs.className = "wiz-q";
    fs.dataset.q = q.id;

    const legend = document.createElement("legend");
    legend.textContent = q.title;
    fs.appendChild(legend);

    if (q.hint) {
      const hint = document.createElement("p");
      hint.className = "hint";
      hint.textContent = q.hint;
      fs.appendChild(hint);
    }

    const seg = document.createElement("div");
    seg.className = "seg";
    for (const opt of q.options) {
      const label = document.createElement("label");
      const input = document.createElement("input");
      input.type = "radio";
      input.name = `wiz-${q.id}`;
      input.value = opt.value;
      const span = document.createElement("span");
      span.textContent = opt.label;
      label.append(input, span);
      seg.appendChild(label);
    }
    fs.appendChild(seg);
    qRoot.appendChild(fs);
  }

  const sync = (): void => {
    const visible = new Set(visibleQuestions(answers).map((q) => q.id));
    qRoot.querySelectorAll<HTMLFieldSetElement>(".wiz-q").forEach((fs) => {
      const id = fs.dataset.q as keyof WizardAnswers;
      const show = visible.has(id);
      fs.hidden = !show;
      if (!show && answers[id] !== undefined) {
        delete answers[id];
        fs.querySelectorAll<HTMLInputElement>("input").forEach(
          (i) => (i.checked = false),
        );
      }
    });
    renderPlan();
  };

  const renderPlan = (): void => {
    planRoot.textContent = "";
    const h = document.createElement("h3");
    h.textContent = "Ваш план установки";
    planRoot.appendChild(h);

    if (!isComplete(answers)) {
      const left = visibleQuestions(answers).filter(
        (q) => answers[q.id] === undefined,
      ).length;
      const p = document.createElement("p");
      p.className = "wiz-empty";
      p.textContent =
        left > 0
          ? `Осталось ответить на ${left} ${plural(left, "вопрос", "вопроса", "вопросов")} — план соберётся автоматически.`
          : "Ответьте на вопросы слева — план соберётся здесь.";
      planRoot.appendChild(p);
      return;
    }

    track("wizard_complete");
    const plan = buildPlan(answers);

    const ol = document.createElement("ol");
    ol.className = "plan-steps";
    for (const step of plan.steps) {
      const li = document.createElement("li");
      const b = document.createElement("b");
      b.textContent = step.title;
      const p = document.createElement("p");
      p.textContent = step.detail;
      li.append(b, p);
      if (step.link) {
        const a = document.createElement("a");
        a.href = step.link.href;
        a.textContent = `${step.link.label} →`;
        if (step.link.href.startsWith("http")) {
          a.rel = "noopener";
          a.target = "_blank";
        }
        li.appendChild(a);
      }
      if (step.optional) {
        const opt = document.createElement("span");
        opt.className = "opt";
        opt.textContent = " · опционально";
        b.appendChild(opt);
      }
      ol.appendChild(li);
    }
    planRoot.appendChild(ol);

    const extra = document.createElement("div");
    extra.className = "plan-extra";

    if (plan.unlocks.length) {
      const h4 = document.createElement("h4");
      h4.textContent = "Станет доступно";
      const ul = document.createElement("ul");
      ul.className = "unlock";
      plan.unlocks.forEach((u) => {
        const li = document.createElement("li");
        li.textContent = u;
        ul.appendChild(li);
      });
      extra.append(h4, ul);
    }

    if (plan.skipped.length) {
      const h4 = document.createElement("h4");
      h4.textContent = "Можно пропустить";
      const ul = document.createElement("ul");
      plan.skipped.forEach((s) => {
        const li = document.createElement("li");
        li.textContent = s;
        ul.appendChild(li);
      });
      extra.append(h4, ul);
    }

    for (const note of plan.notes) {
      const p = document.createElement("p");
      p.textContent = note;
      extra.appendChild(p);
    }
    planRoot.appendChild(extra);
  };

  qRoot.addEventListener("change", (e) => {
    const input = e.target as HTMLInputElement;
    if (!input.name.startsWith("wiz-")) return;
    if (!started) {
      started = true;
      track("wizard_start");
    }
    const id = input.name.slice(4) as keyof WizardAnswers;
    (answers as Record<string, string>)[id] = input.value;
    sync();
  });

  sync();
}

function plural(n: number, one: string, few: string, many: string): string {
  const m10 = n % 10;
  const m100 = n % 100;
  if (m10 === 1 && m100 !== 11) return one;
  if (m10 >= 2 && m10 <= 4 && (m100 < 12 || m100 > 14)) return few;
  return many;
}
