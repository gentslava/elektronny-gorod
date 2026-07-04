// eg-intercom-call-card — экран входящего вызова и разговора с домофоном «Электронный
// город» (Lit+TS). Одна карточка на ВСЕ домофоны: показывает активный вызов (любой из
// списка) или единую заглушку «Нет вызова» в простое. Облик нативный HA (theme-токены,
// mdi, M3, a11y). Состояние — по sensor.*_call_state. Вёрстка — по production-макетам
// (pencil/design.pen), см. call-card-ux-production.md + plan-call-card-reverstka.md.
import { LitElement, css, html, nothing, type PropertyValues, type TemplateResult } from "lit";
import { customElement, property, state } from "lit/decorators.js";

import { type ActionKind, type CallPhase, type CallView, deriveView, toPhase } from "./state-machine.js";
import { pickCameraEntity } from "./components/call-video.js";
import { type StageState } from "./components/call-stage.js";
import "./components/call-stage.js";
import "./components/open-control.js";
import "./components/eg-icon.js";
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
  /** Автоплей со звуком заблокирован (auto-разворот без жеста) → CTA/тап снимают. */
  @state() private _audioBlocked = false;
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
    this._muted = false; // пытаемся со звуком; снять блок автоплея — тап по видео/CTA (жест)
    // Автоплей со звуком разрешён только после user-жеста. Приняли тапом → звук ок;
    // auto-разворот (kiosk-панель, без тапа) → браузер блокирует → показываем CTA.
    this._audioBlocked = this._detectAudioBlocked();
    this._startTick();
    this._micPerm = await this._mic.queryPermission();
    if (this._config.mic_autostart !== false && shouldAutoStartMic(this._micPerm, this._mic.secure)) {
      await this._mic.start();
    }
  }

  /** Эвристика блокировки автоплея-со-звуком: не было ли user-активации на странице. */
  private _detectAudioBlocked(): boolean {
    const ua = (navigator as Navigator & { userActivation?: { hasBeenActive: boolean } }).userActivation;
    return ua ? !ua.hasBeenActive : false;
  }

  private _exitActive(): void {
    this._mic.stop();
    this._stopTick();
    this._audioBlocked = false;
  }

  /** Снять mute (тап по видео / CTA / кнопка «Звук выкл.»). */
  private _unmute = (): void => {
    this._muted = false;
    this._audioBlocked = false;
  };

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

  /** Повторить (error/connection_lost) — уточняется в Slice 4. */
  private _retry = (): void => {
    void this.hass?.callService("elektronny_gorod", "answer");
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

  /** Состояние видео-области: связь прервана / камера недоступна / живое. */
  private _stageState(view: CallView, cam: string | undefined): StageState {
    if (view.isError) return "connection_lost";
    const camObj = cam ? this.hass?.states[cam] : undefined;
    if (!camObj || camObj.state === "unavailable") return "camera_off";
    return "live";
  }

  /** Таймстамп потока «DD-MM-YYYY HH:MM:SS» (только на живом видео). */
  private _timestamp(stageState: StageState): string {
    if (stageState !== "live") return "";
    const d = new Date(this._now);
    const p = (n: number): string => String(n).padStart(2, "0");
    return `${p(d.getDate())}-${p(d.getMonth() + 1)}-${d.getFullYear()} ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
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
    const stageState = this._stageState(view, cam);

    return html`
      <ha-card class="phase-${phase}">
        <div class="content">
          ${this._renderHeader()}
          ${this._renderStatus(view, phase)}
          <div class="stage">
            <eg-call-stage
              .hass=${this.hass}
              .entity=${cam}
              .muted=${this._muted}
              .live=${stageState === "live"}
              .soundOff=${phase === "active" && this._muted && !this._audioBlocked}
              .timestamp=${this._timestamp(stageState)}
              .stageState=${stageState}
              .audioBlocked=${this._audioBlocked}
              @unmute=${this._unmute}
            ></eg-call-stage>
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
          <eg-icon name="x"></eg-icon>
        </button>
      </header>
    `;
  }

  private _renderStatus(view: CallView, phase: CallPhase): TemplateResult {
    const showTimer = view.showTimer && this._config.timer !== "off";
    const win = view.showAnswerWindow ? this._answerWindow() : null;
    return html`
      <div class="statusrow">
        <div class="strow">
          <span class="badge" style="--badge:${statusColor(phase)}">
            <span class="dot" aria-hidden="true"></span>
            <span>${STATUS_RU[phase] ?? ""}</span>
          </span>
          ${win
            ? html`<span class="countdown"><eg-icon name="timer"></eg-icon>${win.text}</span>`
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
          <eg-icon name="door-open" class="idle-ic"></eg-icon>
          <div class="idle-title">${this._config.idle_text ?? "Нет активного вызова"}</div>
          <div class="idle-sub">Экран покажет видео, звук и кнопки при звонке домофона</div>
          ${names.length
            ? html`<div class="idle-chips">
                ${names.map(
                  (n) => html`<span class="chip"><eg-icon name="circle-check"></eg-icon>${n}</span>`,
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

  /** Круглая кнопка действия: обёртка .ic (68) + lucide-иконка (28) + подпись. */
  private _circle(
    icon: string,
    label: string,
    onClick: () => void,
    variant = "",
  ): TemplateResult {
    return html`
      <button class="circle ${variant}" @click=${onClick} aria-label=${label}>
        <span class="ic"><eg-icon name=${icon}></eg-icon></span>
        <small>${label}</small>
      </button>
    `;
  }

  /** Ряд действий — из view.actions (порядок = слева-направо). */
  private _renderActions(view: CallView): TemplateResult {
    return html`<div class="actions">${view.actions.map((a) => this._renderAction(a))}</div>`;
  }

  private _renderAction(kind: ActionKind): TemplateResult | typeof nothing {
    switch (kind) {
      case "accept":
        return this._circle("phone", "Принять", this._answer, "accept");
      case "reject":
        return this._circle("phone-off", "Отклонить", this._hangup, "reject");
      case "cancel":
        return this._circle("phone-off", "Отменить", this._hangup, "reject");
      case "connecting":
        return this._spinnerBtn("Соединяем…");
      case "mic":
        return this._config.mic === false ? nothing : this._renderMic();
      case "sound":
        return this._audioBlocked
          ? this._circle("volume-x", "Звук выкл.", this._unmute, "warn")
          : this._circle(this._muted ? "volume-x" : "volume-2", "Звук", this._toggleMute);
      case "hangup":
        return this._circle("phone-off", "Завершить", this._hangup, "reject");
      case "retry":
        return this._circle("refresh-cw", "Повторить", this._retry, "retry");
      case "close":
        return this._circle("x", "Закрыть", this._dismiss);
      default:
        return nothing;
    }
  }

  /** «Соединяем…» — неинтерактивная кнопка со спиннером (elevated, приглушённая). */
  private _spinnerBtn(label: string): TemplateResult {
    return html`
      <div class="circle spinner-btn" role="status" aria-label=${label} aria-busy="true">
        <span class="ic"><eg-icon class="spin" name="loader-circle"></eg-icon></span>
        <small>${label}</small>
      </div>
    `;
  }

  /** Микрофон: базовый тумблер. Denied/HTTPS/баннер — уточняется в Slice 4. */
  private _renderMic(): TemplateResult {
    const usable = this._mic.secure && this._micPerm !== "denied";
    if (!usable) {
      return html`<button class="circle" disabled aria-label="Микрофон недоступен"
              title="Микрофон доступен только по HTTPS и с разрешением браузера">
        <span class="ic"><eg-icon name="mic-off"></eg-icon></span><small>Микрофон</small>
      </button>`;
    }
    const icon = this._micActive ? "mic" : "mic-off";
    const aria = this._micActive ? "Выключить микрофон" : "Включить микрофон";
    return html`<button class="circle" @click=${this._toggleMic} aria-label=${aria}>
      <span class="ic"><eg-icon name=${icon}></eg-icon></span><small>Микрофон</small>
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
      .close eg-icon {
        --eg-icon-size: 20px;
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
      .countdown eg-icon {
        --eg-icon-size: 15px;
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
      @keyframes spin {
        to {
          transform: rotate(360deg);
        }
      }
      @media (prefers-reduced-motion: reduce) {
        .spin {
          animation: none;
        }
      }
      /* ---- зона «Открыть» ---- */
      .open-area {
        display: flex;
        justify-content: center;
      }
      .open-area eg-open-control {
        width: 100%;
      }
      /* ---- ряд действий: круги top-align (как в макете), gap 28 ---- */
      .actions {
        display: flex;
        gap: 28px;
        justify-content: center;
        align-items: flex-start;
        flex-wrap: wrap;
      }
      .circle {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 8px;
        border: none;
        background: none;
        cursor: pointer;
        color: var(--eg-text);
        font: inherit;
        padding: 0;
      }
      .circle .ic {
        width: 68px;
        height: 68px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        background: var(--eg-elevated);
        color: var(--eg-text);
      }
      .circle .ic eg-icon {
        --eg-icon-size: 28px;
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
      /* Все кнопки ряда — единый стиль: круг 68, иконка 28, подпись fs12/fw500/text-2.
         Акцент действия — только ЦВЕТОМ круга (см. call-card-ux-production.md §6/§9). */
      .circle.accept .ic {
        background: var(--eg-success);
        color: var(--eg-on-fill);
      }
      .circle.reject .ic {
        background: var(--eg-error);
        color: var(--eg-on-fill);
      }
      .circle.retry .ic {
        background: var(--eg-primary);
        color: var(--eg-on-fill);
      }
      /* audio_blocked: «Звук выкл.» — warning-иконка на elevated */
      .circle.warn .ic {
        color: var(--eg-warning);
      }
      .circle.warn small {
        color: var(--eg-warning);
      }
      /* «Соединяем…» — неинтерактивно, приглушённый крутящийся loader */
      .spinner-btn {
        cursor: default;
      }
      .spinner-btn small {
        color: var(--eg-text-3);
      }
      .spinner-btn .ic eg-icon.spin {
        color: var(--eg-text-2);
        animation: spin 0.9s linear infinite;
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
      .idle-stage .idle-ic {
        --eg-icon-size: 52px;
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
      .chip eg-icon {
        --eg-icon-size: 16px;
        color: var(--eg-success);
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
