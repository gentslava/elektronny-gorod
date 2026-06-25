// eg-intercom-call-card — экран вызова домофона «Электронный город» (Lit+TS).
// Каркас Slice 3b-1: state-машина по sensor.*_call_state + действия (answer/hangup/
// открыть). Видео (HA-native WebRTC), адаптивный slide/hold open-control и микрофон —
// следующие слайсы (см. plan-call-card-ui.md). Облик — нативный HA (theme-токены).
import { LitElement, css, html, nothing, type TemplateResult } from "lit";
import { customElement, property, state } from "lit/decorators.js";

import { type CallView, deriveView, toPhase } from "./state-machine.js";

interface HassLike {
  states: Record<string, { state: string; attributes: Record<string, unknown> }>;
  callService: (domain: string, service: string, data?: Record<string, unknown>) => Promise<unknown>;
  localize?: (key: string) => string;
}

interface CardConfig {
  call_state?: string;
  camera?: string;
  doorbell_camera?: string;
  lock?: string;
  name?: string;
}

const STATUS_RU: Record<string, string> = {
  ringing: "Входящий вызов",
  connecting: "Соединение…",
  active: "Разговор",
  error: "Ошибка вызова",
};

@customElement("eg-intercom-call-card")
export class EgIntercomCallCard extends LitElement {
  @property({ attribute: false }) public hass?: HassLike;
  @state() private _config: CardConfig = {};

  public setConfig(config: CardConfig): void {
    if (!config || !config.call_state) {
      throw new Error("eg-intercom-call-card: укажите 'call_state' (sensor.*_call_state)");
    }
    this._config = config;
  }

  public getCardSize(): number {
    return 6;
  }

  private get _phase() {
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

  private _answer = (): void => {
    void this.hass?.callService("elektronny_gorod", "answer");
  };

  private _hangup = (): void => {
    void this.hass?.callService("elektronny_gorod", "hangup");
  };

  private _open = (): void => {
    const lock = this._config.lock;
    if (!lock) return;
    // Slice 3b-1: подтверждение tap'ом. Адаптивный slide/hold — следующий слайс.
    if (confirm(`Открыть дверь — ${this._intercomName}?`)) {
      void this.hass?.callService("lock", "unlock", { entity_id: lock });
    }
  };

  protected override render(): TemplateResult | typeof nothing {
    const view: CallView = deriveView(this._phase);
    if (!view.visible) return nothing;

    return html`
      <ha-card>
        <div class="head">
          <span class="name">${this._intercomName}</span>
          <span class="status ${view.isError ? "err" : ""}">
            ${view.busy ? html`<span class="dot" aria-hidden="true"></span>` : nothing}
            ${STATUS_RU[this._phase] ?? ""}
          </span>
        </div>

        <div class="video" role="img" aria-label="Видео с домофона">
          <ha-icon icon="mdi:cctv"></ha-icon>
          <span class="video-hint">видео (${view.video})</span>
        </div>

        ${view.showOpen ? this._renderOpen() : nothing}

        <div class="actions">
          ${view.showReject
            ? html`<button class="btn reject" @click=${this._hangup} aria-label="Отклонить">
                <ha-icon icon="mdi:phone-hangup"></ha-icon><span>Отклонить</span>
              </button>`
            : nothing}
          ${view.showAccept
            ? html`<button class="btn accept" @click=${this._answer} aria-label="Принять">
                <ha-icon icon="mdi:phone"></ha-icon><span>Принять</span>
              </button>`
            : nothing}
          ${view.showHangup
            ? html`<button class="btn reject" @click=${this._hangup} aria-label="Завершить">
                <ha-icon icon="mdi:phone-hangup"></ha-icon><span>Завершить</span>
              </button>`
            : nothing}
        </div>
      </ha-card>
    `;
  }

  private _renderOpen(): TemplateResult {
    return html`
      <button class="open" @click=${this._open} aria-label="Открыть дверь">
        <ha-icon icon="mdi:key-variant"></ha-icon><span>Открыть дверь</span>
      </button>
    `;
  }

  static override styles = css`
    :host {
      display: block;
    }
    ha-card {
      padding: 12px;
      display: flex;
      flex-direction: column;
      gap: 12px;
    }
    .head {
      display: flex;
      align-items: baseline;
      justify-content: space-between;
      gap: 8px;
    }
    .name {
      font-size: 1.1rem;
      font-weight: 600;
      color: var(--primary-text-color);
    }
    .status {
      font-size: 0.9rem;
      color: var(--secondary-text-color);
      display: inline-flex;
      align-items: center;
      gap: 6px;
    }
    .status.err {
      color: var(--error-color);
    }
    .dot {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: var(--primary-color);
      animation: pulse 1s ease-in-out infinite;
    }
    @keyframes pulse {
      50% {
        opacity: 0.3;
      }
    }
    @media (prefers-reduced-motion: reduce) {
      .dot {
        animation: none;
      }
    }
    .video {
      aspect-ratio: 16 / 9;
      background: var(--secondary-background-color);
      border-radius: 12px;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      gap: 4px;
      color: var(--secondary-text-color);
    }
    .video ha-icon {
      --mdc-icon-size: 40px;
    }
    .video-hint {
      font-size: 0.8rem;
    }
    .open {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      min-height: 56px;
      border: none;
      border-radius: 12px;
      cursor: pointer;
      font-size: 1rem;
      font-weight: 600;
      color: var(--text-primary-color, #fff);
      background: var(--primary-color);
    }
    .actions {
      display: flex;
      gap: 12px;
      justify-content: center;
    }
    .btn {
      flex: 1;
      max-width: 180px;
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 4px;
      padding: 10px;
      min-height: 56px;
      border: none;
      border-radius: 12px;
      cursor: pointer;
      font-size: 0.85rem;
      color: var(--text-primary-color, #fff);
    }
    .btn.accept {
      background: var(--success-color, #2e7d32);
    }
    .btn.reject {
      background: var(--error-color, #c62828);
    }
    .btn ha-icon {
      --mdc-icon-size: 26px;
    }
  `;
}

declare global {
  interface Window {
    customCards?: Array<{ type: string; name: string; description: string }>;
  }
}

window.customCards = window.customCards || [];
window.customCards.push({
  type: "eg-intercom-call-card",
  name: "ЭГ Домофон — Экран вызова",
  description: "Экран входящего вызова и разговора с домофоном (видео, открыть, принять/завершить).",
});
