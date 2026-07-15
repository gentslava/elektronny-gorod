import type { Lang } from "../i18n.js";

export type HistoryEventType = "call_accepted" | "call_missed";

export interface HistoryEventRow {
  event_id: string;
  event_type: HistoryEventType;
  /** Unix timestamp in seconds. */
  occurred_at: number;
  /** Entity/feed identity keeps opaque event IDs isolated between accounts. */
  feed_id: string;
  feed_name: string;
  /** Stable client-side identity for one account/place/access-control source. */
  source_key: string;
  source_name: string;
}

export interface HistoryPage {
  entity_id: string;
  source_name: string;
  events: HistoryEventRow[];
  page: number;
  last: boolean;
}

export interface HistoryCardConfig {
  entities: string[];
  title?: string;
}

export interface HistorySource {
  key: string;
  label: string;
}

export interface HistoryFeedState {
  page: number;
  last: boolean;
}

export interface HistoryPageRequest {
  entityId: string;
  page: number;
}

export interface HistoryDayGroup {
  key: string;
  label: string;
  events: HistoryEventRow[];
}

interface HistoryConnection {
  callWS: (message: Record<string, unknown>) => Promise<unknown>;
}

export interface HistoryStrings {
  title: string;
  event: Record<HistoryEventType, string>;
  empty: string;
  unavailable: string;
  retry: string;
  refresh: string;
  more: string;
  loading: string;
  devices: string;
  allDevices: string;
}

const STRINGS: Record<Lang, HistoryStrings> = {
  ru: {
    title: "События",
    event: {
      call_accepted: "Домофон: принят звонок",
      call_missed: "Домофон: пропущен звонок",
    },
    empty: "Событий пока нет",
    unavailable: "Не удалось загрузить историю",
    retry: "Повторить",
    refresh: "Обновить",
    more: "Показать ещё",
    loading: "Загрузка истории…",
    devices: "Устройства",
    allDevices: "Все устройства",
  },
  en: {
    title: "Events",
    event: {
      call_accepted: "Intercom: answered call",
      call_missed: "Intercom: missed call",
    },
    empty: "No events yet",
    unavailable: "Unable to load history",
    retry: "Retry",
    refresh: "Refresh",
    more: "Show more",
    loading: "Loading history…",
    devices: "Devices",
    allDevices: "All devices",
  },
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isHistoryType(value: unknown): value is HistoryEventType {
  return value === "call_accepted" || value === "call_missed";
}

/** Keep only the documented, privacy-safe response shape. */
export function normalizeHistoryPage(value: unknown): HistoryPage {
  const page = isRecord(value) ? value : {};
  const entityId = typeof page.entity_id === "string" ? page.entity_id : "";
  const feedName = typeof page.source_name === "string" ? page.source_name : "";
  const rawEvents = Array.isArray(page.events) ? page.events : [];
  const events = rawEvents.flatMap((raw): HistoryEventRow[] => {
    if (
      !isRecord(raw)
      || typeof raw.event_id !== "string"
      || raw.event_id.length === 0
      || !isHistoryType(raw.event_type)
      || typeof raw.occurred_at !== "number"
      || !Number.isFinite(raw.occurred_at)
    ) {
      return [];
    }
    const placeId = typeof raw.place_id === "string" ? raw.place_id : "";
    const sourceId = typeof raw.source_id === "string" ? raw.source_id : "";
    const sourceName = typeof raw.source_name === "string" && raw.source_name
      ? raw.source_name
      : feedName;
    return [{
      event_id: raw.event_id,
      event_type: raw.event_type,
      occurred_at: raw.occurred_at,
      feed_id: entityId,
      feed_name: feedName,
      source_key: placeId && sourceId
        ? `${entityId}:${placeId}:${sourceId}`
        : entityId,
      source_name: sourceName,
    }];
  });
  return {
    entity_id: entityId,
    source_name: feedName,
    events,
    page: Number.isInteger(page.page) && Number(page.page) >= 0 ? Number(page.page) : 0,
    last: page.last === true,
  };
}

export async function fetchHistoryPage(
  connection: HistoryConnection,
  entityId: string,
  page: number,
): Promise<HistoryPage> {
  const response = await connection.callWS({
    type: "elektronny_gorod/history",
    entity_id: entityId,
    page,
  });
  const normalized = normalizeHistoryPage(response);
  if (normalized.entity_id !== entityId) {
    throw new Error("History response entity does not match the request");
  }
  return normalized;
}

export function mergeHistoryEvents(
  current: readonly HistoryEventRow[],
  incoming: readonly HistoryEventRow[],
): HistoryEventRow[] {
  const byId = new Map<string, HistoryEventRow>();
  for (const event of [...current, ...incoming]) {
    byId.set(`${event.feed_id}:${event.event_id}`, event);
  }
  return [...byId.values()].sort((left, right) => right.occurred_at - left.occurred_at);
}

export function historySources(
  events: readonly HistoryEventRow[],
  includeFeedName = false,
): HistorySource[] {
  const sources = new Map<string, HistorySource>();
  for (const event of events) {
    const sourceName = event.source_name || event.feed_name;
    const label = includeFeedName && event.feed_name && event.feed_name !== sourceName
      ? `${sourceName} · ${event.feed_name}`
      : sourceName;
    if (event.source_key && label) {
      sources.set(event.source_key, { key: event.source_key, label });
    }
  }
  return [...sources.values()].sort((left, right) => left.label.localeCompare(right.label, "ru"));
}

export function filterHistoryEvents(
  events: readonly HistoryEventRow[],
  sourceKey: string,
): HistoryEventRow[] {
  return sourceKey
    ? events.filter((event) => event.source_key === sourceKey)
    : [...events];
}

export function historyPageRequests(
  entities: readonly string[],
  states: ReadonlyMap<string, HistoryFeedState>,
  refresh: boolean,
): HistoryPageRequest[] {
  return entities.flatMap((entityId) => {
    if (refresh) return [{ entityId, page: 0 }];
    const state = states.get(entityId);
    if (state?.last) return [];
    return [{ entityId, page: state ? state.page + 1 : 0 }];
  });
}

export function groupEventsByDay(
  events: readonly HistoryEventRow[],
  lang: Lang,
  timeZone?: string,
): HistoryDayGroup[] {
  const keyFormatter = new Intl.DateTimeFormat("en-CA", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    timeZone,
  });
  const labelFormatter = new Intl.DateTimeFormat(lang === "en" ? "en-US" : "ru-RU", {
    weekday: "long",
    day: "numeric",
    month: "long",
    timeZone,
  });
  const groups = new Map<string, HistoryDayGroup>();
  for (const event of [...events].sort((left, right) => right.occurred_at - left.occurred_at)) {
    const date = new Date(event.occurred_at * 1000);
    const key = keyFormatter.format(date);
    const group = groups.get(key) ?? {
      key,
      label: labelFormatter.format(date),
      events: [],
    };
    group.events.push(event);
    groups.set(key, group);
  }
  return [...groups.values()];
}

export function formatHistoryTime(
  timestamp: number,
  lang: Lang,
  timeZone?: string,
): string {
  return new Intl.DateTimeFormat(lang === "en" ? "en-US" : "ru-RU", {
    hour: "2-digit",
    minute: "2-digit",
    timeZone,
  }).format(new Date(timestamp * 1000));
}

export function resolveHistoryConfig(value: unknown): HistoryCardConfig {
  if (!isRecord(value)) {
    throw new Error("eg-event-history-card: укажите 'entity' или 'entities'");
  }
  const configured = [
    ...(typeof value.entity === "string" && value.entity ? [value.entity] : []),
    ...(Array.isArray(value.entities) ? value.entities : []),
  ];
  const entities = [...new Set(configured)];
  if (!entities.length) {
    throw new Error("eg-event-history-card: укажите 'entity' или 'entities'");
  }
  if (entities.some((entity) => typeof entity !== "string" || !entity.startsWith("event."))) {
    throw new Error("eg-event-history-card: все 'entity' должны быть event-сущностями");
  }
  return {
    entities,
    ...(typeof value.title === "string" && value.title ? { title: value.title } : {}),
  };
}

export function historyStrings(lang: Lang): HistoryStrings {
  return STRINGS[lang];
}
