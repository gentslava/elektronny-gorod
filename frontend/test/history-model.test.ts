import { describe, expect, it, vi } from "vitest";

import {
  fetchHistoryPage,
  formatHistoryTime,
  groupEventsByDay,
  historyStrings,
  mergeHistoryEvents,
  normalizeHistoryPage,
  resolveHistoryConfig,
  type HistoryEventRow,
} from "../src/history/model.js";

const ROWS: HistoryEventRow[] = [
  { event_id: "new", event_type: "call_missed", occurred_at: 1770033600 },
  { event_id: "accepted", event_type: "call_accepted", occurred_at: 1770030000 },
  { event_id: "older", event_type: "call_missed", occurred_at: 1769947200 },
];

describe("history page transport", () => {
  it("uses the entity-scoped WebSocket command", async () => {
    const callWS = vi.fn().mockResolvedValue({
      entity_id: "event.intercom_history",
      events: [],
      page: 3,
      last: true,
    });

    await fetchHistoryPage({ callWS }, "event.intercom_history", 3);

    expect(callWS).toHaveBeenCalledOnce();
    expect(callWS).toHaveBeenCalledWith({
      type: "elektronny_gorod/history",
      entity_id: "event.intercom_history",
      page: 3,
    });
  });

  it("rejects a response routed to another entity", async () => {
    const callWS = vi.fn().mockResolvedValue({
      entity_id: "event.other_history",
      events: [],
      page: 0,
      last: true,
    });

    await expect(fetchHistoryPage({ callWS }, "event.intercom_history", 0))
      .rejects.toThrow(/entity/);
  });

  it("drops malformed and unverified fields from an untrusted response", () => {
    const page = normalizeHistoryPage({
      entity_id: "event.intercom_history",
      source_name: "Подъезд 1",
      page: 0,
      last: false,
      events: [
        { ...ROWS[0], message: "PII-SENTINEL" },
        { event_id: "unknown", event_type: "other", occurred_at: 1770033500 },
        { event_id: "bad-time", event_type: "call_missed", occurred_at: "now" },
      ],
    });

    expect(page.events).toEqual([ROWS[0]]);
    expect(JSON.stringify(page)).not.toContain("PII-SENTINEL");
  });
});

describe("history presentation model", () => {
  it("requires one event entity and preserves an optional title", () => {
    expect(resolveHistoryConfig({ entity: "event.intercom_history", title: "Дом" }))
      .toEqual({ entity: "event.intercom_history", title: "Дом" });
    expect(() => resolveHistoryConfig({})).toThrow(/entity/);
    expect(() => resolveHistoryConfig({ entity: "sensor.balance" })).toThrow(/event/);
  });

  it("formats event time in the selected locale and timezone", () => {
    expect(formatHistoryTime(1770033600, "ru", "UTC")).toBe("12:00");
    expect(formatHistoryTime(1770033600, "en", "UTC")).toBe("12:00 PM");
  });

  it("groups newest-first rows by local calendar day", () => {
    const groups = groupEventsByDay(ROWS, "ru", "UTC");

    expect(groups.map((group) => group.key)).toEqual(["2026-02-02", "2026-02-01"]);
    expect(groups[0]?.events.map((event) => event.event_id)).toEqual(["new", "accepted"]);
    expect(groups[1]?.events.map((event) => event.event_id)).toEqual(["older"]);
  });

  it("deduplicates overlapping pages and preserves descending time order", () => {
    expect(mergeHistoryEvents(ROWS.slice(0, 2), [ROWS[1], ROWS[2]]).map((row) => row.event_id))
      .toEqual(["new", "accepted", "older"]);
  });

  it("provides matching Russian and English call labels", () => {
    expect(historyStrings("ru").event.call_missed).toBe("Домофон: пропущен звонок");
    expect(historyStrings("ru").event.call_accepted).toBe("Домофон: принят звонок");
    expect(historyStrings("en").event.call_missed).toBe("Intercom: missed call");
    expect(historyStrings("en").event.call_accepted).toBe("Intercom: answered call");
  });
});
