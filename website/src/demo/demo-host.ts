// DemoHost — управляет реальной карточкой eg-intercom-call-card вне HA:
// подставляет mock hass, переключает фазы вызова, перехватывает сервисы.
// Симуляция: без подключения к аккаунту, без логинов и SMS. Интерфейс —
// production-бандл интеграции, не перерисованная копия.

import { loadCardBundle } from "./ha-stubs";
import type { DemoPhase } from "./scenario";

export interface DemoAction {
  domain: string;
  service: string;
}

export interface DemoHostOptions {
  layout?: "full" | "compact";
  lang?: "ru" | "en";
  name?: string;
  address?: string;
  /** Начальная фаза — карточка рендерится сразу в ней, без флликера idle. */
  phase?: DemoPhase;
  talkSec?: number;
  /** Реакция на действия пользователя в карточке (Принять, Открыть…). */
  onAction?: (action: DemoAction) => void;
}

interface MockState {
  state: string;
  attributes: Record<string, unknown>;
}

/* eslint-disable @typescript-eslint/no-explicit-any */
type CardEl = HTMLElement & Record<string, any>;

export class DemoHost {
  private root: HTMLElement;
  private opts: Required<Omit<DemoHostOptions, "onAction" | "phase" | "talkSec">> & {
    onAction?: (a: DemoAction) => void;
  };
  private card: CardEl | null = null;
  private phase: DemoPhase;
  private lockState: "locked" | "unlocked" = "locked";
  private startedAt = "";
  private destroyed = false;

  constructor(root: HTMLElement, options: DemoHostOptions = {}) {
    this.root = root;
    this.phase = options.phase ?? "idle";
    if (this.phase === "active") {
      const talk = options.talkSec ?? 0;
      this.startedAt = new Date(Date.now() - talk * 1000).toISOString();
    }
    this.opts = {
      layout: options.layout ?? "full",
      lang: options.lang ?? "ru",
      name: options.name ?? "Подъезд 2",
      address: options.address ?? "ул. Примерная, 1",
      onAction: options.onAction,
    };
  }

  async mount(): Promise<void> {
    await loadCardBundle();
    if (this.destroyed) return;
    this.createCard();
  }

  private createCard(): void {
    this.root.textContent = "";
    const card = document.createElement("eg-intercom-call-card") as CardEl;
    card.setConfig({
      camera: "camera.intercom_call",
      layout: this.opts.layout,
      open_action: "slide",
      // Реальный захват микрофона в симуляции запрещён — авто-старт выключен,
      // сам тумблер остаётся видимым (см. override _toggleMic ниже).
      mic_autostart: false,
      doorbells: [
        {
          call_state: "sensor.intercom_call_state",
          doorbell_camera: "camera.doorbell",
          lock: "lock.intercom",
          name: this.opts.name,
          address: this.opts.address,
        },
      ],
    });
    // Демо-детерминизм: ошибка и «Вызов завершён» в карточке гаснут по
    // внутренним таймерам — здесь состояние держится, пока его не сменит
    // сценарий или пользователь. Тумблер микрофона переключает только
    // индикатор: настоящий getUserMedia в симуляции не вызывается никогда.
    try {
      card._scheduleErrDismiss = () => {};
      card._clearEnded = () => {};
      card._toggleMic = () => {
        card._micActive = !card._micActive;
        card.requestUpdate?.();
      };
      // Точечно (только для этого экземпляра): статус разрешения микрофона
      // всегда «granted», чтобы реальное состояние браузера пользователя
      // не рисовало на витрине «Доступ запрещён».
      card._mic.queryPermission = async () => "granted";
    } catch {
      /* приватный API может измениться — не критично для демо */
    }
    this.card = card;
    this.quiet();
    card.hass = this.buildHass();
    this.root.appendChild(card);
    this.quietAfterRender();
  }

  /** Переключить фазу вызова, как это сделал бы координатор интеграции. */
  setPhase(phase: DemoPhase, opts: { talkSec?: number; doorOpen?: boolean } = {}): void {
    this.phase = phase;
    if (phase === "active") {
      const talk = opts.talkSec ?? 0;
      this.startedAt = new Date(Date.now() - talk * 1000).toISOString();
    }
    this.lockState = opts.doorOpen ? "unlocked" : "locked";
    this.pushHass();
    const card = this.card;
    if (card) {
      const openStatus = opts.doorOpen ? "opened" : "idle";
      Promise.resolve(card.updateComplete)
        .then(() => {
          // Слайдер «Открыть» показывает зелёное «Открыто», когда дверь
          // открыта сценарием, — визуал совпадает с текстом шага.
          card._openStatus = openStatus;
          if (phase === "ringing") {
            // Окно ответа: «идёт 9-я секунда», а не нулевой прогресс.
            card._ringingSince = Date.now() - 9000;
          }
          card.requestUpdate?.();
        })
        .catch(() => {});
    }
    this.quietAfterRender();
  }

  getPhase(): DemoPhase {
    return this.phase;
  }

  setLang(lang: "ru" | "en"): void {
    this.opts.lang = lang;
    this.opts.name = lang === "en" ? "Entrance 2" : "Подъезд 2";
    this.opts.address = lang === "en" ? "1 Example St" : "ул. Примерная, 1";
    this.createCard();
    this.setPhase(this.phase);
  }

  setLayout(layout: "full" | "compact"): void {
    this.opts.layout = layout;
    this.createCard();
    this.setPhase(this.phase);
  }

  getLayout(): "full" | "compact" {
    return this.opts.layout;
  }

  destroy(): void {
    this.destroyed = true;
    this.root.textContent = "";
    this.card = null;
  }

  private buildHass(): Record<string, unknown> {
    const camState = this.phase === "error" ? "unavailable" : "streaming";
    const states: Record<string, MockState> = {
      "sensor.intercom_call_state": {
        state: this.phase,
        attributes: {
          intercom_name: this.opts.name,
          started_at: this.startedAt,
        },
      },
      "camera.intercom_call": { state: camState, attributes: {} },
      "camera.doorbell": { state: camState, attributes: {} },
      "lock.intercom": { state: this.lockState, attributes: {} },
    };
    return {
      states,
      locale: { language: this.opts.lang },
      language: this.opts.lang,
      connection: {},
      callService: async (domain: string, service: string) => {
        this.opts.onAction?.({ domain, service });
      },
    };
  }

  private pushHass(): void {
    if (!this.card) return;
    this.card.hass = this.buildHass();
  }

  /**
   * В симуляции звук считается включённым, микрофон — активным: реальные
   * autoplay/permission-состояния браузера не должны кричать с витрины.
   * Ставим ДО первого рендера — иначе состояния мигают (см. также
   * заглушку Permissions API в ha-stubs).
   */
  private quiet(): void {
    const card = this.card;
    if (!card) return;
    try {
      card._audioBlocked = false;
      card._micPerm = "granted";
      card._micActive = true;
    } catch {
      /* noop */
    }
  }

  /** Повторно после рендера — внутренние обработчики могли перезаписать. */
  private quietAfterRender(): void {
    const card = this.card;
    if (!card) return;
    this.quiet();
    Promise.resolve(card.updateComplete)
      .then(() => {
        this.quiet();
        card.requestUpdate?.();
      })
      .catch(() => {});
  }
}
