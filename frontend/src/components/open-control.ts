// Адаптивный контрол открытия двери: slide (тач) | hold (десктоп) | tap.
// Защита от случайного открытия + «не инородно» (на стиле HA-слайдера, theme-токены).
// Чистая математика жеста вынесена в экспортируемые функции (юнит-тесты).
import { LitElement, css, html, type TemplateResult } from "lit";
import { customElement, property, state } from "lit/decorators.js";

import type { OpenAction } from "../util/open-action.js";

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
    const knob = 56;
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
    return this.label;
  }

  private _renderTap(): TemplateResult {
    return html`
      <button class="bar tap" ?disabled=${this.disabled} @click=${this._onTap}
              aria-label=${this.label}>
        <ha-icon icon="mdi:key-variant"></ha-icon><span>${this._caption()}</span>
      </button>
    `;
  }

  private _renderHold(): TemplateResult {
    return html`
      <button
        class="bar hold ${this._arming ? "arming" : ""}"
        ?disabled=${this.disabled}
        aria-label="${this.label} — удерживайте"
        @pointerdown=${this._onHoldDown}
        @pointerup=${this._onHoldUp}
        @pointercancel=${this._onHoldUp}
        @pointerleave=${this._onHoldUp}
      >
        <div class="fill" style="width:${this._progress * 100}%"></div>
        <span class="bar-label">
          <ha-icon icon="mdi:key-variant"></ha-icon>
          ${this._arming ? "Удерживайте…" : this._caption()}
        </span>
      </button>
    `;
  }

  private _renderSlide(): TemplateResult {
    return html`
      <div class="track" aria-label="${this.label} — сдвиньте, чтобы открыть" role="slider"
           aria-valuemin="0" aria-valuemax="100"
           aria-valuenow=${Math.round(this._progress * 100)}>
        <div class="fill" style="width:${this._progress * 100}%"></div>
        <span class="bar-label">${this._caption()}</span>
        <div
          class="knob ${this.disabled ? "off" : ""}"
          style="transform:translateX(calc(${this._progress} * (100% + var(--eg-track-w, 0px))))"
          @pointerdown=${this._onSlideDown}
          @pointermove=${this._onSlideMove}
          @pointerup=${this._onSlideUp}
          @pointercancel=${this._onSlideUp}
        >
          <ha-icon icon="mdi:key-variant"></ha-icon>
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
      min-height: 56px;
      border-radius: 28px;
      display: flex;
      align-items: center;
      justify-content: center;
      background: var(--secondary-background-color);
      color: var(--primary-text-color);
      font-weight: 600;
      user-select: none;
      touch-action: none;
    }
    .bar {
      width: 100%;
      border: none;
      cursor: pointer;
      font: inherit;
      font-weight: 600;
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
      opacity: 0.25;
      transition: width 80ms linear;
    }
    .bar-label,
    .bar > span {
      position: relative;
      display: inline-flex;
      align-items: center;
      gap: 8px;
      z-index: 1;
    }
    .knob {
      position: absolute;
      left: 4px;
      width: 48px;
      height: 48px;
      border-radius: 50%;
      background: var(--primary-color);
      color: var(--text-primary-color, #fff);
      display: flex;
      align-items: center;
      justify-content: center;
      cursor: grab;
      touch-action: none;
      z-index: 2;
    }
    .knob.off {
      opacity: 0.5;
    }
    ha-icon {
      --mdc-icon-size: 24px;
    }
    @media (prefers-reduced-motion: reduce) {
      .fill {
        transition: none;
      }
    }
  `;
}
