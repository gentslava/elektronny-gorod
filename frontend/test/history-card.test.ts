import { describe, expect, it } from "vitest";

import { EgEventHistoryCard } from "../src/eg-event-history-card.js";

describe("history card", () => {
  it("documents the account and place scoped entity id in its stub", () => {
    expect(EgEventHistoryCard.getStubConfig()).toEqual({
      entities: ["event.account_123456_place_7890_event_history"],
    });
  });
});
