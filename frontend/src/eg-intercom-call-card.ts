// eg-intercom-call-card — экран входящего вызова и разговора с домофоном «Электронный
// город» (Lit+TS). Одна карточка на ВСЕ домофоны: показывает активный вызов (любой из
// списка) или единую заглушку «Нет вызова» в простое. Облик нативный HA (theme-токены,
// mdi, M3, a11y). Состояние — по sensor.*_call_state (Slice 3a). См. call-card-ux-spec.md.
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

interface DoorbellCfg {
  call_state: string;
  doorbell_camera?: string;
  lock?: string;
  name?: string;
}

interface CardConfig {
  /** Камера активного вызова (видео+звук гостя), общая для всех домофонов. */
  camera?: string;
  /** Список домофонов; карточка показывает активный вызов любого из них. */
  doorbells?: DoorbellCfg[];
  // legacy: один домофон через поля верхнего уровня
  call_state?: string;
  doorbell_camera?: string;
  lock?: string;
  name?: string;
  open_action?: string;
  mic?: boolean;
  mic_autostart?: boolean;
  timer?: "auto" | "stopwatch" | "off";
  idle_text?: string;
}

type OpenStatus = "idle" | "opening" | "opened" | "error";

const STATUS_RU: Partial<Record<CallPhase, string>> = {
  ringing: "Входящий вызов",
  connecting: "Соединение…",
  active: "Разговор",
  ended: "Вызов завершён",
  error: "Ошибка вызова",
};

/** Фазы, при которых вызов «активен» и карточка показывает экран (не idle). */
const LIVE_PHASES: ReadonlySet<CallPhase> = new Set(["ringing", "connecting", "active", "error"]);

const DISMISS_MS = 6000;
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
  /** call_state-сущности, чей error уже «погашен» по таймеру (показываем idle). */
  @state() private _errDismissed = new Set<string>();

  private _doorbells: DoorbellCfg[] = [];
  private _openAction: OpenAction = "hold";
  private _prevKey = ""; // "<call_state>|<phase>" активного домофона — для детекта переходов
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
    const list = config?.doorbells
      ?? (config?.call_state
        ? [{ call_state: config.call_state, doorbell_camera: config.doorbell_camera, lock: config.lock, name: config.name }]
        : []);
    if (!list.length || list.some((d) => !d.call_state)) {
      throw new Error("eg-intercom-call-card: укажите 'doorbells' (с call_state) или 'call_state'");
    }
    this._config = config;
    this._doorbells = list;
    this._openAction = resolveOpenAction(config.open_action, isCoarsePointer());
  }

  public getCardSize(): number {
    return 8;
  }

  public static getStubConfig(): CardConfig {
    return { camera: "", doorbells: [{ call_state: "", doorbell_camera: "", lock: "" }] };
  }

  public override disconnectedCallback(): void {
    super.disconnectedCallback();
    this._mic.stop();
    this._stopTick();
    if (this._errHide) clearTimeout(this._errHide);
    if (this._openReset) clearTimeout(this._openReset);
  }

  private _phaseOf(d: DoorbellCfg): CallPhase {
    const st = this.hass?.states[d.call_state]?.state;
    return toPhase(st);
  }

  /** Активный домофон: первый с «живой» фазой (не погашенной error'ом). */
  private get _active(): DoorbellCfg | undefined {
    return this._doorbells.find(
      (d) => LIVE_PHASES.has(this._phaseOf(d)) && !this._errDismissed.has(d.call_state),
    );
  }

  private get _phase(): CallPhase {
    const a = this._active;
    return a ? this._phaseOf(a) : "idle";
  }

  private get _intercomName(): string {
    const a = this._active;
    // Заголовок = полный адрес домофона (как в оригинальном приложении):
    // берём intercom_name из атрибута сенсора, схлопывая двойные пробелы.
    const attrs = a ? this.hass?.states[a.call_state]?.attributes : undefined;
    const fromAttr = attrs?.["intercom_name"];
    const full = typeof fromAttr === "string" ? fromAttr.replace(/\s+/g, " ").trim() : "";
    return full || a?.name || this._config.name || "Домофон";
  }

  private get _startedAtMs(): number | undefined {
    const a = this._active;
    const v = a ? this.hass?.states[a.call_state]?.attributes?.["started_at"] : undefined;
    if (typeof v !== "string") return undefined;
    const t = Date.parse(v);
    return Number.isNaN(t) ? undefined : t;
  }

  protected override willUpdate(changed: PropertyValues): void {
    if (!changed.has("hass")) return;
    // снять «погашенный error» с домофонов, которые уже вышли из error
    for (const d of this._doorbells) {
      if (this._errDismissed.has(d.call_state) && this._phaseOf(d) !== "error") {
        this._errDismissed.delete(d.call_state);
      }
    }
    const a = this._active;
    const key = a ? `${a.call_state}|${this._phaseOf(a)}` : "idle";
    if (key !== this._prevKey) {
      this._onPhase(this._phase, a);
      this._prevKey = key;
    }
  }

  private _onPhase(phase: CallPhase, active: DoorbellCfg | undefined): void {
    if (phase === "active") {
      void this._enterActive();
    } else {
      this._exitActive();
    }
    if (phase === "error" && active) {
      this._scheduleErrDismiss(active.call_state);
    }
    if (phase === "idle" || phase === "ringing") {
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

  private _scheduleErrDismiss(entity: string): void {
    if (this._errHide) clearTimeout(this._errHide);
    this._errHide = window.setTimeout(() => {
      this._errDismissed = new Set(this._errDismissed).add(entity);
      this.requestUpdate();
    }, DISMISS_MS);
  }

  // ---- действия (answer/hangup — глобальные сервисы; контроллер резолвит активный вызов) ----
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
    const lock = this._active?.lock;
    if (!lock || !this.hass) return;
    this._openStatus = "opening";
    try {
      await this.hass.callService("lock", "unlock", { entity_id: lock });
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

  protected override render(): TemplateResult {
    const active = this._active;
    if (!active) return this._renderIdle();

    const phase = this._phase;
    const view = deriveView(phase);
    const cam = pickCameraEntity(view.video, {
      camera: this._config.camera,
      doorbell_camera: active.doorbell_camera,
    });
    const showTimer = view.showTimer && this._config.timer !== "off";

    return html`
      <ha-card class="phase-${phase}">
        <div class="media">
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
        </div>

        <div class="controls">
          <div class="open-area">
            ${view.showOpen ? this._renderOpen() : nothing}
          </div>
          ${this._renderActions(view)}
        </div>
      </ha-card>
    `;
  }

  private _doorbellNames(): string[] {
    return this._doorbells
      .map((d) => {
        const attr = this.hass?.states[d.call_state]?.attributes?.["intercom_name"];
        return d.name ?? (typeof attr === "string" ? attr : "");
      })
      .filter(Boolean);
  }

  private _renderIdle(): TemplateResult {
    const names = this._doorbellNames();
    return html`
      <ha-card class="idle">
        <div class="idle-stage" role="status">
          <ha-icon icon="mdi:doorbell-video"></ha-icon>
          <div class="idle-title">${this._config.idle_text ?? "Нет активного вызова"}</div>
          <div class="idle-sub">Экран покажет видео, звук и кнопки при звонке домофона</div>
          ${names.length
            ? html`<div class="idle-chips">
                ${names.map(
                  (n) => html`<span class="chip"><ha-icon icon="mdi:check-circle"></ha-icon>${n}</span>`,
                )}
              </div>`
            : nothing}
        </div>
      </ha-card>
    `;
  }

  private _renderOpen(): TemplateResult {
    return html`
      <eg-open-control
        .mode=${this._openAction}
        .status=${this._openStatus}
        ?disabled=${!this._active?.lock}
        @open=${this._open}
      ></eg-open-control>
    `;
  }

  private _renderActions(view: CallView): TemplateResult {
    if (view.showAccept || (view.showReject && !view.showHangup)) {
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
      height: 100%;
      /* адаптив по собственной ширине карточки (телефон / планшет-ландшафт / десктоп) */
      container-type: inline-size;
    }
    ha-card {
      height: 100%;
      box-sizing: border-box;
      /* щедрые отступы от краёв экрана + безопасные зоны */
      padding: max(20px, env(safe-area-inset-top))
        max(20px, env(safe-area-inset-right))
        max(20px, env(safe-area-inset-bottom))
        max(20px, env(safe-area-inset-left));
      display: flex;
      flex-direction: column;
      /* телефон: равномерные промежутки вокруг видео; на низком экране схлопываются */
      justify-content: space-evenly;
      gap: 12px;
    }
    .media {
      display: flex;
      flex-direction: column;
      gap: 12px;
      flex: none; /* видео фиксированной высоты (16:9 по ширине), не пляшет */
    }
    .stage {
      position: relative;
      /* видео всегда полная ширина и 16:9 (не «окошко», не ужимается по высоте) */
      width: 100%;
      aspect-ratio: 16 / 9;
      border-radius: 12px;
      overflow: hidden;
      background: var(--secondary-background-color);
    }
    .stage > eg-call-video {
      position: absolute;
      inset: 0;
    }
    /* телефон: open и actions — прямые flex-элементы карточки (равномерно вокруг видео) */
    .controls {
      display: contents;
    }
    .open-area {
      display: flex;
      justify-content: center;
      flex: none;
    }
    .open-area eg-open-control {
      width: 100%;
    }
    /* idle-заглушка «Нет активного вызова» — «призрак» экрана вызова */
    ha-card.idle {
      align-items: stretch;
      justify-content: center;
    }
    .idle-stage {
      width: 100%;
      aspect-ratio: 16 / 9;
      border-radius: 12px;
      background: var(--secondary-background-color);
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      gap: 6px;
      text-align: center;
      padding: 14px;
      box-sizing: border-box;
      color: var(--secondary-text-color);
    }
    .idle-stage ha-icon {
      --mdc-icon-size: 52px;
      color: var(--primary-color);
      opacity: 0.75;
    }
    .idle-title {
      font-size: 1.3rem;
      font-weight: 700;
      color: var(--primary-text-color);
    }
    .idle-sub {
      font-size: 0.95rem;
      max-width: 34ch;
    }
    .idle-chips {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      justify-content: center;
      margin-top: 8px;
    }
    .chip {
      display: inline-flex;
      align-items: center;
      gap: 5px;
      padding: 5px 12px 5px 8px;
      border-radius: 999px;
      background: var(--card-background-color, var(--ha-card-background));
      color: var(--primary-text-color);
      font-size: 0.8rem;
      font-weight: 600;
      box-shadow: 0 1px 3px rgba(0, 0, 0, 0.25);
    }
    .chip ha-icon {
      --mdc-icon-size: 16px;
      color: var(--success-color, #4caf50);
      opacity: 1;
    }
    /* широкий контейнер — планшет-ландшафт / десктоп: 2 колонки */
    @container (min-width: 640px) {
      ha-card {
        flex-direction: row;
        align-items: center;
        justify-content: flex-start;
        gap: 18px;
      }
      ha-card.idle {
        flex-direction: column;
        justify-content: center;
        align-items: center;
      }
      ha-card.idle .idle-stage {
        max-width: 760px;
        gap: 10px;
        padding: 28px;
      }
      ha-card.idle .idle-stage ha-icon {
        --mdc-icon-size: 80px;
      }
      ha-card.idle .idle-title {
        font-size: 1.7rem;
      }
      ha-card.idle .idle-sub {
        font-size: 1.1rem;
      }
      ha-card.idle .idle-chips {
        gap: 10px;
        margin-top: 14px;
      }
      ha-card.idle .chip {
        font-size: 0.95rem;
        padding: 7px 16px 7px 11px;
      }
      ha-card.idle .chip ha-icon {
        --mdc-icon-size: 18px;
      }
      .media {
        flex: 1.6 1 0;
      }
      .controls {
        display: flex;
        flex-direction: column;
        gap: 14px;
        flex: 1 1 0;
        max-width: 380px;
      }
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
      .spinner,
      .dot {
        animation: none;
      }
    }
    .frame {
      position: absolute;
      inset: 0;
      background: var(--secondary-background-color);
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
    "Входящий вызов и разговор с домофоном: видео+звук, открыть дверь, принять/завершить, микрофон. Одна карта на все домофоны.",
  preview: false,
});
