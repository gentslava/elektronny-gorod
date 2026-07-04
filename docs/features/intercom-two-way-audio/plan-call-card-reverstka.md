# Перевёрстка `<eg-intercom-call-card>` по production-макетам — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Пиксельно пересобрать визуальный слой карточки вызова домофона по новым макетам `pencil/design.pen` (6 секций), сохранив проверенную механику two-way audio и машину состояний.

**Architecture:** Lit + TypeScript. Оркестратор-карточка держит фазу (`sensor.*_call_state`) + локальные UI-слои и рендерит адаптивные раскладки (мобайл / компакт / настенная / десктоп) через container-queries. Презентационные компоненты (`call-stage`, `open-control`) — self-contained, общаются событиями. Цвета/радиусы — единый токен-слой на `:host`, наследуемый сквозь shadow DOM в HA theme-переменные. Захват микрофона и WS-uplink не трогаем.

**Tech Stack:** Lit 3, TypeScript (strict), esbuild (`build.mjs`), Vitest (`frontend/test/`), Home Assistant custom Lovelace card (`ha-camera-stream`, theme CSS-переменные, mdi/lucide иконки).

## Global Constraints

- **Источник правды состояния** — `sensor.<intercom>_call_state` (`idle|ringing|connecting|active|ended|error`). Слои (`audio_blocked / mic_permission_required / camera_unavailable / connection_lost / door-стадии`) — локальный UI-стейт карточки, НЕ новые значения сенсора.
- **Никаких хардкод-hex в UI**, кроме `scrim` (`rgba(0,0,0,.72)`) и красного `LIVE`-бейджа. Все цвета — через токен-слой `--eg-*` → HA theme-переменные с fallback.
- **Токены макета (design.pen) → HA-переменные** (точные значения):
  `primary #03A9F4/#0288D1`→`--primary-color`; `success #4CAF50/#2E7D32`→`--success-color`; `error #EF5350/#D32F2F`→`--error-color`; `warning #FFB300/#B26A00`→`--warning-color`; `text #E8E8E8/#212121`→`--primary-text-color`; `text-2 #A6A6A6/#6B6B6B`→`--secondary-text-color`; `text-3 #787878/#9B9B9B`→`--disabled-text-color`; `elevated #2A2A2A/#F0F0F0`→`--secondary-background-color`; `card #1C1C1C/#FFFFFF`→`--ha-card-background`/`--card-background-color`; `bg #111/#FAFAFA`→`--primary-background-color`; `divider`→`--divider-color`; `on-fill #FFFFFF`→`--text-primary-color`; радиусы `r-card 16 / r-md 12 / r-full 999`; шрифты `Roboto` (body) / `Roboto Mono` (таймер).
- **`*-bg` тинты** (badge/banner фон): `color-mix(in srgb, var(--eg-<role>) 18%, transparent)` (эквивалент alpha `2E`/`1A` из макета).
- **Точные размеры (из `design.pen`, обязательны):** карточка контент `padding [6,16,28,16]`, `gap 20`, radius `16`; шапка: name `fs22 fw700`, addr `fs13 text-2`, close `44×44` elevated; статус-бейдж `pad[5,12] r-full`, dot `8×8`, текст `fs13 fw600`; окно ответа `h4 r-full`; видео `16:9 r-md`; слайдер трек `h80 r-full elevated`, thumb `68×68 primary` (ключ), торец `44×68 lock-open text-3`, «Открыть» `fs17 fw600`, hint `fs12 text-3`; круглая кнопка `68×68 r-full elevated`, иконка `28`, подпись `fs12 fw500 text-2`; ряд действий `gap 28 center`; компакт мини-видео `96×72`.
- **Иконки** — mdi (текущий стек `ha-icon`). Маппинг lucide→mdi: `key-round`→`mdi:key-variant`, `lock-open`→`mdi:lock-open-variant`, `lock`→`mdi:lock`, `mic`→`mdi:microphone`, `mic-off`→`mdi:microphone-off`, `volume-2`→`mdi:volume-high`, `volume-x`→`mdi:volume-off`, `phone`→`mdi:phone`, `phone-off`→`mdi:phone-hangup`, `x`→`mdi:close`, `refresh-cw`→`mdi:refresh`, `door`→`mdi:door`, `video-off`→`mdi:video-off`, `wifi-off`→`mdi:wifi-off`, `timer`→`mdi:timer-outline`.
- **Проект-правила:** `.claude/rules/no-secret-logs.md` (не логировать токены/headers), `ha-best-practices.md` (theme-токены, `unique_id` без локали, a11y), `test-coverage.md` (bug→тест; не упрощать тесты ради зелёного CI), `git-history.md` (conventional commits, substantive). `mic-controller.ts` НЕ править (ADR-0013, two-way audio работает).
- **Проверка сборки:** `cd frontend && node build.mjs` собирает в `custom_components/elektronny_gorod/www/eg-intercom-call-card.js`. Тесты: `cd frontend && npm test`.
- **A11y:** каждая кнопка — `aria-label`; слайдер — `role="slider"` + `aria-valuenow`; `@media (prefers-reduced-motion: reduce)` отключает анимации.
- **Референс визуала** — узлы `design.pen` (id для скриншот-сверки указаны в задачах) + `call-card-ux-production.md`. Сверка КАЖДОГО слайса — скриншот узла макета vs рендер в браузере.

---

## File Structure

**Создаём:**
- `frontend/src/theme/tokens.ts` — экспорт `css`-фрагмента `egTokens` (токен-слой `:host{--eg-*}`) + палитра статус-цветов. Единственный источник цвета/радиуса.
- `frontend/src/components/call-stage.ts` — `<eg-call-stage>`: видео-область (плеер + оверлеи LIVE/таймстамп/чип звука + CTA/плейсхолдеры/затемнение + tap-to-unmute). Emits `unmute`.

**Переписываем (визуал):**
- `frontend/src/eg-intercom-call-card.ts` — оркестратор: config, фаза+слои, таймеры, раскладки, шапка, статус-строка, баннер, ряды действий, idle, компакт.
- `frontend/src/components/open-control.ts` — слайдер/hold/tap под макет (размеры + стадии).

**Расширяем (логика, чистые функции):**
- `frontend/src/state-machine.ts` — обогащённая `CallView` (набор действий + флаги слоёв + цвет статуса). Остаётся без DOM.

**Правим точечно:**
- `frontend/src/components/call-video.ts` — убрать `controls` (критично, UX-док §13.1), убрать внутренние frame-плейсхолдеры (переезжают в `call-stage`); оставить провайдер-логику (`ha`/`webrtc`) и `pickCameraEntity`.

**Не трогаем:** `frontend/src/components/mic-controller.ts`, `frontend/src/util/open-action.ts`, `build.mjs`, `package.json`.

**Тесты:**
- `frontend/test/state-machine.test.ts` — расширить под новую модель.
- `frontend/test/open-control.test.ts` — обновить константы жеста.
- `frontend/test/call-stage.test.ts` — новый (выбор оверлея/плейсхолдера по флагам — чистые функции).

---

## Slice 0 — Токен-слой + скелет карточки

### Task 0.1: Токен-слой `tokens.ts`

**Files:**
- Create: `frontend/src/theme/tokens.ts`
- Test: `frontend/test/tokens.test.ts`

**Interfaces:**
- Produces: `export const egTokens: CSSResult` (Lit `css` фрагмент для `static styles`); `export function statusColor(phase: CallPhase): string` (возвращает CSS-переменную роли: `ringing→--eg-warning`, `connecting→--eg-primary`, `active→--eg-success`, `error→--eg-error`, `ended→--eg-text-2`).

- [ ] **Step 1: Написать падающий тест**

```ts
import { describe, expect, it } from "vitest";
import { egTokens, statusColor } from "../src/theme/tokens.js";

describe("tokens", () => {
  it("статус-цвет по фазе — роль-переменная", () => {
    expect(statusColor("ringing")).toBe("var(--eg-warning)");
    expect(statusColor("connecting")).toBe("var(--eg-primary)");
    expect(statusColor("active")).toBe("var(--eg-success)");
    expect(statusColor("error")).toBe("var(--eg-error)");
    expect(statusColor("ended")).toBe("var(--eg-text-2)");
    expect(statusColor("idle")).toBe("var(--eg-text-2)");
  });
  it("egTokens содержит маппинг primary на HA-переменную", () => {
    expect(egTokens.cssText).toContain("--eg-primary: var(--primary-color");
    expect(egTokens.cssText).toContain("--eg-r-full: 999px");
  });
});
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run: `cd frontend && npm test -- tokens`
Expected: FAIL «Cannot find module '../src/theme/tokens.js'».

- [ ] **Step 3: Реализовать минимально**

```ts
// Единый токен-слой: значения из pencil/design.pen → HA theme-переменные с fallback.
// CSS custom properties наследуются сквозь shadow DOM — задаём на :host карточки,
// дети (call-stage, open-control) берут var(--eg-*). Никаких хардкод-hex в UI.
import { css, type CSSResult } from "lit";

import type { CallPhase } from "../state-machine.js";

export const egTokens: CSSResult = css`
  :host {
    --eg-primary: var(--primary-color, #03a9f4);
    --eg-success: var(--success-color, #4caf50);
    --eg-error: var(--error-color, #ef5350);
    --eg-warning: var(--warning-color, #ffb300);
    --eg-text: var(--primary-text-color, #e8e8e8);
    --eg-text-2: var(--secondary-text-color, #a6a6a6);
    --eg-text-3: var(--disabled-text-color, #787878);
    --eg-elevated: var(--secondary-background-color, #2a2a2a);
    --eg-card: var(--ha-card-background, var(--card-background-color, #1c1c1c));
    --eg-divider: var(--divider-color, #2e2e2e);
    --eg-on-fill: var(--text-primary-color, #ffffff);
    --eg-scrim: rgba(0, 0, 0, 0.72);
    --eg-r-card: 16px;
    --eg-r-md: 12px;
    --eg-r-full: 999px;
    --eg-mono: "Roboto Mono", ui-monospace, monospace;
    --eg-primary-bg: color-mix(in srgb, var(--eg-primary) 18%, transparent);
    --eg-success-bg: color-mix(in srgb, var(--eg-success) 18%, transparent);
    --eg-error-bg: color-mix(in srgb, var(--eg-error) 18%, transparent);
    --eg-warning-bg: color-mix(in srgb, var(--eg-warning) 18%, transparent);
  }
`;

const STATUS_COLOR: Record<CallPhase, string> = {
  idle: "var(--eg-text-2)",
  ringing: "var(--eg-warning)",
  connecting: "var(--eg-primary)",
  active: "var(--eg-success)",
  ended: "var(--eg-text-2)",
  error: "var(--eg-error)",
};

export function statusColor(phase: CallPhase): string {
  return STATUS_COLOR[phase] ?? "var(--eg-text-2)";
}
```

- [ ] **Step 4: Запустить тест — зелёный**

Run: `cd frontend && npm test -- tokens`
Expected: PASS (2 теста).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/theme/tokens.ts frontend/test/tokens.test.ts
git commit -m "feat(call-card): токен-слой design.pen → HA theme-переменные"
```

### Task 0.2: Скелет карточки (шапка + статус-строка + окно ответа + стейдж-заглушка)

**Files:**
- Modify: `frontend/src/eg-intercom-call-card.ts` (render + styles; сохранить существующие `setConfig/_active/_phase/willUpdate/таймеры/сервисы`)

**Interfaces:**
- Consumes: `egTokens`, `statusColor` из `theme/tokens.js`; `deriveView`, `toPhase` из `state-machine.js`.
- Produces: разметка `.card > header + .statusrow + <eg-call-stage> + .banner + .open-area + .actions` с классами, на которые опираются слайсы 1–6.

- [ ] **Step 1: Заменить `render()` шапкой+статусом по макету (узел incoming_call `Z1sbL`)**

Структура (точные значения — из Global Constraints): `header` = `L(name fs22 fw700 + addr fs13 text-2)` + `Close(44×44 r-full elevated, mdi:close)`; `statusrow` = ряд `badge(dot 8 + текст fs13 fw600, цвет=statusColor) · countdown(mdi:timer-outline + fs15 text-2)` + `window(h4 r-full elevated){ fill(warning, width = оставшееся окно %) }`. Таймер активного — `--eg-mono`. Окно ответа показывать только на `ringing`.

```ts
private _renderHeader(): TemplateResult {
  return html`
    <header>
      <div class="hgroup">
        <span class="name" title=${this._intercomName}>${this._intercomName}</span>
        ${this._address ? html`<span class="addr">${this._address}</span>` : nothing}
      </div>
      <button class="close" @click=${this._dismiss} aria-label="Свернуть">
        <ha-icon icon="mdi:close"></ha-icon>
      </button>
    </header>
  `;
}
```

(Полные `_renderStatus`, `_address`, `_dismiss` — реализовать по тем же токенам; `_dismiss` пока `this.dispatchEvent(new CustomEvent("eg-dismiss"))` — карточка остаётся, звонок на фоне.)

- [ ] **Step 2: Стейдж — временно прежний `<eg-call-video>` (оверлеи в Slice 3)**

Оставить `<eg-call-video .hass .entity .muted>` внутри `.stage` (16:9, r-md). Слайдер/кнопки — прежние (заменяются в Slice 1–2).

- [ ] **Step 3: Стили — подключить токены и точные размеры**

```ts
static override styles = [egTokens, css`
  :host { display:block; height:100%; container-type: inline-size; }
  ha-card { height:100%; box-sizing:border-box; background:var(--eg-card); border-radius:var(--eg-r-card); }
  .content { display:flex; flex-direction:column; gap:20px; padding:6px 16px 28px; }
  header { display:flex; align-items:flex-start; justify-content:space-between; gap:12px; }
  .name { font-size:22px; font-weight:700; color:var(--eg-text); }
  .addr { font-size:13px; color:var(--eg-text-2); }
  .close { width:44px; height:44px; border:none; border-radius:var(--eg-r-full); background:var(--eg-elevated); color:var(--eg-text-2); display:flex; align-items:center; justify-content:center; cursor:pointer; }
  /* … statusrow / badge / window / stage — по Global Constraints … */
`];
```

- [ ] **Step 4: Собрать и проверить в браузере**

Run: `cd frontend && node build.mjs`
Expected: сборка без ошибок; `www/eg-intercom-call-card.js` обновлён.
Визуальная проверка (browser-testing-with-devtools): смонтировать карточку с мок-`hass` (`call_state=ringing`), сверить шапку+статус со скриншотом узла `Z1sbL`. Совпадение: имя fs22, адрес fs13, close-круг, badge warning, окно ответа.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/eg-intercom-call-card.ts
git commit -m "feat(call-card): шапка + статус-строка + окно ответа по макету (slice 0)"
```

---

## Slice 1 — Слайдер/hold заново (`open-control`)

### Task 1.1: Обновить константы и математику жеста

**Files:**
- Modify: `frontend/src/components/open-control.ts` (константы `KNOB`, `TRACK_H`)
- Test: `frontend/test/open-control.test.ts`

**Interfaces:**
- Produces: `slideProgress`, `holdProgress`, `clamp01`, `SLIDE_COMPLETE`, `HOLD_MS` (сигнатуры прежние); knob-константа `68`.

- [ ] **Step 1: Обновить тест под knob=68**

```ts
import { slideProgress, SLIDE_COMPLETE } from "../src/components/open-control.js";

it("slideProgress учитывает knob 68 и полную ширину трека", () => {
  // трек 300, knob 68 → usable 232; указатель у правого края → ~1
  expect(slideProgress(300, 0, 300, 68)).toBeGreaterThanOrEqual(SLIDE_COMPLETE);
  expect(slideProgress(34, 0, 300, 68)).toBeCloseTo(0, 1); // центр knob у левого края
});
```

- [ ] **Step 2: Запустить — падает**

Run: `cd frontend && npm test -- open-control`
Expected: FAIL (текущий knob=60 в `_onSlideMove`).

- [ ] **Step 3: Заменить knob-константу на 68 в `_onSlideMove` и CSS `--knob`**

```ts
const knob = 68;
this._progress = slideProgress(e.clientX, this._trackRect.left, this._trackRect.width, knob);
```

- [ ] **Step 4: Тест зелёный**

Run: `cd frontend && npm test -- open-control`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/open-control.ts frontend/test/open-control.test.ts
git commit -m "feat(open-control): knob 68pt по макету (slice 1)"
```

### Task 1.2: Слайдер — точная разметка/стили + стадии (узлы `UZrKy`, `ecmXJ`)

**Files:**
- Modify: `frontend/src/components/open-control.ts` (render + styles)

**Interfaces:**
- Consumes: `egTokens`.
- Produces: `<eg-open-control mode status>` с DOM: `.track{ .hint-lock(под thumb) · .fill · .label «Открыть» · .end(lock-open) · .knob(key) }`; подпись «Дверь открыта · <время>» и «Не удалось открыть · Повторить».

- [ ] **Step 1: Слайдер-стадии по макету**

Реализовать (значения — Global Constraints): трек `h80 r-full elevated`; thumb `68×68 primary` (`mdi:key-variant`, `--eg-on-fill`); в покое закрытый `mdi:lock` лежит ПОД thumb (проявляется при отъезде); торец `44×68`, `mdi:lock-open-variant` `text-3`; «Открыть» `fs17 fw600 text` по центру; шлейф за thumb — `--eg-primary` @ ~15%. Успех: трек `--eg-success`, «Открыто» `--eg-on-fill`, thumb справа `--eg-success` (`mdi:lock-open-variant`); подпись `success` «Дверь открыта · <время>». Ошибка: thumb в покой, подпись `--eg-error` «Не удалось открыть · Повторить». Прокинуть `openedAt`-время из карточки (проп `caption`).

- [ ] **Step 2: Hold-режим по макету (узел `A8dfFd`)**

Пилюля outlined `--eg-primary` (обводка, фон прозрачный), контент неподвижен (`mdi:key-variant` + «Удерживайте, чтобы открыть» по центру); заливка `--eg-primary` @ ~20% бежит слева-направо под контентом (`_progress`), откат на раннем `pointerup`; успех — зелёная «Открыто»; ошибка — покой + подпись под пилюлей.

- [ ] **Step 3: Стили `static styles = [egTokens, css\`…\`]`**

Заменить хардкод-цвета на `--eg-*`. `.track{min-height:80px}`, `--knob:68px`, `.knob{width/height 68}`, `.end{width:44px}`. Full-width (`width:100%`, без `max-width:300px` в мобайл-инстансе — ширину диктует контейнер).

- [ ] **Step 4: Собрать + визуальная сверка**

Run: `cd frontend && node build.mjs`
Визуально сверить 3 стадии слайдера с узлом `UZrKy` и успех — с `ecmXJ` (зелёный трек, ключ справа, подпись «Дверь открыта · 11:25»). Hold — с `A8dfFd`.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/open-control.ts
git commit -m "feat(open-control): слайдер/hold стадии по макету — размеры, торец-замок, «Открыто» (slice 1)"
```

---

## Slice 2 — Ряды кнопок по фазам

### Task 2.1: Расширить модель `CallView` (набор действий + флаги)

**Files:**
- Modify: `frontend/src/state-machine.ts`
- Test: `frontend/test/state-machine.test.ts`

**Interfaces:**
- Produces: `type ActionKind = "accept"|"reject"|"hangup"|"cancel"|"connecting"|"mic"|"sound"|"retry"|"close"`; `CallView.actions: ActionKind[]`; флаги `showAnswerWindow: boolean`, `showOpen`, `showBanner?` (в Slice 4). `deriveView(phase)` возвращает `actions` по фазе: ringing→`["reject","accept"]`; connecting→`["cancel","connecting"]`; active→`["mic","sound","hangup"]`; error/connection_lost→`["retry","hangup"]`; ended→`["close"]`.

- [ ] **Step 1: Тест на action-наборы**

```ts
import { deriveView } from "../src/state-machine.js";
it("actions по фазам совпадают с макетами", () => {
  expect(deriveView("ringing").actions).toEqual(["reject","accept"]);
  expect(deriveView("connecting").actions).toEqual(["cancel","connecting"]);
  expect(deriveView("active").actions).toEqual(["mic","sound","hangup"]);
  expect(deriveView("error").actions).toEqual(["retry","hangup"]);
});
it("окно ответа только на ringing", () => {
  expect(deriveView("ringing").showAnswerWindow).toBe(true);
  expect(deriveView("active").showAnswerWindow).toBe(false);
});
```

- [ ] **Step 2: Запустить — падает** — Run: `cd frontend && npm test -- state-machine` → FAIL.

- [ ] **Step 3: Дописать `ActionKind`, поля в `CallView`, наборы в каждом `case` `deriveView`.** (Сохранить существующие поля `video/showOpen/showTimer/busy/isError/visible`.)

- [ ] **Step 4: Тест зелёный** — Run: `cd frontend && npm test -- state-machine` → PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/state-machine.ts frontend/test/state-machine.test.ts
git commit -m "feat(call-card): модель действий по фазам в CallView (slice 2)"
```

### Task 2.2: Рендер рядов кнопок из `actions` (узлы `Z1sbL`,`s2c1h`,`guqYE`)

**Files:**
- Modify: `frontend/src/eg-intercom-call-card.ts`

**Interfaces:**
- Consumes: `view.actions`, `statusColor`.
- Produces: `.actions` из круглых кнопок `68×68`; фабрика `_actionButton(kind)` → нужная иконка/цвет/подпись/handler.

- [ ] **Step 1: Фабрика кнопок**

`accept`→`mdi:phone` `--eg-success` «Принять» `_answer`; `reject`/`hangup`→`mdi:phone-hangup` `--eg-error` «Отклонить»/«Завершить» `_hangup`; `cancel`→`mdi:phone-hangup` `--eg-error` «Отменить» `_hangup`; `connecting`→спиннер disabled «Соединяем…»; `mic`→`_renderMic()` (состояния); `sound`→`mdi:volume-high/off` «Звук» `_toggleMute` (warning при audio_blocked — Slice 3); `retry`→`mdi:refresh` `--eg-primary` «Повторить» `_retry`; `close`→`mdi:close` neutral «Закрыть» `_dismiss`. Круг цветной = fill-роль + `--eg-on-fill` иконка; нейтральный = `--eg-elevated` + `--eg-text` иконка.

- [ ] **Step 2: Стили круга 68 + спиннер-кнопка**

`.circle{min-width:68px}`, `.circle .ic{width:68px;height:68px;border-radius:var(--eg-r-full);background:var(--eg-elevated)}`, `--mdc-icon-size:28px`, подпись `fs12 fw500 text-2`. Спиннер — как существующий `.spinner`, но в круге.

- [ ] **Step 3: Собрать + визуальная сверка** — Run: `cd frontend && node build.mjs`. Сверить ringing (`Z1sbL`: Отклонить/Принять), connecting (`s2c1h`: Отменить + «Соединяем…» спиннер), active (`guqYE`: Микрофон/Звук/Завершить).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/eg-intercom-call-card.ts
git commit -m "feat(call-card): ряды кнопок по фазам (68pt, спиннер connecting) (slice 2)"
```

---

## Slice 3 — Оверлеи видео + плейсхолдеры (`call-stage`)

### Task 3.1: `call-video` — убрать `controls`, вынести плейсхолдеры

**Files:**
- Modify: `frontend/src/components/call-video.ts`
- Test: `frontend/test/call-video.test.ts`

**Interfaces:**
- Produces: `<eg-call-video>` — chromeless-плеер (без `controls`), `pickCameraEntity` без изменений. Плейсхолдер «нет провайдера» — минимальный (детальные плейсхолдеры — в `call-stage`).

- [ ] **Step 1: Тест — в шаблоне HA-провайдера НЕТ `controls`** (обновить существующий `call-video.test.ts`; UX-док §13.1 — `controls` ломает tap-to-unmute и паузит звонок).

- [ ] **Step 2: Запустить — падает** (сейчас `controls` в строке 102) → FAIL.

- [ ] **Step 3: Убрать `controls` из `<ha-camera-stream>`; убрать внутренние `_frame(...)` кроме «плеер недоступен».**

- [ ] **Step 4: Тест зелёный.**

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/call-video.ts frontend/test/call-video.test.ts
git commit -m "fix(call-video): chromeless-плеер без controls (tap-to-unmute) (slice 3)"
```

### Task 3.2: `<eg-call-stage>` — видео + оверлеи + плейсхолдеры + tap-to-unmute

**Files:**
- Create: `frontend/src/components/call-stage.ts`
- Test: `frontend/test/call-stage.test.ts`

**Interfaces:**
- Consumes: `egTokens`, `eg-call-video`.
- Produces: `<eg-call-stage .hass .entity .muted .live .timestamp .stageState .audioBlocked>`; `stageState: "live"|"camera_off"|"connection_lost"|"ended"`; чистая `pickStageContent(stageState)` (что рендерить). Emits `unmute` (tap по видео в `audioBlocked`).

- [ ] **Step 1: Тест на `pickStageContent`**

```ts
import { pickStageContent } from "../src/components/call-stage.js";
it("выбор содержимого стейджа по состоянию", () => {
  expect(pickStageContent("live")).toBe("video");
  expect(pickStageContent("camera_off")).toBe("placeholder-camera");
  expect(pickStageContent("connection_lost")).toBe("placeholder-connection");
  expect(pickStageContent("ended")).toBe("video-dimmed");
});
```

- [ ] **Step 2: Запустить — падает** → FAIL.

- [ ] **Step 3: Реализовать `call-stage`.** Оверлеи (абсолютные, `inset:0` слои над видео): `LIVE`-бейдж (top-left, красный `#EF5350` фон, `--eg-on-fill`, «● LIVE»); таймстамп (bottom-left, scrim-подложка, `fs12`); чип «🔊 Звук вкл.» (top-right, scrim, `mdi:volume-high`) при `!muted && live`; CTA «Нажмите, чтобы включить звук» (центр-низ, scrim-чип, `mdi:volume-off`) при `audioBlocked`; tap-слой (`inset:0`, прозрачный) → `unmute`. Плейсхолдеры: `camera_off` — elevated-фрейм `mdi:video-off` + «Видео недоступно» + «Аудиовызов продолжается» (узел `iSJr4`); `connection_lost` — `mdi:wifi-off` `--eg-error` + «Соединение прервано» + «Пробуем восстановить…» (узел `l9V770`); `ended` — видео + затемнение scrim (узел `llgeR`).

- [ ] **Step 4: Тест зелёный + сборка.** Run: `cd frontend && npm test -- call-stage && node build.mjs`.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/call-stage.ts frontend/test/call-stage.test.ts
git commit -m "feat(call-stage): видео-оверлеи LIVE/таймстамп/чип/CTA + плейсхолдеры (slice 3)"
```

### Task 3.3: Встроить `call-stage` в карточку + audio_blocked слой

**Files:**
- Modify: `frontend/src/eg-intercom-call-card.ts`

**Interfaces:**
- Consumes: `<eg-call-stage>`; локальный флаг `_audioBlocked`.
- Produces: карточка передаёт `stageState/live/timestamp/audioBlocked`, слушает `@unmute`; кнопка «Звук» получает warning-стиль при `_audioBlocked` (узел `I3yiL8`).

- [ ] **Step 1: Заменить `<eg-call-video>` на `<eg-call-stage>`; вычислять `stageState`** из фазы+флагов (active+cameraOK→`live`; camera недоступна→`camera_off`; `error/connection_lost`→`connection_lost`; ended→`ended`).

- [ ] **Step 2: audio_blocked** — при неудаче автоплея со звуком (`_enterActive`: если `video.muted` осталось true без жеста) выставить `_audioBlocked=true`; `@unmute`/тап по «Звук» → `muted=false`, `_audioBlocked=false`. Кнопка «Звук» при `_audioBlocked` — `--eg-warning`, подпись «Звук выкл.».

- [ ] **Step 3: Сборка + визуальная сверка** — Run: `cd frontend && node build.mjs`. Сверить active (`guqYE`: LIVE+чип), audio_blocked (`I3yiL8`: CTA + жёлтая «Звук выкл.»), camera (`iSJr4`), ended (`llgeR`).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/eg-intercom-call-card.ts
git commit -m "feat(call-card): интеграция call-stage + слой audio_blocked (slice 3)"
```

---

## Slice 4 — Баннеры / ошибки / retry / close

### Task 4.1: Баннер mic_permission_required (узел `iUNo1`)

**Files:**
- Modify: `frontend/src/eg-intercom-call-card.ts`

**Interfaces:**
- Consumes: `_micPerm`, `_mic.secure` (уже есть).
- Produces: `.banner.warn` между стейджем и слайдером при `active && (mic denied/prompt || !secure)`.

- [ ] **Step 1: Рендер баннера** — warning-фрейм (`--eg-warning-bg` фон, `--eg-warning` иконка `mdi:microphone-off`), текст «Нет доступа к микрофону · Вас не слышно» `fs13`, кнопка «Разрешить» (outlined warning) `@click=${this._toggleMic}`. Показывать по флагу из view/локального стейта. Кнопка «Микрофон» в ряду при denied — `--eg-error`, подпись «Нет доступа» (узел `iUNo1`).

- [ ] **Step 2: Сборка + сверка с `iUNo1`.** Run: `cd frontend && node build.mjs`.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/eg-intercom-call-card.ts
git commit -m "feat(call-card): баннер «нет доступа к микрофону» + «Разрешить» (slice 4)"
```

### Task 4.2: connection_lost (retry) + call_ended (close) + door_error подпись

**Files:**
- Modify: `frontend/src/eg-intercom-call-card.ts`

**Interfaces:**
- Consumes: `view.actions` (`retry`/`close` уже в модели), `_openStatus` (`error`).
- Produces: `_retry` (повтор answer/open), `_dismiss` (close); door-error подпись под слайдером (`--eg-error`, 4с) — уже через `open-control` `status="error"`.

- [ ] **Step 1: Реализовать `_retry`** (на `connection_lost`/`error` — повтор `answer`; на door-error — повтор `_open`). Ряды `retry+hangup` (узел `l9V770`) и `close` (узел `llgeR`) уже рендерятся из `actions` (Slice 2) — проверить корректность иконок/цветов.

- [ ] **Step 2: Сборка + сверка** `l9V770` (Повторить/Завершить) и `llgeR` (Закрыть).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/eg-intercom-call-card.ts
git commit -m "feat(call-card): connection_lost retry + call_ended close (slice 4)"
```

---

## Slice 5 — Idle + компактная карточка

### Task 5.1: Idle по макету (узел `aSs3Z` нижняя часть)

**Files:**
- Modify: `frontend/src/eg-intercom-call-card.ts` (`_renderIdle`)

- [ ] **Step 1:** door-иконка `mdi:door` в круге `--eg-elevated`; «Нет активного вызова» `fw700`; «Видео появится при звонке в домофон» `text-2`; чипы точек — elevated-пилюли `mdi:door` + имя (`_doorbellNames()`), тап = открыть (slide-confirm, later). Заменить прежний `mdi:doorbell-video`/check-chips.

- [ ] **Step 2: Сборка + сверка с `aSs3Z`.** — Run: `cd frontend && node build.mjs`.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/eg-intercom-call-card.ts
git commit -m "feat(call-card): idle с door-иконкой и чипами точек по макету (slice 5)"
```

### Task 5.2: Компактная карточка (узел `aSs3Z` верхняя часть)

**Files:**
- Modify: `frontend/src/eg-intercom-call-card.ts`

**Interfaces:**
- Produces: раскладка `.compact` при узком контейнере (`@container (max-width: 360px)`) ИЛИ `config.layout==="compact"`: строка `[мини-видео 96×72 LIVE] [имя + «● Вызов · 0:24»] [🔑 ❌ 📞]`.

- [ ] **Step 1:** Компакт-ветка в `render()`; мини-`<eg-call-stage>` `96×72` (или мини-превью), имя `fw600`, статус `fs13`, 3 круглые кнопки `48×48` (`key`/`hangup`/`accept`). Container-query порог.

- [ ] **Step 2: Сборка + сверка с `aSs3Z` (верх).**

- [ ] **Step 3: Commit**

```bash
git add frontend/src/eg-intercom-call-card.ts
git commit -m "feat(call-card): компактная строка вызова (slice 5)"
```

---

## Slice 6 — Адаптив: настенная панель + десктоп + паритет тем

### Task 6.1: Настенная 2-колонки (узлы `SGWYt`,`QowWr`)

**Files:**
- Modify: `frontend/src/eg-intercom-call-card.ts` (styles, container-queries)

- [ ] **Step 1:** `@container (min-width: 900px)`: `.content` → 2 колонки (`grid` / `flex row`): слева видео-герой 16:9 (растёт), справа колонка контролов `~340px` (слайдер по вертикали центра, кнопки `100pt` по низу); шапка спанит верх (имя+адрес слева, статус+автосброс справа). Сверить с `SGWYt`/`QowWr`.

- [ ] **Step 2: Десктоп** `@container (min-width: 560px) and (max-width: 900px)`: компактная широкая карточка; на fine-pointer — hold (`resolveOpenAction`). Модалка-обрамление (тень/скругление) при `config.layout==="modal"` — узел `bjNxZ`.

- [ ] **Step 3: Сборка + сверка** `SGWYt`,`QowWr`,`bjNxZ`.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/eg-intercom-call-card.ts
git commit -m "feat(call-card): настенная 2-колонки + десктоп адаптив (slice 6)"
```

### Task 6.2: Паритет светлой темы + reduced-motion + a11y

**Files:**
- Modify: `frontend/src/eg-intercom-call-card.ts`, `open-control.ts`, `call-stage.ts` (только если найдены хардкоды)

- [ ] **Step 1:** Прогнать светлую тему (узлы `GEYUi`,`O4PYQ`): все цвета берутся из `--eg-*` (нет хардкодов кроме scrim/LIVE). `prefers-reduced-motion` отключает slide/spinner/pulse. Проверить `aria-label` на всех кнопках, `role="slider"`.

- [ ] **Step 2: Сборка + сверка обеих тем.** Run: `cd frontend && node build.mjs`.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/
git commit -m "feat(call-card): паритет светлой темы + reduced-motion + a11y (slice 6)"
```

---

## Slice 7 — Тесты, docs sync, review, история

### Task 7.1: Догнать тесты и прогнать полный набор

**Files:**
- Modify/Create: `frontend/test/*`

- [ ] **Step 1:** Полный прогон — Run: `cd frontend && npm test`. Expected: все зелёные. Дописать недостающие (view-model, gesture, call-stage выбор). Не упрощать тесты ради зелёного (`.claude/rules/test-coverage.md`).
- [ ] **Step 2: Финальная сборка** — Run: `cd frontend && node build.mjs` → без ошибок.
- [ ] **Step 3: Commit** — `test(call-card): покрытие перевёрстки`.

### Task 7.2: Docs sync

**Files:**
- Modify: `CHANGELOG.md` (`[Unreleased]`), `docs/project/project-map.md` (новые `tokens.ts`,`call-stage.ts`), `docs/features/intercom-two-way-audio/call-card-ux-production.md` (статус → реализовано), `docs/roadmap.md`.

- [ ] **Step 1:** Обновить перечисленное. `unique_id`/config-контракт без breaking — отметить в CHANGELOG. **Step 2: Commit** — `docs(call-card): sync CHANGELOG/project-map/roadmap`.

### Task 7.3: Code-review + git-историан

- [ ] **Step 1:** Запустить `code-reviewer` subagent по диффу (`.claude/rules/pre-pr-checklist.md`); применить P0/P1.
- [ ] **Step 2:** `git-historian` — `HISTORY_CLEAN` (схлопнуть slice-фиксапы если есть).
- [ ] **Step 3:** Финальный прогон тестов+сборки; отчёт пользователю (без push/PR без явной команды — `.claude/rules/pre-pr-checklist.md`, boundary «Ask first»).

---

## Self-Review (проверка плана против спеки)

**Покрытие макетов (6 секций):** 01 мобайл→Slice 0–3; 02 состояния (audio_blocked/mic/camera/connection_lost/ended)→Slice 3–4; 03 светлая→Slice 6.2; 04 настенная→Slice 6.1; 05 десктоп+компакт+idle→Slice 5,6.1; 06 слайдер/hold стадии+мульти→Slice 1 (мульти-домофон-список — покрыт существующим `_active`-выбором; отдельный список-UI `LZnZu` — опционально, при необходимости добавить в Slice 5). ✅
**Плейсхолдеры:** нет TBD/«обработать ошибки» — значения и узлы указаны. ✅
**Консистентность типов:** `ActionKind`, `stageState`, `statusColor`, `egTokens` — определены в задачах 2.1/3.2/0.1 и используются согласованно. ✅
**Открытый пункт для исполнителя:** список-UI нескольких домофонов (`LZnZu`) — если у пользователя >1 активного домофона; текущая модель «активен один» (UX-док §4 п.16) уже покрывает MVP.
