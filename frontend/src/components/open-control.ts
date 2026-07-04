// Адаптивный контрол открытия двери: slide (тач) | hold (десктоп) | tap.
// Защита от случайного открытия, облик — по макетам pencil/design.pen (узлы
// SliderStages/HoldStages): трек 80 / ключ-thumb 68, торец-замок, стадии
// покой→тянем→«Открыто», подпись снизу. Математика жеста — экспортируемые
// pure-функции (юнит-тесты). Иконки — единый набор lucide (eg-icon).
import { LitElement, css, html, type TemplateResult } from "lit";
import { customElement, property, state } from "lit/decorators.js";

import type { OpenAction } from "../util/open-action.js";
import { egTokens } from "../theme/tokens.js";
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
/** Диаметр ключа-thumb (px) — совпадает с CSS --knob. */
const KNOB = 68;

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

  public override disconnectedCallback(): void {
    super.disconnectedCallback();
    this._reset(); // отменить RAF hold/slide при удалении элемента (гигиена)
  }

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
    this._progress = slideProgress(e.clientX, this._trackRect.left, this._trackRect.width, KNOB);
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
    const control =
      this.mode === "tap"
        ? this._renderTap()
        : this.mode === "slide"
          ? this._renderSlide()
          : this._renderHold();
    return html`
      <div class="wrap" style="--eg-prog:${this._vp()}">
        ${control}
        ${this._caption()}
      </div>
    `;
  }

  /** Подпись под контролом (цвет по статусу). */
  private _caption(): TemplateResult {
    let text = "";
    let cls = "";
    if (this.status === "opened") {
      text = "Дверь открыта";
      cls = "st-opened";
    } else if (this.status === "error") {
      text = "Не удалось открыть · Повторить";
      cls = "st-error";
    } else if (this.status === "opening") {
      text = "Открываю…";
    } else if (this.mode === "slide") {
      text = "Сдвиньте, чтобы открыть дверь";
    } else {
      return html``; // hold/tap: текст на пилюле, подписи в покое нет
    }
    return html`<span class="caption ${cls}">${text}</span>`;
  }

  /** Текст на контроле. */
  private _labelText(): string {
    if (this.status === "opened") return "Открыто";
    if (this.mode === "slide") return "Открыть";
    return "Удерживайте, чтобы открыть";
  }

  /** Иконка ключа/замка на пилюле hold/tap. */
  private _barIcon(): string {
    return this.status === "opened" ? "lock-open" : "key-round";
  }

  /** Иконка кружка-слайдера: ключ-thumb едет к открытому замку (всегда ключ). */
  private _knobIcon(): string {
    return "key-round";
  }

  /** Визуальный прогресс: при «открыто»/«ошибка» — заполнено целиком. */
  private _vp(): number {
    return this.status === "opened" ? 1 : this._progress;
  }

  private _statusClass(): string {
    if (this.status === "opened") return "st-opened";
    if (this.status === "error") return "st-error";
    return "";
  }

  private _renderTap(): TemplateResult {
    return html`
      <button class="pill tap ${this._statusClass()}" ?disabled=${this.disabled} @click=${this._onTap}
              aria-label=${this.label}>
        <div class="fill"></div>
        <span class="content"><eg-icon name=${this._barIcon()}></eg-icon>${this._labelText()}</span>
      </button>
    `;
  }

  private _renderHold(): TemplateResult {
    return html`
      <button
        class="pill hold ${this._arming ? "arming" : ""} ${this._statusClass()}"
        ?disabled=${this.disabled}
        aria-label="${this.label} — удерживайте"
        @pointerdown=${this._onHoldDown}
        @pointerup=${this._onHoldUp}
        @pointercancel=${this._onHoldUp}
        @pointerleave=${this._onHoldUp}
      >
        <div class="fill"></div>
        <span class="content"><eg-icon name=${this._barIcon()}></eg-icon>${this._labelText()}</span>
      </button>
    `;
  }

  private _renderSlide(): TemplateResult {
    return html`
      <div
        class="track ${this._statusClass()} ${this._arming ? "dragging" : ""}"
        role="slider"
        aria-label=${this.label}
        aria-valuemin="0"
        aria-valuemax="100"
        aria-valuenow=${Math.round(this._vp() * 100)}
      >
        <eg-icon class="lock-under" name="lock"></eg-icon>
        <eg-icon class="end" name="lock-open"></eg-icon>
        <div class="fill"></div>
        <span class="label">${this._labelText()}</span>
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

  static override styles = [
    egTokens,
    css`
      :host {
        display: block;
      }
      .wrap {
        display: flex;
        flex-direction: column;
        gap: 8px;
        align-items: center;
        width: 100%;
      }
      /* ---- общая заливка-прогресс ---- */
      .fill {
        position: absolute;
        inset: 0 auto 0 0;
        width: calc(var(--eg-prog, 0) * 100%);
        background: var(--eg-primary);
        opacity: 0.15;
        transition: width 0.2s ease;
      }
      /* ---- slide: трек 300×80 (макет: фиксированный, центрирован — не на всю ширину) ---- */
      .track {
        position: relative;
        width: 300px;
        max-width: 100%;
        height: 80px;
        border-radius: var(--eg-r-full);
        background: var(--eg-elevated);
        overflow: hidden;
        display: flex;
        align-items: center;
        justify-content: center;
        touch-action: none;
        user-select: none;
      }
      /* в покое заливки нет (иначе «залипло»); появляется только при перетаскивании */
      .track .fill {
        width: 0;
      }
      /* при drag правый край заливки строго = центр ключа (не обгоняет) */
      .track.dragging .fill {
        width: calc(40px + var(--eg-prog, 0) * (100% - 80px));
        transition: none;
      }
      /* закрытый замок под ключом (проявляется при отъезде): иконка 20, центр под ключом */
      .lock-under {
        position: absolute;
        left: 30px;
        top: 50%;
        transform: translateY(-50%);
        --eg-icon-size: 20px;
        color: var(--eg-text-3);
        z-index: 0;
      }
      /* торец: открытый замок (макет: иконка 20, центр 28px от правого края) */
      .end {
        position: absolute;
        right: 18px;
        top: 50%;
        transform: translateY(-50%);
        --eg-icon-size: 20px;
        color: var(--eg-text-3);
        z-index: 0;
      }
      .track .label {
        position: relative;
        z-index: 1;
        font-size: 17px;
        font-weight: 600;
        color: var(--eg-text);
      }
      .knob {
        position: absolute;
        top: 6px;
        left: calc(6px + var(--eg-prog, 0) * (100% - 80px));
        width: 68px;
        height: 68px;
        border-radius: 50%;
        background: var(--eg-primary);
        color: var(--eg-on-fill);
        display: flex;
        align-items: center;
        justify-content: center;
        cursor: grab;
        touch-action: none;
        z-index: 2;
        --eg-icon-size: 28px;
        transition: left 0.18s ease;
      }
      .track.dragging .knob {
        transition: none;
        cursor: grabbing;
      }
      .knob.off {
        opacity: 0.5;
      }
      /* slide success: зелёный трек + «Открыто» + ключ справа */
      .track.st-opened .fill {
        background: var(--eg-success);
        opacity: 1;
        width: 100%;
      }
      .track.st-opened .label {
        color: var(--eg-on-fill);
      }
      .track.st-opened .knob {
        background: var(--eg-success);
      }
      /* success: ключ-knob уехал вправо и накрыл торец — торец прячем */
      .track.st-opened .end {
        display: none;
      }
      /* ---- hold/tap: outlined-пилюля, контент неподвижен, заливка бежит ---- */
      .pill {
        position: relative;
        width: 100%;
        min-height: 64px;
        border-radius: var(--eg-r-full);
        border: 2px solid var(--eg-primary);
        background: transparent;
        color: var(--eg-text);
        display: flex;
        align-items: center;
        justify-content: center;
        overflow: hidden;
        cursor: pointer;
        touch-action: none;
        user-select: none;
        font: inherit;
        padding: 0 16px;
      }
      .pill.arming .fill {
        transition: none;
      }
      .pill .fill {
        opacity: 0.2;
      }
      .pill .content {
        position: relative;
        z-index: 1;
        display: inline-flex;
        align-items: center;
        gap: 8px;
        font-size: 17px;
        font-weight: 600;
        --eg-icon-size: 24px;
      }
      .pill[disabled] {
        opacity: 0.5;
        cursor: not-allowed;
      }
      .pill.st-opened {
        border-color: var(--eg-success);
      }
      .pill.st-opened .fill {
        background: var(--eg-success);
        opacity: 1;
        width: 100%;
      }
      .pill.st-opened .content {
        color: var(--eg-on-fill);
      }
      /* ---- подпись под контролом ---- */
      .caption {
        font-size: 12px;
        color: var(--eg-text-3);
        text-align: center;
      }
      .caption.st-opened {
        color: var(--eg-success);
      }
      .caption.st-error {
        color: var(--eg-error);
      }
      @media (prefers-reduced-motion: reduce) {
        .fill,
        .knob {
          transition: none;
        }
      }
    `,
  ];
}
