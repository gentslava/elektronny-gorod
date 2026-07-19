// Единый конфиг-источник проверки совместимости. Все правила — здесь,
// UI только рендерит результат. Формулировки честные: без «100% работает».

export type Device = "intercom" | "camera" | "lock";
export type HaVersion = "ok" | "old" | "unknown";

export type FeatureId =
  | "video"
  | "audio"
  | "doorbell-event"
  | "talk"
  | "open-door"
  | "history"
  | "rtsp"
  | "motion-history";

export type Verdict =
  | "ok"
  | "ok-go2rtc"
  | "needs-https"
  | "experimental"
  | "unsupported"
  | "unknown";

export interface CompatInput {
  device: Device;
  haVersion: HaVersion;
  features: FeatureId[];
}

export interface CompatItem {
  feature: FeatureId;
  label: string;
  verdict: Verdict;
  note: string;
}

export interface CompatReport {
  blocked: boolean;
  summary: string;
  items: CompatItem[];
}

export const DEVICES: Record<Device, string> = {
  intercom: "Домофон",
  camera: "Камера двора / подъезда",
  lock: "Замок / калитка",
};

export const FEATURES: Record<FeatureId, { label: string; devices: Device[] }> = {
  video: { label: "Видео в Home Assistant", devices: ["intercom", "camera"] },
  audio: { label: "Звук с камеры", devices: ["intercom", "camera"] },
  "doorbell-event": { label: "Событие звонка в реальном времени", devices: ["intercom"] },
  talk: { label: "Ответить и говорить с гостем", devices: ["intercom"] },
  "open-door": { label: "Открытие двери", devices: ["intercom", "lock"] },
  history: { label: "История вызовов", devices: ["intercom"] },
  rtsp: { label: "Внешний RTSP для NVR / плеера", devices: ["intercom", "camera"] },
  "motion-history": { label: "История движения камеры", devices: ["camera"] },
};

const MIN_HA = "2024.10.4";

function itemFor(feature: FeatureId, device: Device): CompatItem {
  const meta = FEATURES[feature];
  const base = { feature, label: meta.label };

  if (!meta.devices.includes(device)) {
    const deviceNote: Record<FeatureId, string> = {
      "doorbell-event": "События звонка приходят от домофона, а не от камеры.",
      talk: "Разговор возможен только с домофоном.",
      "open-door": "Открывать можно домофоны и замки; у камер нет замка.",
      history: "История вызовов ведётся по домофону.",
      video: "У замка нет видеопотока.",
      audio: "У замка нет аудиопотока.",
      rtsp: "RTSP публикуется для камер и домофонов.",
      "motion-history": "История движения доступна для камер.",
    };
    return {
      ...base,
      verdict: "unsupported",
      note: deviceNote[feature],
    };
  }

  switch (feature) {
    case "video":
      return {
        ...base,
        verdict: "ok",
        note:
          "Превью и live-поток работают из коробки. Операторская ссылка живёт ~30 минут — для долгого просмотра рекомендуем go2rtc.",
      };
    case "audio":
      return {
        ...base,
        verdict: "ok-go2rtc",
        note:
          "Звук и низкая задержка появляются при подключении потока через go2rtc (в Home Assistant 2024.11+ он уже встроен).",
      };
    case "doorbell-event":
      return {
        ...base,
        verdict: "ok",
        note:
          "Звонок приходит FCM-пушем, как в мобильном приложении, — без облачного опроса.",
      };
    case "talk":
      return {
        ...base,
        verdict: "needs-https",
        note:
          "Приём вызова и звук гостя работают из коробки; для микрофона браузеру нужен HTTPS-доступ к Home Assistant. Продвинутая функция.",
      };
    case "open-door":
      return {
        ...base,
        verdict: "ok",
        note: "Сущность lock открывает дверь из интерфейса, автоматизаций и пушей.",
      };
    case "history":
      return {
        ...base,
        verdict: "ok",
        note:
          "Принятые и пропущенные вызовы: сущности событий + готовая карточка с фильтрами.",
      };
    case "rtsp":
      return {
        ...base,
        verdict: "ok-go2rtc",
        note:
          "Опция публикации выключена по умолчанию; включённые камеры получают стабильные RTSP-адреса. Сетевой доступ и firewall — на вашей стороне.",
      };
    case "motion-history":
      return {
        ...base,
        verdict: "experimental",
        note:
          "Отдельная сущность, отключена по умолчанию: её включение запускает опрос выбранной камеры.",
      };
  }
}

export function checkCompatibility(input: CompatInput): CompatReport {
  if (input.haVersion === "old") {
    return {
      blocked: true,
      summary: `Нужен Home Assistant ${MIN_HA} или новее. Обновите Home Assistant — остальное совместимо.`,
      items: [],
    };
  }

  const features = input.features.length
    ? input.features
    : (Object.keys(FEATURES) as FeatureId[]);
  const items = features.map((f) => itemFor(f, input.device));

  const supported = items.filter((i) => i.verdict !== "unsupported").length;
  const versionNote =
    input.haVersion === "unknown"
      ? ` Версию Home Assistant проверьте в «Настройки → Система» (нужна ${MIN_HA}+).`
      : "";

  const summary =
    supported === 0
      ? `Для выбранного устройства эти функции не применимы — посмотрите другой тип устройства. Если считаете это ошибкой, откройте issue.${versionNote}`
      : `Работает и с «Электронным городом», и с Дом.ру — у них одно API, выбирать оператора не нужно.${versionNote}`;

  return { blocked: false, summary, items };
}

export const VERDICT_LABELS: Record<Verdict, string> = {
  ok: "Поддерживается",
  "ok-go2rtc": "Поддерживается с go2rtc",
  "needs-https": "Нужен HTTPS",
  experimental: "Экспериментальная возможность",
  unsupported: "Не применимо",
  unknown: "Недостаточно данных — откройте issue",
};
