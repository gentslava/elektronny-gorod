// Адаптивный контрол открытия двери: slide (тач) | hold (десктоп) | tap.
// Защита от случайного открытия + «не инородно» (на стиле HA-слайдера, theme-токены).
// Чистая математика жеста вынесена в экспортируемые функции (юнит-тесты).
import { LitElement, css, html, type TemplateResult } from "lit";
import { customElement, property, state } from "lit/decorators.js";

import type { OpenAction } from "../util/open-action.js";
import "./eg-icon.js";

/** Зажать в [0..1]. */
export function clamp01(x: number): number {
  return x < 0 ? 0 : x > 1 ? 1 : x;
}

/** Прогресс slide по позиции указателя относительно дорожки (0..1). */
export function slideProgress(
  pointerX: number,
  trackLeft: number,
  trackWidth: number,
  knobWidth: number,
): number {
  const usable = Math.max(1, trackWidth - knobWidth);
  return clamp01((pointerX - trackLeft - knobWidth / 2) / usable);
}

/** Прогресс hold по времени удержания (0..1). */
export function holdProgress(elapsedMs: number, durationMs: number): number {
  return clamp01(elapsedMs / Math.max(1, durationMs));
}

/** Порог завершения slide (почти до конца — чтобы не «перелетать»). */
export const SLIDE_COMPLETE = 0.92;
/** Длительность удержания для hold. */
export const HOLD_MS = 800;

/**
 * `<eg-open-control mode hold|slide|tap>` — на завершении жеста шлёт `open`-событие.
 * Карта слушает `@open` и вызывает `lock.unlock`.
 */
@customElement("eg-open-control")
export class EgOpenControl extends LitElement {
  @property() public mode: OpenAction = "hold";
  @property({ type: Boolean }) public disabled = false;
  @property() public label = "Открыть дверь";
  /** Внешний статус: idle | opening | opened | error (для подписи/цвета). */
  @property() public status: "idle" | "opening" | "opened" | "error" = "idle";

  @state() private _progress = 0;
  @state() private _arming = false;

  private _raf = 0;
  private _holdStart = 0;
  private _trackRect: DOMRect | null = null;

  private _fireOpen(): void {
    this.dispatchEvent(new CustomEvent("open", { bubbles: true, composed: true }));
  }

  private _reset(): void {
    if (this._raf) cancelAnimationFrame(this._raf);
    this._raf = 0;
    this._arming = false;
    this._progress = 0;
    this._trackRect = null;
  }

  // ---- hold ----
  private _holdTick = (): void => {
    this._progress = holdProgress(performance.now() - this._holdStart, HOLD_MS);
    if (this._progress >= 1) {
      this._reset();
      this._fireOpen();
      return;
    }
    this._raf = requestAnimationFrame(this._holdTick);
  };

  private _onHoldDown = (e: PointerEvent): void => {
    if (this.disabled) return;
    (e.target as HTMLElement).setPointerCapture?.(e.pointerId);
    this._arming = true;
    this._holdStart = performance.now();
    this._raf = requestAnimationFrame(this._holdTick);
  };

  private _onHoldUp = (): void => {
    if (this._progress < 1) this._reset();
  };

  // ---- slide ----
  private _onSlideDown = (e: PointerEvent): void => {
    if (this.disabled) return;
    const track = (e.currentTarget as HTMLElement).closest(".track") as HTMLElement | null;
    this._trackRect = track?.getBoundingClientRect() ?? null;
    (e.target as HTMLElement).setPointerCapture?.(e.pointerId);
    this._arming = true;
  };

  private _onSlideMove = (e: PointerEvent): void => {
    if (!this._arming || !this._trackRect) return;
    const knob = 60;
    this._progress = slideProgress(
      e.clientX,
      this._trackRect.left,
      this._trackRect.width,
      knob,
    );
  };

  private _onSlideUp = (): void => {
    if (this._progress >= SLIDE_COMPLETE) {
      this._reset();
      this._fireOpen();
    } else {
      this._reset();
    }
  };

  // ---- tap ----
  private _onTap = (): void => {
    if (!this.disabled) this._fireOpen();
  };

  protected override render(): TemplateResult {
    if (this.mode === "tap") return this._renderTap();
    if (this.mode === "slide") return this._renderSlide();
    return this._renderHold();
  }

  private _caption(): string {
    if (this.status === "opening") return "Открываю…";
    if (this.status === "opened") return "Открыто";
    if (this.status === "error") return "Ошибка";
    // hold (десктоп) не самоочевиден — явно просим удерживать. slide/tap — коротко.
    if (this.mode === "hold") return "Удерживайте, чтобы открыть";
    return "Открыть";
  }

  /** Иконка плашки hold/tap: закрытый замок → открытый при успехе. */
  private _iconName(): string {
    if (this.status === "opened") return "lock-open";
    return "lock";
  }

  /** Иконка кружка-слайдера: ключ (тащим к замку), замок при результате. */
  private _knobIcon(): string {
    if (this.status === "opened") return "lock-open";
    if (this.status === "error") return "lock";
    return "key-round";
  }

  /** Визуальный прогресс: при «открыто»/«ошибка» — заполнено целиком. */
  private _vp(): number {
    return this.status === "opened" || this.status === "error" ? 1 : this._progress;
  }

  private _statusClass(): string {
    if (this.status === "opened") return "st-opened";
    if (this.status === "error") return "st-error";
    if (this.status === "opening") return "st-opening";
    return "";
  }

  private _renderTap(): TemplateResult {
    return html`
      <button class="bar tap ${this._statusClass()}" ?disabled=${this.disabled} @click=${this._onTap}
              aria-label=${this.label}>
        <div class="fill" style="width:${this._vp() * 100}%"></div>
        <span class="bar-label"><eg-icon name=${this._iconName()}></eg-icon>${this._caption()}</span>
      </button>
    `;
  }

  private _renderHold(): TemplateResult {
    return html`
      <button
        class="bar hold ${this._arming ? "arming" : ""} ${this._statusClass()}"
        ?disabled=${this.disabled}
        aria-label="${this.label} — удерживайте"
        @pointerdown=${this._onHoldDown}
        @pointerup=${this._onHoldUp}
        @pointercancel=${this._onHoldUp}
        @pointerleave=${this._onHoldUp}
      >
        <div class="fill" style="width:${this._vp() * 100}%"></div>
        <span class="bar-label">
          <eg-icon name=${this._iconName()}></eg-icon>
          ${this._caption()}
        </span>
      </button>
    `;
  }

  private _renderSlide(): TemplateResult {
    const vp = this._vp();
    return html`
      <div
        class="track ${this._statusClass()} ${this._arming ? "dragging" : ""}"
        style="--eg-prog:${vp}"
        role="slider"
        aria-label=${this.label}
        aria-valuemin="0"
        aria-valuemax="100"
        aria-valuenow=${Math.round(vp * 100)}
      >
        <eg-icon class="hint hint-l" name="lock"></eg-icon>
        <eg-icon class="hint hint-r" name="lock-open"></eg-icon>
        <div class="fill"></div>
        <span class="bar-label">${this._caption()}</span>
        <div
          class="knob ${this.disabled ? "off" : ""}"
          @pointerdown=${this._onSlideDown}
          @pointermove=${this._onSlideMove}
          @pointerup=${this._onSlideUp}
          @pointercancel=${this._onSlideUp}
        >
          <eg-icon name=${this._knobIcon()}></eg-icon>
        </div>
      </div>
    `;
  }

  static override styles = css`
    :host {
      display: block;
    }
    .bar,
    .track {
      position: relative;
      overflow: hidden;
      min-height: 68px;
      border-radius: 34px;
      display: flex;
      align-items: center;
      justify-content: center;
      background: var(--secondary-background-color);
      color: var(--primary-text-color);
      font-weight: 600;
      font-size: 1.05rem;
      user-select: none;
      touch-action: none;
    }
    .bar {
      width: 100%;
      max-width: 340px;
      margin: 0 auto;
      border: none;
      cursor: pointer;
      font: inherit;
      font-weight: 600;
    }
    /* слайдер — подтверждение действия: узкий, не во всю ширину (как в оригинале) */
    .track {
      box-sizing: border-box;
      width: 100%;
      max-width: 300px;
      margin: 0 auto;
      --knob: 60px; /* крупная цель под палец: > 48dp Material / 44pt Apple HIG */
    }
    .bar[disabled] {
      opacity: 0.5;
      cursor: not-allowed;
    }
    .fill {
      position: absolute;
      inset: 0 auto 0 0;
      /* Открыть = accent (НЕ красный — красный за «Завершить», см. spec §3). */
      background: var(--primary-color);
      opacity: 0.16;
      transition: width 80ms linear;
    }
    /* на слайдере заливка следует за кнопкой через --eg-prog (тот же источник, без лага) */
    .track .fill {
      width: calc(var(--eg-prog, 0) * 100%);
    }
    .track.dragging .fill {
      transition: none;
    }
    .bar-label,
    .bar > span {
      position: relative;
      display: inline-flex;
      align-items: center;
      gap: 8px;
      z-index: 1;
    }
    /* подсказки направления: закрытый замок слева (старт), открытый справа (цель) */
    .hint {
      position: absolute;
      top: 50%;
      transform: translateY(-50%);
      --eg-icon-size: 22px;
      color: var(--secondary-text-color);
      opacity: 0.5;
      z-index: 0;
    }
    .hint-l {
      left: 20px;
    }
    .hint-r {
      right: 20px;
    }
    /* кружок слайдера: позиция строго по прогрессу (CSS left от --eg-prog, без JS-трансформа) */
    .knob {
      position: absolute;
      top: 4px;
      left: calc(var(--eg-prog, 0) * (100% - var(--knob, 60px)));
      width: var(--knob, 60px);
      height: var(--knob, 60px);
      border-radius: 50%;
      background: var(--primary-color);
      color: var(--text-primary-color, #fff);
      display: flex;
      align-items: center;
      justify-content: center;
      cursor: grab;
      touch-action: none;
      z-index: 2;
      box-shadow: 0 1px 4px rgba(0, 0, 0, 0.28);
      transition: left 0.18s ease;
    }
    .track.dragging .knob {
      transition: none;
      cursor: grabbing;
    }
    .knob.off {
      opacity: 0.5;
    }
    .knob eg-icon {
      --eg-icon-size: 26px;
    }
    .bar eg-icon {
      --eg-icon-size: 24px;
    }
    /* «Открыто»/«Ошибка»: на плашке hold/tap — вся плашка; на слайдере — ТОЛЬКО кнопка */
    .bar.st-opened .fill {
      background: var(--success-color, #2e7d32);
      opacity: 1;
    }
    .bar.st-error .fill {
      background: var(--error-color, #c62828);
      opacity: 1;
    }
    .bar.st-opened .bar-label,
    .bar.st-error .bar-label {
      color: #fff;
    }
    .bar.st-opened ha-icon,
    .bar.st-error ha-icon {
      color: #fff;
    }
    .track.st-opened .knob {
      background: var(--success-color, #2e7d32);
    }
    .track.st-error .knob {
      background: var(--error-color, #c62828);
    }
    @media (prefers-reduced-motion: reduce) {
      .fill,
      .knob {
        transition: none;
      }
    }
  `;
}
