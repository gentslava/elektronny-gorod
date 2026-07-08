// Видео вызова: HA-native плеер `ha-camera-stream` (видео+звук, WebRTC/HLS — как HA),
// без жёсткой зависимости от сторонних карточек. Fallback на `webrtc-camera`, если она
// уже установлена у пользователя. Звук — по `muted`-проп (autoplay-политика: старт
// возможно muted, снятие — жестом по кнопке звука в карточке). call-screen-display-design.md.
import { LitElement, css, html, nothing, type PropertyValues, type TemplateResult } from "lit";
import { customElement, property, state } from "lit/decorators.js";

import type { VideoSource } from "../state-machine.js";
import { type Lang, t } from "../i18n.js";
import "./eg-icon.js";

interface HassLike {
  states: Record<string, { state: string; attributes: Record<string, unknown> }>;
  connection?: unknown;
}

interface CamConfig {
  camera?: string;
  doorbell_camera?: string;
}

/** Какую камеру показывать: активный вызов (видео+звук) / домофон (ringing) / нет. */
export function pickCameraEntity(video: VideoSource, cfg: CamConfig): string | undefined {
  if (video === "call") return cfg.camera;
  if (video === "doorbell") return cfg.doorbell_camera ?? cfg.camera;
  return undefined;
}

type Provider = "pending" | "ha" | "webrtc" | "none";

@customElement("eg-call-video")
export class EgCallVideo extends LitElement {
  @property({ attribute: false }) public hass?: HassLike;
  @property() public entity?: string;
  @property({ type: Boolean }) public muted = false;
  /** Язык (ru/en) — прокидывается стейджем. */
  @property() public uiLang: Lang = "ru";

  @state() private _provider: Provider = "pending";
  private _webrtcEl?: HTMLElement & { setConfig: (c: unknown) => void; hass?: unknown };

  public override connectedCallback(): void {
    super.connectedCallback();
    void this._resolveProvider();
  }

  private async _resolveProvider(): Promise<void> {
    if (customElements.get("ha-camera-stream")) {
      this._provider = "ha";
      return;
    }
    // Подгрузить HA card helpers — тянет hui-image → ha-camera-stream.
    try {
      await (window as unknown as { loadCardHelpers?: () => Promise<unknown> }).loadCardHelpers?.();
    } catch {
      /* ignore */
    }
    if (customElements.get("ha-camera-stream")) {
      this._provider = "ha";
    } else if (customElements.get("webrtc-camera")) {
      this._provider = "webrtc"; // fallback: у пользователя уже стоит AlexxIT/WebRTC
    } else {
      this._provider = "none";
    }
  }

  protected override updated(changed: PropertyValues): void {
    if (this._provider === "webrtc") this._syncWebrtc(changed);
  }

  private _syncWebrtc(changed: PropertyValues): void {
    const host = this.renderRoot.querySelector("#webrtc-host");
    if (!host || !this.entity || !this.hass) return;
    if (changed.has("entity") || changed.has("_provider") || changed.has("muted") || !this._webrtcEl) {
      host.replaceChildren();
      const el = document.createElement("webrtc-camera") as HTMLElement & {
        setConfig: (c: unknown) => void;
        hass?: unknown;
      };
      el.setConfig({ entity: this.entity, muted: this.muted });
      el.hass = this.hass;
      host.appendChild(el);
      this._webrtcEl = el;
    } else {
      this._webrtcEl.hass = this.hass;
    }
  }

  protected override render(): TemplateResult {
    const s = t(this.uiLang).video;
    if (!this.entity || !this.hass) {
      return this._frame("video-off", s.noVideo);
    }
    const stateObj = this.hass.states[this.entity];
    if (!stateObj) {
      return this._frame("video-off", s.cameraUnavailable);
    }
    switch (this._provider) {
      case "pending":
        return this._frame("video-off", s.loading);
      case "ha":
        // Без controls: chromeless-поверхность — весь UI наш (LIVE/чип/CTA/tap-to-unmute
        // в call-stage). controls в Chrome/FF = клик по видео → пауза живого звонка +
        // дубль нативной панели. См. call-card-ux-production.md §13.1.
        return html`
          <ha-camera-stream
            .hass=${this.hass}
            .stateObj=${stateObj}
            .muted=${this.muted}
          ></ha-camera-stream>
        `;
      case "webrtc":
        return html`<div id="webrtc-host"></div>`;
      default:
        return this._frame("video-off", s.playerUnavailable);
    }
  }

  private _frame(icon: string, text: string): TemplateResult {
    return html`
      <div class="frame" role="img" aria-label=${text}>
        <eg-icon name=${icon}></eg-icon>
        <span>${text}</span>
      </div>
      ${nothing}
    `;
  }

  static override styles = css`
    :host {
      display: block;
      width: 100%;
      height: 100%;
    }
    ha-camera-stream,
    #webrtc-host {
      display: block;
      width: 100%;
      height: 100%;
    }
    /* реальный плеер заполняет область (object-fit самого видео — по потоку) */
    .frame {
      width: 100%;
      height: 100%;
      background: var(--secondary-background-color);
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      gap: 6px;
      color: var(--secondary-text-color);
      text-align: center;
      padding: 8px;
      box-sizing: border-box;
    }
    .frame eg-icon {
      --eg-icon-size: 40px;
    }
    .frame span {
      font-size: 0.85rem;
    }
  `;
}
