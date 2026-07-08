// Локализация карточки вызова (ru/en). Язык берётся из `hass.locale.language`
// (fallback `hass.language`, затем `ru`). Строки — плоские таблицы; интерполяция
// (таймер/окно ответа) делается в местах использования. Юнит-тест: test/i18n.test.ts.

export type Lang = "ru" | "en";

interface HassLangLike {
  locale?: { language?: string };
  language?: string;
}

/** Выбрать язык карточки по hass (en* → en, иначе ru). */
export function langOf(hass?: HassLangLike): Lang {
  const raw = hass?.locale?.language ?? hass?.language ?? "";
  return raw.toLowerCase().startsWith("en") ? "en" : "ru";
}

export interface Strings {
  /** Статус-бейдж по фазе (полный). */
  status: Record<"ringing" | "connecting" | "active" | "ended" | "error", string>;
  /** Компактная строка (layout: compact) — короткие слова статуса. */
  compact: Record<"call" | "talk" | "connecting" | "ended" | "error", string>;
  nameFallback: string;
  minimize: string;
  idle: { title: string; sub: string };
  action: {
    accept: string;
    reject: string;
    cancel: string;
    connecting: string;
    hangup: string;
    retry: string;
    close: string;
    sound: string;
    soundOff: string;
    mic: string;
    micNoAccess: string;
    micOn: string;
    micOff: string;
  };
  micBanner: {
    no_https: { title: string; sub: string };
    denied: { title: string; sub: string; cta: string };
    prompt: { title: string; sub: string; cta: string };
  };
  stage: {
    cameraOff: { title: string; sub: string };
    connectionLost: { title: string; sub: string };
    soundOffChip: string;
    unmuteAria: string;
    unmuteCta: string;
  };
  video: {
    noVideo: string;
    cameraUnavailable: string;
    loading: string;
    playerUnavailable: string;
  };
  open: {
    labelDefault: string;
    opened: string;
    opening: string;
    slide: string;
    hold: string;
    captionOpened: string;
    captionError: string;
    captionSlideHint: string;
    holdAriaSuffix: string;
  };
}

const RU: Strings = {
  status: {
    ringing: "Входящий вызов",
    connecting: "Соединение…",
    active: "Разговор",
    ended: "Вызов завершён",
    error: "Ошибка вызова",
  },
  compact: {
    call: "Вызов",
    talk: "Разговор",
    connecting: "Соединение…",
    ended: "Завершён",
    error: "Ошибка вызова",
  },
  nameFallback: "Домофон",
  minimize: "Свернуть",
  idle: {
    title: "Нет активного вызова",
    sub: "Видео появится при звонке в домофон",
  },
  action: {
    accept: "Принять",
    reject: "Отклонить",
    cancel: "Отменить",
    connecting: "Соединяем…",
    hangup: "Завершить",
    retry: "Повторить",
    close: "Закрыть",
    sound: "Звук",
    soundOff: "Звук выкл.",
    mic: "Микрофон",
    micNoAccess: "Нет доступа",
    micOn: "Включить микрофон",
    micOff: "Выключить микрофон",
  },
  micBanner: {
    no_https: {
      title: "Микрофон недоступен",
      sub: "Откройте Home Assistant по HTTPS, чтобы говорить в домофон.",
    },
    denied: {
      title: "Доступ к микрофону запрещён",
      sub: "Разрешите микрофон для этого сайта в настройках браузера.",
      cta: "Повторить",
    },
    prompt: {
      title: "Нужен доступ к микрофону",
      sub: "Нажмите «Разрешить», чтобы вас было слышно.",
      cta: "Разрешить",
    },
  },
  stage: {
    cameraOff: { title: "Видео недоступно", sub: "Аудиовызов продолжается" },
    connectionLost: { title: "Соединение прервано", sub: "Пробуем восстановить…" },
    soundOffChip: "Звук выкл.",
    unmuteAria: "Включить звук",
    unmuteCta: "Нажмите, чтобы включить звук",
  },
  video: {
    noVideo: "Нет активного видео",
    cameraUnavailable: "Камера недоступна",
    loading: "Загрузка видео…",
    playerUnavailable: "Видеоплеер недоступен — обновите HA или установите advanced-camera-card",
  },
  open: {
    labelDefault: "Открыть дверь",
    opened: "Открыто",
    opening: "Открываю…",
    slide: "Открыть",
    hold: "Удерживайте, чтобы открыть",
    captionOpened: "Дверь открыта",
    captionError: "Не удалось открыть · Повторить",
    captionSlideHint: "Сдвиньте, чтобы открыть дверь",
    holdAriaSuffix: "— удерживайте",
  },
};

const EN: Strings = {
  status: {
    ringing: "Incoming call",
    connecting: "Connecting…",
    active: "In call",
    ended: "Call ended",
    error: "Call error",
  },
  compact: {
    call: "Call",
    talk: "In call",
    connecting: "Connecting…",
    ended: "Ended",
    error: "Call error",
  },
  nameFallback: "Intercom",
  minimize: "Minimize",
  idle: {
    title: "No active call",
    sub: "Video appears when someone calls",
  },
  action: {
    accept: "Answer",
    reject: "Decline",
    cancel: "Cancel",
    connecting: "Connecting…",
    hangup: "Hang up",
    retry: "Retry",
    close: "Close",
    sound: "Sound",
    soundOff: "Sound off",
    mic: "Mic",
    micNoAccess: "No access",
    micOn: "Turn microphone on",
    micOff: "Turn microphone off",
  },
  micBanner: {
    no_https: {
      title: "Microphone unavailable",
      sub: "Open Home Assistant over HTTPS to talk to the intercom.",
    },
    denied: {
      title: "Microphone blocked",
      sub: "Allow the microphone for this site in your browser settings.",
      cta: "Retry",
    },
    prompt: {
      title: "Microphone access needed",
      sub: "Tap “Allow” so you can be heard.",
      cta: "Allow",
    },
  },
  stage: {
    cameraOff: { title: "Video unavailable", sub: "Audio call continues" },
    connectionLost: { title: "Connection lost", sub: "Trying to reconnect…" },
    soundOffChip: "Sound off",
    unmuteAria: "Turn sound on",
    unmuteCta: "Tap to turn on sound",
  },
  video: {
    noVideo: "No active video",
    cameraUnavailable: "Camera unavailable",
    loading: "Loading video…",
    playerUnavailable: "Video player unavailable — update HA or install advanced-camera-card",
  },
  open: {
    labelDefault: "Open door",
    opened: "Opened",
    opening: "Opening…",
    slide: "Open",
    hold: "Hold to open",
    captionOpened: "Door opened",
    captionError: "Couldn’t open · Retry",
    captionSlideHint: "Slide to open the door",
    holdAriaSuffix: "— hold",
  },
};

const TABLES: Record<Lang, Strings> = { ru: RU, en: EN };

/** Таблица строк для языка. */
export function t(lang: Lang): Strings {
  return TABLES[lang] ?? RU;
}
