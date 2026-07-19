// Библиотека автоматизаций. Все сценарии на событии звонка собраны в один
// блок с переключателем (одно событие — десятки применений), самостоятельные
// сценарии — строки-цепочки ниже.

import {
  AUTOMATIONS,
  DIFFICULTY_LABELS,
  type AutomationRecipe,
} from "../data/automations";
import { codeBlock } from "../lib/code-block";

export function initAutomations(): void {
  const ringRoot = document.getElementById("auto-hero");
  const rowsRoot = document.getElementById("auto-rows");
  if (!ringRoot || !rowsRoot) return;

  const ring = AUTOMATIONS.filter((r) => r.category === "ring");
  const standalone = AUTOMATIONS.filter((r) => r.category === "standalone");

  if (ring.length) ringRoot.appendChild(renderRingGroup(ring));
  for (const recipe of standalone) rowsRoot.appendChild(renderRow(recipe));
}

/* ---------- ring-блок: пуш-мокап + переключатель сценариев ---------- */

function renderRingGroup(recipes: AutomationRecipe[]): HTMLElement {
  const wrap = document.createElement("div");
  wrap.className = "auto-hero-grid";

  // Мокап уведомления: визуал события, вокруг которого всё крутится.
  const phone = document.createElement("div");
  phone.className = "push-scene";
  phone.setAttribute("aria-hidden", "true");
  phone.innerHTML = `
    <div class="push-mock">
      <div class="push-app">
        <img src="${import.meta.env.BASE_URL}favicon.svg" alt="" width="18" height="18" />
        <span>Home Assistant</span><i>·</i><span>сейчас</span>
      </div>
      <div class="push-body">
        <div class="push-text">
          <b>🔔 Звонок в домофон</b>
          <span>Подъезд 2</span>
        </div>
        <img class="push-thumb" src="${import.meta.env.BASE_URL}assets/guest.jpg" alt="" />
      </div>
      <div class="push-actions"><span>🔓 Открыть дверь</span></div>
    </div>
    <p class="push-caption">одно событие — все сценарии ниже</p>`;

  const info = document.createElement("div");
  info.className = "auto-hero-info";

  const h = document.createElement("h3");
  h.textContent = "Одно событие — десятки сценариев";
  const intro = document.createElement("p");
  intro.className = "story";
  intro.textContent =
    "Гость нажимает кнопку — в Home Assistant прилетает event: ring. Дальше дом решает сам:";

  const tabs = document.createElement("div");
  tabs.className = "ring-tabs";
  tabs.setAttribute("aria-label", "Сценарии на событии звонка");

  const detail = document.createElement("div");
  detail.className = "ring-detail";

  const buttons = new Map<string, HTMLButtonElement>();

  const select = (recipe: AutomationRecipe): void => {
    buttons.forEach((btn, id) => {
      const active = id === recipe.id;
      btn.classList.toggle("active", active);
      btn.setAttribute("aria-pressed", String(active));
    });
    detail.textContent = "";

    const head = document.createElement("div");
    head.className = "flow-head";
    const title = document.createElement("h4");
    title.textContent = recipe.title;
    head.append(title, renderDiff(recipe));

    const story = document.createElement("p");
    story.className = "story";
    story.textContent = recipe.story;

    detail.append(head, story, renderChain(recipe.chain));

    if (recipe.requires.length) {
      const req = document.createElement("p");
      req.className = "flow-req";
      req.textContent = `Понадобится: ${recipe.requires.join("; ")}`;
      detail.appendChild(req);
    }

    detail.appendChild(renderYamlControls(recipe, true));
  };

  for (const recipe of recipes) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.textContent = recipe.tab ?? recipe.title;
    btn.addEventListener("click", () => select(recipe));
    buttons.set(recipe.id, btn);
    tabs.appendChild(btn);
  }

  info.append(h, intro, tabs, detail);
  const first = recipes[0];
  if (first) select(first);

  wrap.append(phone, info);
  return wrap;
}

/* ---------- самостоятельные сценарии: строки-цепочки + визуал ---------- */

function renderRow(recipe: AutomationRecipe): HTMLElement {
  const row = document.createElement("article");
  row.className = "flow-row";

  const head = document.createElement("div");
  head.className = "flow-head";
  const h = document.createElement("h3");
  h.textContent = recipe.title;
  head.append(h, renderDiff(recipe));

  const story = document.createElement("p");
  story.className = "story";
  story.textContent = recipe.story;

  const body = document.createElement("div");
  body.className = "flow-body";
  body.append(head, story, renderChain(recipe.chain));

  if (recipe.requires.length) {
    const req = document.createElement("p");
    req.className = "flow-req";
    req.textContent = `Понадобится: ${recipe.requires.join("; ")}`;
    body.appendChild(req);
  }

  body.appendChild(renderYamlControls(recipe, false));
  row.appendChild(body);

  const viz = renderViz(recipe.id);
  if (viz) {
    row.appendChild(viz);
    row.classList.add("has-viz");
  }
  return row;
}

/* ---------- CSS-мокапы результата: то, что получит пользователь ---------- */

function renderViz(id: string): HTMLElement | null {
  const html = VIZ[id];
  if (!html) return null;
  const wrap = document.createElement("div");
  wrap.className = "flow-viz";
  wrap.setAttribute("aria-hidden", "true");
  wrap.innerHTML = html;
  return wrap;
}

const GUEST = `${import.meta.env.BASE_URL}assets/guest.jpg`;

const VIZ: Record<string, string> = {
  "camera-panel": `
    <div class="viz viz-cams">
      <i class="tile t1"><span class="ts">19-07 14:02</span><b>Калитка</b><em>🔒</em></i>
      <i class="tile t2"><span class="ts">19-07 14:02</span><b>Подъезд</b><em>🔒</em></i>
      <i class="tile t3"><span class="ts">19-07 14:02</span><b>Двор</b></i>
      <i class="tile t4"><span class="ts">19-07 14:02</span><b>Лифт</b></i>
      <p class="viz-cap">вкладка «Камеры» — весь дом на одном экране</p>
    </div>`,
  "locks-panel": `
    <div class="viz viz-locks">
      <i><span class="lk">🔒</span><span class="nm">Внешняя калитка<small>Закрыто</small></span><span class="act">🔓</span></i>
      <i><span class="lk">🔒</span><span class="nm">Внутренняя калитка<small>Закрыто</small></span><span class="act">🔓</span></i>
      <i><span class="lk">🔒</span><span class="nm">Подъезд<small>Закрыто</small></span><span class="act">🔓</span></i>
      <p class="viz-cap">все двери дома — одной колонкой</p>
    </div>`,
  "face-known": `
    <div class="viz viz-face">
      <i class="frame" style="background-image:url('${GUEST}')">
        <span class="c c1"></span><span class="c c2"></span><span class="c c3"></span><span class="c c4"></span>
        <b>свои · 0.98</b>
      </i>
      <p class="viz-cap">Frigate + Double Take по RTSP-потоку</p>
    </div>`,
  "night-dnd": `
    <div class="viz viz-dnd">
      <i><span>🌙</span><b>Не беспокоить</b><em class="tgl"></em></i>
      <p class="viz-cap">23:00 → 07:00 · включается само</p>
    </div>`,
  "bedside-button": `
    <div class="viz viz-btn">
      <i class="press"></i><span class="arr">→</span><i class="done">🔓</i>
      <p class="viz-cap">кнопка у кровати → lock.unlock</p>
    </div>`,
  "low-balance": `
    <div class="viz viz-push">
      <i><span>💳</span><span class="tx"><b>Электронный город</b>Баланс ниже 100 ₽ — пора пополнить</span></i>
      <p class="viz-cap">напоминание до отключения</p>
    </div>`,
  "days-to-block": `
    <div class="viz viz-push">
      <i><span>⚠️</span><span class="tx"><b>Договор скоро заблокируют</b>Осталось 2 дня — пополните счёт</span></i>
      <p class="viz-cap">заранее, а не когда всё замолчало</p>
    </div>`,
  "evening-snapshot": `
    <div class="viz viz-snap">
      <i class="tile t2"><span>17.07</span></i>
      <i class="tile t3"><span>18.07</span></i>
      <i class="tile t1"><span>19.07</span></i>
      <p class="viz-cap">каждый вечер — кадр двора в медиатеке</p>
    </div>`,
};

/* ---------- общие кусочки ---------- */

function renderChain(chain: string[]): HTMLElement {
  const el = document.createElement("p");
  el.className = "chain";
  chain.forEach((part, i) => {
    if (i > 0) {
      const arrow = document.createElement("i");
      arrow.textContent = "→";
      arrow.setAttribute("aria-hidden", "true");
      el.appendChild(arrow);
    }
    const chip = document.createElement("code");
    chip.textContent = part;
    el.appendChild(chip);
  });
  return el;
}

function renderDiff(recipe: AutomationRecipe): HTMLElement {
  const diff = document.createElement("span");
  diff.className = `diff diff-${recipe.difficulty}`;
  diff.textContent = DIFFICULTY_LABELS[recipe.difficulty];
  return diff;
}

function renderYamlControls(recipe: AutomationRecipe, open: boolean): HTMLElement {
  const details = document.createElement("details");
  details.className = "yaml-box";
  if (open) details.open = true;

  const lines = recipe.yaml.split("\n").length;
  const summary = document.createElement("summary");
  summary.innerHTML =
    `<svg class="chev" viewBox="0 0 16 16" aria-hidden="true">` +
    `<path d="M6 4l4 4-4 4" fill="none" stroke="currentColor" stroke-width="1.8" ` +
    `stroke-linecap="round" stroke-linejoin="round"/></svg>` +
    `YAML <span class="lines">· ${lines} ${pluralLines(lines)}</span>`;

  details.append(summary, codeBlock(recipe.yaml, recipe.id));
  return details;
}

function pluralLines(n: number): string {
  const m10 = n % 10;
  const m100 = n % 100;
  if (m10 === 1 && m100 !== 11) return "строка";
  if (m10 >= 2 && m10 <= 4 && (m100 < 12 || m100 > 14)) return "строки";
  return "строк";
}
