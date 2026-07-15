import { describe, expect, it, vi } from "vitest";

import {
  fetchHistoryPage,
  filterHistoryEvents,
  formatHistoryTime,
  groupEventsByDay,
  historySources,
  historyPageRequests,
  historyStrings,
  mergeHistoryEvents,
  normalizeHistoryPage,
  replaceHistoryFeeds,
  resolveHistoryConfig,
  type HistoryEventRow,
} from "../src/history/model.js";

const ROWS: HistoryEventRow[] = [
  {
    event_id: "new", event_type: "call_missed", occurred_at: 1770033600,
    feed_id: "event.account_one", feed_name: "Аккаунт 1",
    source_key: "event.account_one:1001:2001", source_name: "Подъезд 1",
  },
  {
    event_id: "accepted", event_type: "call_accepted", occurred_at: 1770030000,
    feed_id: "event.account_one", feed_name: "Аккаунт 1",
    source_key: "event.account_one:1001:2001", source_name: "Подъезд 1",
  },
  {
    event_id: "older", event_type: "call_missed", occurred_at: 1769947200,
    feed_id: "event.account_two", feed_name: "Аккаунт 2",
    source_key: "event.account_two:1002:3001", source_name: "Калитка 1",
  },
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
      entity_id: "event.account_one",
      source_name: "Аккаунт 1",
      page: 0,
      last: false,
      events: [
        {
          event_id: "new",
          event_type: "call_missed",
          occurred_at: 1770033600,
          place_id: "1001",
          source_id: "2001",
          source_name: "Подъезд 1",
          message: "PII-SENTINEL",
        },
        { event_id: "unknown", event_type: "other", occurred_at: 1770033500 },
        { event_id: "bad-time", event_type: "call_missed", occurred_at: "now" },
      ],
    });

    expect(page.events).toEqual([ROWS[0]]);
    expect(JSON.stringify(page)).not.toContain("PII-SENTINEL");
  });
});

describe("history presentation model", () => {
  it("normalizes one or many account entities and preserves an optional title", () => {
    expect(resolveHistoryConfig({ entity: "event.intercom_history", title: "Дом" }))
      .toEqual({ entities: ["event.intercom_history"], title: "Дом" });
    expect(resolveHistoryConfig({
      entities: ["event.account_one", "event.account_two", "event.account_one"],
    })).toEqual({ entities: ["event.account_one", "event.account_two"] });
    expect(() => resolveHistoryConfig({})).toThrow(/entity/);
    expect(() => resolveHistoryConfig({ entity: "sensor.balance" })).toThrow(/event/);
    expect(() => resolveHistoryConfig({ entities: ["event.ok", "sensor.balance"] })).toThrow(/event/);
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

  it("keeps equal backend IDs from different configured accounts", () => {
    const secondAccount = {
      ...ROWS[0],
      feed_id: "event.account_two",
      feed_name: "Аккаунт 2",
      source_key: "event.account_two:1002:3001",
      source_name: "Калитка 1",
    };

    expect(mergeHistoryEvents([ROWS[0]], [secondAccount])).toHaveLength(2);
  });

  it("preserves stale rows for a feed that failed during refresh", () => {
    const refreshed = {
      ...ROWS[0],
      event_id: "newer",
      occurred_at: ROWS[0].occurred_at + 60,
    };

    expect(
      replaceHistoryFeeds(ROWS, [refreshed], ["event.account_one"])
        .map((row) => row.event_id),
    ).toEqual(["newer", "older"]);
  });

  it("builds device filters across accounts and filters the merged feed", () => {
    expect(historySources(ROWS, true)).toEqual([
      {
        key: "event.account_two:1002:3001",
        label: "Калитка 1 · Аккаунт 2",
      },
      {
        key: "event.account_one:1001:2001",
        label: "Подъезд 1 · Аккаунт 1",
      },
    ]);
    expect(filterHistoryEvents(ROWS, "event.account_one:1001:2001"))
      .toEqual(ROWS.slice(0, 2));
    expect(filterHistoryEvents(ROWS, "")).toEqual(ROWS);
  });

  it("paginates unfinished account feeds independently", () => {
    const states = new Map([
      ["event.account_one", { page: 2, last: true }],
      ["event.account_two", { page: 4, last: false }],
    ]);

    expect(historyPageRequests(
      ["event.account_one", "event.account_two"],
      states,
      false,
    )).toEqual([{ entityId: "event.account_two", page: 5 }]);
    expect(historyPageRequests(
      ["event.account_one", "event.account_two"],
      states,
      true,
    )).toEqual([
      { entityId: "event.account_one", page: 0 },
      { entityId: "event.account_two", page: 0 },
    ]);
  });

  it("provides matching Russian and English call labels", () => {
    expect(historyStrings("ru").event.call_missed).toBe("Домофон: пропущен звонок");
    expect(historyStrings("ru").event.call_accepted).toBe("Домофон: принят звонок");
    expect(historyStrings("en").event.call_missed).toBe("Intercom: missed call");
    expect(historyStrings("en").event.call_accepted).toBe("Intercom: answered call");
  });
});
