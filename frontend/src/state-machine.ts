// Чистая логика экрана вызова: фаза вызова (sensor.*_call_state) → что показывать.
// Без DOM/Lit — юнит-тестируемо (vitest). Соответствует call-card-ux-production.md §5.

export type CallPhase =
  | "idle"
  | "ringing"
  | "connecting"
  | "active"
  | "ended"
  | "error";

export type VideoSource = "call" | "doorbell" | "none";

/** Действие в нижнем ряду. Порядок массива = порядок слева-направо. */
export type ActionKind =
  | "accept" // Принять (success, primary)
  | "reject" // Отклонить (error)
  | "cancel" // Отменить (error) — на connecting
  | "connecting" // «Соединяем…» — disabled-спиннер
  | "mic" // Микрофон (состояния — в карточке)
  | "sound" // Звук (mute/unmute)
  | "hangup" // Завершить (error, primary)
  | "retry" // Повторить (primary) — error/connection_lost
  | "close"; // Закрыть (нейтральная) — ended

export interface CallView {
  /** Карточка видима (idle/ended-после-скрытия → false). */
  visible: boolean;
  /** Какую камеру показывать: активный вызов (видео+звук) / домофон (ringing) / нет. */
  video: VideoSource;
  /** Набор кнопок нижнего ряда (порядок = слева-направо). */
  actions: ActionKind[];
  showOpen: boolean;
  showTimer: boolean;
  /** Полоса окна ответа (только входящий). */
  showAnswerWindow: boolean;
  /** Идёт соединение (connecting) — спиннер в кнопке «Соединяем…». */
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
  actions: [],
  showOpen: false,
  showTimer: false,
  showAnswerWindow: false,
  busy: false,
  isError: false,
};

/**
 * Свести фазу вызова к видимой модели экрана.
 *
 * - idle / ended → карточка скрыта (ended гасится после краткого показа таймером);
 * - ringing → видео домофона (без звука) + Отклонить/Принять + Открыть + окно ответа;
 * - connecting → видео домофона + Отменить/«Соединяем…»(спиннер) + Открыть;
 * - active → видео вызова (видео+звук) + Микрофон/Звук/Завершить + Открыть + таймер;
 * - error → краткий показ ошибки + Повторить/Завершить (карточка гасит сама, 3a).
 */
export function deriveView(phase: CallPhase): CallView {
  switch (phase) {
    case "ringing":
      return {
        ...HIDDEN,
        visible: true,
        video: "doorbell",
        actions: ["reject", "accept"],
        showOpen: true,
        showAnswerWindow: true,
      };
    case "connecting":
      return {
        ...HIDDEN,
        visible: true,
        video: "doorbell",
        actions: ["cancel", "connecting"],
        showOpen: true,
        busy: true,
      };
    case "active":
      return {
        ...HIDDEN,
        visible: true,
        video: "call",
        actions: ["mic", "sound", "hangup"],
        showOpen: true,
        showTimer: true,
      };
    case "error":
      return {
        ...HIDDEN,
        visible: true,
        video: "none",
        actions: ["retry", "hangup"],
        showOpen: true,
        isError: true,
      };
    case "idle":
    case "ended":
    default:
      return { ...HIDDEN };
  }
}
