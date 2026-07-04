// Видео-область экрана вызова: chromeless-плеер (eg-call-video) + оверлеи
// (LIVE-бейдж, таймстамп, чип «Звук вкл.», CTA «включить звук») + плейсхолдеры
// (камера недоступна / связь прервана) + tap-to-unmute. Облик — по макетам
// pencil/design.pen (компонент CallVideo + узлы camera_unavailable/connection_lost).
// Единственные хардкод-цвета — scrim и красный LIVE (разрешённые исключения).
import { LitElement, css, html, nothing, type TemplateResult } from "lit";
import { customElement, property } from "lit/decorators.js";

import { egTokens } from "../theme/tokens.js";
import "./call-video.js";
import "./eg-icon.js";

interface HassLike {
  states: Record<string, { state: string; attributes: Record<string, unknown> }>;
  connection?: unknown;
}

export type StageState = "live" | "camera_off" | "connection_lost" | "ended";
export type StageContent = "video" | "placeholder-camera" | "placeholder-connection" | "video-dimmed";

/** Что рендерить в видео-области по состоянию стейджа (чистая — юнит-тест). */
export function pickStageContent(state: StageState): StageContent {
  switch (state) {
    case "camera_off":
      return "placeholder-camera";
    case "connection_lost":
      return "placeholder-connection";
    case "ended":
      return "video-dimmed";
    default:
      return "video";
  }
}

@customElement("eg-call-stage")
export class EgCallStage extends LitElement {
  @property({ attribute: false }) public hass?: HassLike;
  @property() public entity?: string;
  @property({ type: Boolean }) public muted = false;
  /** Показать красный бейдж LIVE. */
  @property({ type: Boolean }) public live = false;
  /** Показать чип «Звук выкл.» (звук выключен пользователем) — подсказка, почему тихо. */
  @property({ type: Boolean }) public soundOff = false;
  /** Таймстамп потока (bottom-left), пусто = скрыт. */
  @property() public timestamp = "";
  @property() public stageState: StageState = "live";
  /** Автоплей со звуком заблокирован — CTA + тап по всему видео снимают mute. */
  @property({ type: Boolean }) public audioBlocked = false;

  private _unmute = (): void => {
    this.dispatchEvent(new CustomEvent("unmute", { bubbles: true, composed: true }));
  };

  protected override render(): TemplateResult {
    const content = pickStageContent(this.stageState);
    if (content === "placeholder-camera") {
      return this._placeholder("video-off", "muted", "Видео недоступно", "Аудиовызов продолжается");
    }
    if (content === "placeholder-connection") {
      return this._placeholder("wifi-off", "err", "Соединение прервано", "Пробуем восстановить…");
    }
    return html`
      <eg-call-video .hass=${this.hass} .entity=${this.entity} .muted=${this.muted}></eg-call-video>
      ${content === "video-dimmed" ? html`<div class="dim" aria-hidden="true"></div>` : nothing}
      <div class="top">
        ${this.live
          ? html`<span class="live"><span class="live-dot" aria-hidden="true"></span>LIVE</span>`
          : nothing}
        ${this.soundOff
          ? html`<span class="chip"><eg-icon name="volume-x"></eg-icon>Звук выкл.</span>`
          : nothing}
      </div>
      ${this.timestamp && !this.audioBlocked ? html`<span class="ts">${this.timestamp}</span>` : nothing}
      ${this.audioBlocked
        ? html`
            <button class="tap" @click=${this._unmute} aria-label="Включить звук"></button>
            <span class="cta" aria-hidden="true">
              <eg-icon name="volume-x"></eg-icon>Нажмите, чтобы включить звук
            </span>
          `
        : nothing}
    `;
  }

  private _placeholder(icon: string, tone: string, title: string, sub: string): TemplateResult {
    return html`
      <div class="fallback ${tone}" role="img" aria-label=${title}>
        <eg-icon name=${icon}></eg-icon>
        <span class="fb-title">${title}</span>
        <span class="fb-sub">${sub}</span>
      </div>
    `;
  }

  static override styles = [
    egTokens,
    css`
      :host {
        position: absolute;
        inset: 0;
        display: block;
      }
      eg-call-video {
        position: absolute;
        inset: 0;
      }
      .dim {
        position: absolute;
        inset: 0;
        background: rgba(0, 0, 0, 0.5);
      }
      /* верхний ряд оверлеев: LIVE (слева) + чип звука (справа) */
      .top {
        position: absolute;
        top: 12px;
        left: 12px;
        right: 12px;
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        pointer-events: none;
      }
      .live {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 3px 9px;
        border-radius: var(--eg-r-full);
        background: rgba(211, 47, 47, 0.88);
        color: #fff;
        font-size: 10px;
        font-weight: 600;
        letter-spacing: 0.04em;
      }
      .live-dot {
        width: 6px;
        height: 6px;
        border-radius: 50%;
        background: #fff;
      }
      .chip {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 5px 10px;
        border-radius: var(--eg-r-full);
        background: rgba(0, 0, 0, 0.63);
        color: #fff;
        font-size: 11px;
      }
      .chip eg-icon {
        --eg-icon-size: 14px;
      }
      .ts {
        position: absolute;
        left: 12px;
        bottom: 12px;
        font-size: 10px;
        color: rgba(255, 255, 255, 0.69);
        font-variant-numeric: tabular-nums;
        pointer-events: none;
      }
      /* CTA «включить звук» + прозрачный tap-слой поверх всего видео */
      .tap {
        position: absolute;
        inset: 0;
        border: none;
        background: transparent;
        cursor: pointer;
        z-index: 2;
      }
      /* CTA — в НИЖНЕЙ части видео (не перекрывает лицо звонящего), UX §8/§13 */
      .cta {
        position: absolute;
        left: 50%;
        bottom: 16px;
        transform: translateX(-50%);
        display: inline-flex;
        align-items: center;
        gap: 8px;
        padding: 10px 18px;
        border-radius: var(--eg-r-full);
        background: var(--eg-scrim);
        color: #fff;
        font-size: 13px;
        font-weight: 500;
        white-space: nowrap;
        z-index: 3;
        pointer-events: none;
      }
      .cta eg-icon {
        --eg-icon-size: 18px;
      }
      /* плейсхолдеры (камера недоступна / связь прервана) */
      .fallback {
        position: absolute;
        inset: 0;
        background: var(--eg-card);
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: 6px;
        text-align: center;
        padding: 12px;
        box-sizing: border-box;
      }
      .fallback eg-icon {
        --eg-icon-size: 36px;
        color: var(--eg-text-3);
      }
      .fallback.err eg-icon {
        color: var(--eg-error);
      }
      .fb-title {
        font-size: 15px;
        color: var(--eg-text);
      }
      .fb-sub {
        font-size: 12px;
        color: var(--eg-text-2);
      }
    `,
  ];
}
