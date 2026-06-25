// Чистая логика экрана вызова: фаза вызова (sensor.*_call_state) → что показывать.
// Без DOM/Lit — юнит-тестируемо (vitest). Соответствует call-card-ux-spec.md §5.

export type CallPhase =
  | "idle"
  | "ringing"
  | "connecting"
  | "active"
  | "ended"
  | "error";

export type VideoSource = "call" | "doorbell" | "none";

export interface CallView {
  /** Карточка видима (idle/ended-после-скрытия → false). */
  visible: boolean;
  /** Какую камеру показывать: активный вызов (видео+звук) / домофон (ringing) / нет. */
  video: VideoSource;
  showAccept: boolean;
  showReject: boolean;
  showHangup: boolean;
  showOpen: boolean;
  showMic: boolean;
  showTimer: boolean;
  /** Идёт соединение (connecting) — показать спиннер вместо статичного статуса. */
  busy: boolean;
  /** Терминальная ошибка — карточка гасится по локальному таймеру (контракт 3a). */
  isError: boolean;
}

const KNOWN: ReadonlySet<string> = new Set([
  "idle",
  "ringing",
  "connecting",
  "active",
  "ended",
  "error",
]);

/** Нормализовать произвольное state-значение HA в фазу (unknown/unavailable → idle). */
export function toPhase(state: string | undefined | null): CallPhase {
  return state && KNOWN.has(state) ? (state as CallPhase) : "idle";
}

const HIDDEN: CallView = {
  visible: false,
  video: "none",
  showAccept: false,
  showReject: false,
  showHangup: false,
  showOpen: false,
  showMic: false,
  showTimer: false,
  busy: false,
  isError: false,
};

/**
 * Свести фазу вызова к видимой модели экрана.
 *
 * - idle / ended → карточка скрыта (ended гасится после краткого показа на стороне
 *   карточки таймером; модель здесь — «скрыто»);
 * - ringing → видео домофона (без звука) + Принять/Отклонить/Открыть;
 * - connecting → видео домофона + спиннер + Отклонить/Открыть (Принять убран);
 * - active → видео вызова (видео+звук) + Открыть/Микрофон/Завершить + таймер;
 * - error → краткий показ ошибки + Открыть/Завершить (контракт 3a: карточка гасит сама).
 */
export function deriveView(phase: CallPhase): CallView {
  switch (phase) {
    case "ringing":
      return {
        ...HIDDEN,
        visible: true,
        video: "doorbell",
        showAccept: true,
        showReject: true,
        showOpen: true,
      };
    case "connecting":
      return {
        ...HIDDEN,
        visible: true,
        video: "doorbell",
        showReject: true,
        showOpen: true,
        busy: true,
      };
    case "active":
      return {
        ...HIDDEN,
        visible: true,
        video: "call",
        showHangup: true,
        showOpen: true,
        showMic: true,
        showTimer: true,
      };
    case "error":
      return {
        ...HIDDEN,
        visible: true,
        video: "none",
        showHangup: true,
        showOpen: true,
        isError: true,
      };
    case "idle":
    case "ended":
    default:
      return { ...HIDDEN };
  }
}
