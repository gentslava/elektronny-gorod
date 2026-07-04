// eg-intercom-call-card — экран входящего вызова и разговора с домофоном «Электронный
// город» (Lit+TS). Одна карточка на ВСЕ домофоны: показывает активный вызов (любой из
// списка) или единую заглушку «Нет вызова» в простое. Облик нативный HA (theme-токены,
// mdi, M3, a11y). Состояние — по sensor.*_call_state. Вёрстка — по production-макетам
// (pencil/design.pen), см. call-card-ux-production.md + plan-call-card-reverstka.md.
import { LitElement, css, html, nothing, type PropertyValues, type TemplateResult } from "lit";
import { customElement, property, state } from "lit/decorators.js";

import { type CallPhase, type CallView, deriveView, toPhase } from "./state-machine.js";
import { pickCameraEntity } from "./components/call-video.js";
import "./components/open-control.js";
import { MicController, type MicPermission, shouldAutoStartMic } from "./components/mic-controller.js";
import { isCoarsePointer, type OpenAction, resolveOpenAction } from "./util/open-action.js";
import { egTokens, statusColor } from "./theme/tokens.js";

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
  address?: string;
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
  address?: string;
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
/** Окно ответа на входящий (домофон отменяет вызов ~через 30с). Domain-timing — локально. */
const ANSWER_WINDOW_MS = 30000;

@customElement("eg-intercom-call-card")
export class EgIntercomCallCard extends LitElement {
  @property({ attribute: false }) public hass?: HassLike;

  @state() private _config: CardConfig = {};
  @state() private _muted = false;
  @state() private _micActive = false;
  @state() private _micPerm: MicPermission = "unknown";
  @state() private _openStatus: OpenStatus = "idle";
  @state() private _now = Date.now();
  /** Момент начала звонка (для окна ответа на ringing). */
  @state() private _ringingSince = 0;
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
        ? [{ call_state: config.call_state, doorbell_camera: config.doorbell_camera, lock: config.lock, name: config.name, address: config.address }]
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

  /** Имя домофона (короткое): config name → атрибут intercom_name → дефолт. */
  private get _intercomName(): string {
    const a = this._active;
    if (a?.name) return a.name;
    const attrs = a ? this.hass?.states[a.call_state]?.attributes : undefined;
    const fromAttr = attrs?.["intercom_name"];
    const full = typeof fromAttr === "string" ? fromAttr.replace(/\s+/g, " ").trim() : "";
    return full || this._config.name || "Домофон";
  }

  /** Адрес (вторая строка шапки) — из конфига домофона/карты; иначе скрыт. */
  private get _address(): string {
    return this._active?.address ?? this._config.address ?? "";
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
    } else if (phase === "ringing") {
      this._ringingSince = Date.now();
      this._startTick(); // тикаем для отсчёта окна ответа
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

  /** Свернуть карточку (звонок продолжается на фоне) — «✕» в шапке. */
  private _dismiss = (): void => {
    this.dispatchEvent(new CustomEvent("eg-dismiss", { bubbles: true, composed: true }));
  };

  private _timerText(): string {
    const start = this._startedAtMs;
    if (start === undefined) return "";
    const sec = Math.max(0, Math.floor((this._now - start) / 1000));
    return this._mmss(sec);
  }

  private _mmss(sec: number): string {
    const mm = String(Math.floor(sec / 60)).padStart(2, "0");
    const ss = String(sec % 60).padStart(2, "0");
    return `${mm}:${ss}`;
  }

  /** Окно ответа на входящий: сколько осталось и доля [0..1] для полосы.
   *  Формат countdown — m:ss (минуты без ведущего нуля, как в макете «0:24»). */
  private _answerWindow(): { text: string; fraction: number } {
    if (!this._ringingSince) return { text: "", fraction: 0 };
    const remaining = Math.max(0, ANSWER_WINDOW_MS - (this._now - this._ringingSince));
    const sec = Math.ceil(remaining / 1000);
    const text = `${Math.floor(sec / 60)}:${String(sec % 60).padStart(2, "0")}`;
    return { text, fraction: remaining / ANSWER_WINDOW_MS };
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

    return html`
      <ha-card class="phase-${phase}">
        <div class="content">
          ${this._renderHeader()}
          ${this._renderStatus(view, phase)}
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
          <div class="open-area">
            ${view.showOpen ? this._renderOpen() : nothing}
          </div>
          ${this._renderActions(view)}
        </div>
      </ha-card>
    `;
  }

  private _renderHeader(): TemplateResult {
    const addr = this._address;
    return html`
      <header>
        <div class="hgroup">
          <span class="name" title=${this._intercomName}>${this._intercomName}</span>
          ${addr ? html`<span class="addr">${addr}</span>` : nothing}
        </div>
        <button class="close" @click=${this._dismiss} aria-label="Свернуть">
          <ha-icon icon="mdi:close"></ha-icon>
        </button>
      </header>
    `;
  }

  private _renderStatus(view: CallView, phase: CallPhase): TemplateResult {
    const showTimer = view.showTimer && this._config.timer !== "off";
    const win = phase === "ringing" ? this._answerWindow() : null;
    return html`
      <div class="statusrow">
        <div class="strow">
          <span class="badge" style="--badge:${statusColor(phase)}">
            <span class="dot" aria-hidden="true"></span>
            <span>${STATUS_RU[phase] ?? ""}</span>
          </span>
          ${win
            ? html`<span class="countdown"><ha-icon icon="mdi:timer-outline"></ha-icon>${win.text}</span>`
            : showTimer
              ? html`<span class="timer">${this._timerText()}</span>`
              : nothing}
        </div>
        ${win
          ? html`<div class="window"><div class="fill" style="width:${win.fraction * 100}%"></div></div>`
          : nothing}
      </div>
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

  static override styles = [
    egTokens,
    css`
      :host {
        display: block;
        height: 100%;
        /* адаптив по собственной ширине карточки (телефон / планшет / десктоп / панель) */
        container-type: inline-size;
      }
      ha-card {
        height: 100%;
        box-sizing: border-box;
        background: var(--eg-card);
        border-radius: var(--eg-r-card);
      }
      .content {
        display: flex;
        flex-direction: column;
        gap: 20px;
        padding: 6px 16px 28px;
        box-sizing: border-box;
      }
      /* ---- шапка: имя + адрес + свернуть ---- */
      header {
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        gap: 12px;
      }
      .hgroup {
        display: flex;
        flex-direction: column;
        gap: 3px;
        min-width: 0;
      }
      .name {
        font-size: 22px;
        font-weight: 700;
        line-height: 1.15;
        color: var(--eg-text);
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
      .addr {
        font-size: 13px;
        color: var(--eg-text-2);
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
      .close {
        flex: none;
        width: 44px;
        height: 44px;
        border: none;
        border-radius: var(--eg-r-full);
        background: var(--eg-elevated);
        color: var(--eg-text-2);
        display: flex;
        align-items: center;
        justify-content: center;
        cursor: pointer;
      }
      .close ha-icon {
        --mdc-icon-size: 20px;
      }
      /* ---- статус-строка: бейдж + таймер/countdown + окно ответа ---- */
      .statusrow {
        display: flex;
        flex-direction: column;
        gap: 8px;
      }
      .strow {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 10px;
      }
      .badge {
        display: inline-flex;
        align-items: center;
        gap: 7px;
        padding: 5px 12px;
        border-radius: var(--eg-r-full);
        font-size: 13px;
        font-weight: 600;
        color: var(--badge, var(--eg-text-2));
        background: color-mix(in srgb, var(--badge, var(--eg-text-2)) 18%, transparent);
      }
      .badge .dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background: var(--badge, var(--eg-text-2));
      }
      .countdown {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        font-size: 15px;
        color: var(--eg-text-2);
      }
      .countdown ha-icon {
        --mdc-icon-size: 15px;
      }
      .timer {
        font-family: var(--eg-mono);
        font-size: 17px;
        font-weight: 600;
        color: var(--eg-text);
        font-variant-numeric: tabular-nums;
      }
      .window {
        width: 100%;
        height: 4px;
        border-radius: var(--eg-r-full);
        background: var(--eg-elevated);
        overflow: hidden;
      }
      .window .fill {
        height: 100%;
        border-radius: var(--eg-r-full);
        background: var(--eg-warning);
        transition: width 1s linear;
      }
      /* ---- видео-стейдж ---- */
      .stage {
        position: relative;
        width: 100%;
        aspect-ratio: 16 / 9;
        border-radius: var(--eg-r-md);
        overflow: hidden;
        background: var(--eg-elevated);
      }
      .stage > eg-call-video {
        position: absolute;
        inset: 0;
      }
      .connecting {
        position: absolute;
        inset: 0;
        display: flex;
        align-items: center;
        justify-content: center;
        background: var(--eg-scrim);
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
        position: absolute;
        inset: 0;
        background: var(--eg-elevated);
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: 6px;
        color: var(--eg-text-2);
      }
      .frame.err {
        color: var(--eg-error);
      }
      .frame ha-icon {
        --mdc-icon-size: 40px;
      }
      /* ---- зона «Открыть» ---- */
      .open-area {
        display: flex;
        justify-content: center;
      }
      .open-area eg-open-control {
        width: 100%;
      }
      /* ---- ряд действий (кнопки заменяются в Slice 1–2) ---- */
      .actions {
        display: flex;
        gap: 28px;
        justify-content: center;
        flex-wrap: wrap;
      }
      .circle {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 6px;
        border: none;
        background: none;
        cursor: pointer;
        color: var(--eg-text);
        font: inherit;
        min-width: 68px;
      }
      .circle ha-icon {
        --mdc-icon-size: 28px;
        width: 68px;
        height: 68px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        background: var(--eg-elevated);
        color: var(--eg-text);
      }
      .circle small {
        font-size: 12px;
        font-weight: 500;
        color: var(--eg-text-2);
      }
      .circle[disabled] {
        cursor: not-allowed;
        opacity: 0.5;
      }
      .circle.accept ha-icon {
        background: var(--eg-success);
        color: var(--eg-on-fill);
      }
      .circle.reject ha-icon {
        background: var(--eg-error);
        color: var(--eg-on-fill);
      }
      .circle.mic-on ha-icon {
        background: var(--eg-primary);
        color: var(--eg-on-fill);
      }
      /* ---- idle-заглушка (детально — в Slice 5) ---- */
      ha-card.idle {
        height: 100%;
        box-sizing: border-box;
        display: flex;
        align-items: stretch;
        justify-content: center;
        padding: 20px 16px;
      }
      .idle-stage {
        width: 100%;
        aspect-ratio: 16 / 9;
        border-radius: var(--eg-r-md);
        background: var(--eg-elevated);
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: 6px;
        text-align: center;
        padding: 14px;
        box-sizing: border-box;
        color: var(--eg-text-2);
      }
      .idle-stage ha-icon {
        --mdc-icon-size: 52px;
        color: var(--eg-primary);
        opacity: 0.75;
      }
      .idle-title {
        font-size: 1.3rem;
        font-weight: 700;
        color: var(--eg-text);
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
        border-radius: var(--eg-r-full);
        background: var(--eg-card);
        color: var(--eg-text);
        font-size: 0.8rem;
        font-weight: 600;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.25);
      }
      .chip ha-icon {
        --mdc-icon-size: 16px;
        color: var(--eg-success);
        opacity: 1;
      }
    `,
  ];
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
