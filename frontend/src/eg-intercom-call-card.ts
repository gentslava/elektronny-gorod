// eg-intercom-call-card — экран входящего вызова и разговора с домофоном «Электронный
// город» (Lit+TS). Облик нативный HA (theme-токены, mdi, M3-кнопки). Состояние ведётся
// по sensor.*_call_state (Slice 3a). Композиция: <eg-call-video> (видео+звук гостя),
// <eg-open-control> (адаптивное открытие), MicController (микрофон). См. call-card-ux-spec.md.
import { LitElement, css, html, nothing, type PropertyValues, type TemplateResult } from "lit";
import { customElement, property, state } from "lit/decorators.js";

import { type CallPhase, type CallView, deriveView, toPhase } from "./state-machine.js";
import { pickCameraEntity } from "./components/call-video.js";
import "./components/open-control.js";
import { MicController, type MicPermission, shouldAutoStartMic } from "./components/mic-controller.js";
import { isCoarsePointer, type OpenAction, resolveOpenAction } from "./util/open-action.js";

interface HassLike {
  states: Record<string, { state: string; attributes: Record<string, unknown> }>;
  connection?: unknown;
  callService: (domain: string, service: string, data?: Record<string, unknown>) => Promise<unknown>;
}

interface CardConfig {
  call_state?: string;
  camera?: string;
  doorbell_camera?: string;
  lock?: string;
  name?: string;
  open_action?: string;
  mic?: boolean;
  mic_autostart?: boolean;
  timer?: "auto" | "stopwatch" | "off";
}

type OpenStatus = "idle" | "opening" | "opened" | "error";

const STATUS_RU: Partial<Record<CallPhase, string>> = {
  ringing: "Входящий вызов",
  connecting: "Соединение…",
  active: "Разговор",
  ended: "Вызов завершён",
  error: "Ошибка вызова",
};

const DISMISS_MS = 5000;
const OPEN_RESET_MS = 3000;

@customElement("eg-intercom-call-card")
export class EgIntercomCallCard extends LitElement {
  @property({ attribute: false }) public hass?: HassLike;

  @state() private _config: CardConfig = {};
  @state() private _muted = false;
  @state() private _micActive = false;
  @state() private _micPerm: MicPermission = "unknown";
  @state() private _openStatus: OpenStatus = "idle";
  @state() private _now = Date.now();
  @state() private _dismissed = false;

  private _openAction: OpenAction = "hold";
  private _prevPhase: CallPhase = "idle";
  private _tick?: number;
  private _errHide?: number;
  private _openReset?: number;
  private readonly _mic = new MicController(
    () => this.hass?.connection as never,
    () => {
      this._micActive = this._mic.active;
      this.requestUpdate();
    },
  );

  public setConfig(config: CardConfig): void {
    if (!config || !config.call_state) {
      throw new Error("eg-intercom-call-card: укажите 'call_state' (sensor.*_call_state)");
    }
    this._config = config;
    this._openAction = resolveOpenAction(config.open_action, isCoarsePointer());
  }

  public getCardSize(): number {
    return 8;
  }

  public static getStubConfig(): CardConfig {
    return { call_state: "", camera: "", doorbell_camera: "", lock: "" };
  }

  public override disconnectedCallback(): void {
    super.disconnectedCallback();
    this._mic.stop();
    this._stopTick();
    if (this._errHide) clearTimeout(this._errHide);
    if (this._openReset) clearTimeout(this._openReset);
  }

  private get _phase(): CallPhase {
    const eid = this._config.call_state;
    const st = eid && this.hass ? this.hass.states[eid]?.state : undefined;
    return toPhase(st);
  }

  private get _intercomName(): string {
    const eid = this._config.call_state;
    const attrs = eid && this.hass ? this.hass.states[eid]?.attributes : undefined;
    const fromAttr = attrs?.["intercom_name"];
    return this._config.name ?? (typeof fromAttr === "string" ? fromAttr : "Домофон");
  }

  private get _startedAtMs(): number | undefined {
    const eid = this._config.call_state;
    const v = eid && this.hass ? this.hass.states[eid]?.attributes?.["started_at"] : undefined;
    if (typeof v !== "string") return undefined;
    const t = Date.parse(v);
    return Number.isNaN(t) ? undefined : t;
  }

  protected override willUpdate(changed: PropertyValues): void {
    if (!changed.has("hass")) return;
    const phase = this._phase;
    if (phase !== this._prevPhase) {
      this._onPhase(phase);
      this._prevPhase = phase;
    }
  }

  private _onPhase(phase: CallPhase): void {
    if (phase === "ringing" || phase === "connecting" || phase === "active") {
      this._dismissed = false;
    }
    if (phase === "active") {
      void this._enterActive();
    } else {
      this._exitActive();
    }
    if (phase === "error" || phase === "ended") {
      this._scheduleDismiss();
    }
    if (phase === "ringing" || phase === "idle") {
      this._openStatus = "idle";
    }
  }

  private async _enterActive(): Promise<void> {
    this._muted = false; // пытаемся со звуком; снять блок автоплея — кнопкой звука (жест)
    this._startTick();
    this._micPerm = await this._mic.queryPermission();
    if (this._config.mic_autostart !== false && shouldAutoStartMic(this._micPerm, this._mic.secure)) {
      await this._mic.start();
    }
  }

  private _exitActive(): void {
    this._mic.stop();
    this._stopTick();
  }

  private _startTick(): void {
    this._stopTick();
    this._now = Date.now();
    this._tick = window.setInterval(() => {
      this._now = Date.now();
    }, 1000);
  }

  private _stopTick(): void {
    if (this._tick) {
      clearInterval(this._tick);
      this._tick = undefined;
    }
  }

  private _scheduleDismiss(): void {
    if (this._errHide) clearTimeout(this._errHide);
    this._errHide = window.setTimeout(() => {
      this._dismissed = true;
      this.requestUpdate();
    }, DISMISS_MS);
  }

  // ---- действия ----
  private _answer = (): void => {
    void this.hass?.callService("elektronny_gorod", "answer");
  };

  private _hangup = (): void => {
    void this.hass?.callService("elektronny_gorod", "hangup");
  };

  private _toggleMute = (): void => {
    this._muted = !this._muted;
  };

  private _toggleMic = async (): Promise<void> => {
    if (this._mic.active) {
      this._mic.stop();
    } else {
      await this._mic.start();
    }
    this._micPerm = await this._mic.queryPermission();
  };

  private _open = async (): Promise<void> => {
    if (!this._config.lock || !this.hass) return;
    this._openStatus = "opening";
    try {
      await this.hass.callService("lock", "unlock", { entity_id: this._config.lock });
      this._openStatus = "opened";
    } catch {
      this._openStatus = "error";
    }
    if (this._openReset) clearTimeout(this._openReset);
    this._openReset = window.setTimeout(() => {
      this._openStatus = "idle";
      this.requestUpdate();
    }, OPEN_RESET_MS);
  };

  private _timerText(): string {
    const start = this._startedAtMs;
    if (start === undefined) return "";
    const sec = Math.max(0, Math.floor((this._now - start) / 1000));
    const mm = String(Math.floor(sec / 60)).padStart(2, "0");
    const ss = String(sec % 60).padStart(2, "0");
    return `${mm}:${ss}`;
  }

  protected override render(): TemplateResult | typeof nothing {
    const phase = this._phase;
    const view = deriveView(phase);
    if (!view.visible || this._dismissed) return nothing;

    const cam = pickCameraEntity(view.video, this._config);
    const showTimer = view.showTimer && this._config.timer !== "off";

    return html`
      <ha-card class="phase-${phase}">
        <header>
          <span class="name" title=${this._intercomName}>${this._intercomName}</span>
          <span class="status ${view.isError ? "err" : ""}">
            ${view.busy ? html`<span class="dot" aria-hidden="true"></span>` : nothing}
            <span>${STATUS_RU[phase] ?? ""}</span>
            ${showTimer ? html`<span class="timer">${this._timerText()}</span>` : nothing}
          </span>
        </header>

        <div class="stage">
          ${cam
            ? html`<eg-call-video .hass=${this.hass} .entity=${cam} .muted=${this._muted}></eg-call-video>`
            : view.isError
              ? html`<div class="frame err"><ha-icon icon="mdi:phone-alert"></ha-icon><span>Не удалось установить вызов</span></div>`
              : nothing}
          ${view.busy
            ? html`<div class="connecting" aria-hidden="true"><div class="spinner"></div></div>`
            : nothing}
        </div>

        ${view.showOpen ? this._renderOpen() : nothing}
        ${this._renderActions(view)}
      </ha-card>
    `;
  }

  private _renderOpen(): TemplateResult {
    return html`
      <eg-open-control
        .mode=${this._openAction}
        .status=${this._openStatus}
        ?disabled=${!this._config.lock}
        @open=${this._open}
      ></eg-open-control>
    `;
  }

  private _renderActions(view: CallView): TemplateResult {
    if (view.showAccept || (view.showReject && !view.showHangup)) {
      // ringing / connecting
      return html`
        <div class="actions">
          ${view.showReject
            ? html`<button class="circle reject" @click=${this._hangup}>
                  <ha-icon icon="mdi:phone-hangup"></ha-icon><small>Отклонить</small>
                </button>`
            : nothing}
          ${view.showAccept
            ? html`<button class="circle accept" @click=${this._answer}>
                  <ha-icon icon="mdi:phone"></ha-icon><small>Принять</small>
                </button>`
            : nothing}
        </div>
      `;
    }
    if (view.showHangup) {
      // active / error
      return html`
        <div class="actions">
          ${view.showMic && this._config.mic !== false ? this._renderMic() : nothing}
          ${view.showMic
            ? html`<button class="circle" @click=${this._toggleMute}
                    aria-label=${this._muted ? "Включить звук" : "Выключить звук"}>
                  <ha-icon icon=${this._muted ? "mdi:volume-off" : "mdi:volume-high"}></ha-icon>
                  <small>${this._muted ? "Звук" : "Динамик"}</small>
                </button>`
            : nothing}
          <button class="circle reject" @click=${this._hangup} aria-label="Завершить">
            <ha-icon icon="mdi:phone-hangup"></ha-icon><small>Завершить</small>
          </button>
        </div>
      `;
    }
    return html`<div class="actions"></div>`;
  }

  private _renderMic(): TemplateResult {
    if (!this._mic.secure) {
      return html`<button class="circle" disabled aria-label="Микрофон требует HTTPS" title="Микрофон доступен только по HTTPS">
        <ha-icon icon="mdi:microphone-off"></ha-icon><small>Нет HTTPS</small>
      </button>`;
    }
    if (this._micPerm === "denied") {
      return html`<button class="circle" disabled aria-label="Доступ к микрофону запрещён" title="Разрешите микрофон в настройках браузера">
        <ha-icon icon="mdi:microphone-off"></ha-icon><small>Запрещён</small>
      </button>`;
    }
    if (this._micActive) {
      return html`<button class="circle mic-on" @click=${this._toggleMic} aria-label="Выключить микрофон">
        <ha-icon icon="mdi:microphone"></ha-icon><small>Микрофон</small>
      </button>`;
    }
    if (this._micPerm !== "granted") {
      return html`<button class="circle" @click=${this._toggleMic} aria-label="Разрешить микрофон">
        <ha-icon icon="mdi:microphone-question"></ha-icon><small>Разрешить</small>
      </button>`;
    }
    return html`<button class="circle" @click=${this._toggleMic} aria-label="Включить микрофон">
      <ha-icon icon="mdi:microphone-off"></ha-icon><small>Микрофон</small>
    </button>`;
  }

  static override styles = css`
    :host {
      display: block;
    }
    ha-card {
      padding: 14px;
      display: flex;
      flex-direction: column;
      gap: 14px;
    }
    header {
      display: flex;
      align-items: baseline;
      justify-content: space-between;
      gap: 10px;
    }
    .name {
      font-size: 1.15rem;
      font-weight: 600;
      color: var(--primary-text-color);
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .status {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      font-size: 0.9rem;
      color: var(--secondary-text-color);
      flex-shrink: 0;
    }
    .status.err {
      color: var(--error-color);
    }
    .timer {
      font-variant-numeric: tabular-nums;
      font-weight: 600;
      color: var(--primary-text-color);
    }
    .dot {
      width: 9px;
      height: 9px;
      border-radius: 50%;
      background: var(--primary-color);
      animation: pulse 1s ease-in-out infinite;
    }
    @keyframes pulse {
      50% {
        opacity: 0.3;
      }
    }
    .stage {
      position: relative;
    }
    .connecting {
      position: absolute;
      inset: 0;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      gap: 10px;
      background: rgba(0, 0, 0, 0.45);
      border-radius: 12px;
      color: #fff;
      font-weight: 600;
    }
    .spinner {
      width: 44px;
      height: 44px;
      border-radius: 50%;
      border: 4px solid rgba(255, 255, 255, 0.3);
      border-top-color: #fff;
      animation: spin 0.9s linear infinite;
    }
    @keyframes spin {
      to {
        transform: rotate(360deg);
      }
    }
    @media (prefers-reduced-motion: reduce) {
      .spinner {
        animation: none;
      }
    }
    .frame {
      aspect-ratio: 16 / 9;
      background: var(--secondary-background-color);
      border-radius: 12px;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      gap: 6px;
      color: var(--secondary-text-color);
    }
    .frame.err {
      color: var(--error-color);
    }
    .frame ha-icon {
      --mdc-icon-size: 40px;
    }
    .actions {
      display: flex;
      gap: 16px;
      justify-content: center;
      flex-wrap: wrap;
    }
    .circle {
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 4px;
      border: none;
      background: none;
      cursor: pointer;
      color: var(--primary-text-color);
      font: inherit;
      min-width: 64px;
    }
    .circle ha-icon {
      --mdc-icon-size: 28px;
      width: 56px;
      height: 56px;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      background: var(--secondary-background-color);
      color: var(--primary-text-color);
    }
    .circle small {
      font-size: 0.78rem;
      color: var(--secondary-text-color);
    }
    .circle[disabled] {
      cursor: not-allowed;
      opacity: 0.5;
    }
    .circle.accept ha-icon {
      background: var(--success-color, #2e7d32);
      color: #fff;
    }
    .circle.reject ha-icon {
      background: var(--error-color, #c62828);
      color: #fff;
    }
    .circle.mic-on ha-icon {
      background: var(--primary-color);
      color: var(--text-primary-color, #fff);
    }
    @media (prefers-reduced-motion: reduce) {
      .dot {
        animation: none;
      }
    }
  `;
}

declare global {
  interface Window {
    customCards?: Array<{ type: string; name: string; description: string; preview?: boolean }>;
  }
}

window.customCards = window.customCards || [];
window.customCards.push({
  type: "eg-intercom-call-card",
  name: "ЭГ Домофон — Экран вызова",
  description:
    "Входящий вызов и разговор с домофоном: видео+звук, открыть дверь, принять/завершить, микрофон.",
  preview: false,
});
