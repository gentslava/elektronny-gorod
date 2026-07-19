import { describe, expect, it } from "vitest";

import {
  buildPlan,
  isComplete,
  visibleQuestions,
  type WizardAnswers,
} from "../src/data/wizard";

const BASE: WizardAnswers = {
  hasHA: "yes",
  hasHACS: "yes",
  wantAudio: "no",
  wantTalk: "no",
  wantRtsp: "no",
};

describe("wizard: видимость вопросов", () => {
  it("вопрос про HACS скрыт, пока нет Home Assistant", () => {
    const ids = visibleQuestions({ hasHA: "no" }).map((q) => q.id);
    expect(ids).not.toContain("hasHACS");
  });

  it("вопрос про HTTPS появляется только при желании говорить", () => {
    expect(visibleQuestions({ wantTalk: "no" }).map((q) => q.id)).not.toContain(
      "hasHTTPS",
    );
    expect(visibleQuestions({ wantTalk: "yes" }).map((q) => q.id)).toContain(
      "hasHTTPS",
    );
  });

  it("isComplete учитывает только видимые вопросы", () => {
    expect(isComplete(BASE)).toBe(true);
    expect(isComplete({ ...BASE, wantTalk: "yes" })).toBe(false);
    expect(isComplete({ ...BASE, wantTalk: "yes", hasHTTPS: "yes" })).toBe(true);
  });
});

describe("wizard: сборка плана", () => {
  it("новичок без HA получает шаги HA и HACS первыми", () => {
    const plan = buildPlan({ ...BASE, hasHA: "no", hasHACS: undefined });
    expect(plan.steps[0]?.title).toContain("Home Assistant");
    expect(plan.steps[1]?.title).toContain("HACS");
  });

  it("план всегда содержит HACS deep link и config flow", () => {
    const plan = buildPlan(BASE);
    const links = plan.steps.map((s) => s.link?.href ?? "");
    expect(links.some((l) => l.includes("hacs_repository"))).toBe(true);
    expect(links.some((l) => l.includes("config_flow_start"))).toBe(true);
  });

  it("разговор без HTTPS добавляет шаг настройки HTTPS", () => {
    const plan = buildPlan({ ...BASE, wantTalk: "yes", hasHTTPS: "no" });
    expect(plan.steps.some((s) => s.title.includes("HTTPS"))).toBe(true);
    expect(plan.unlocks.some((u) => u.includes("разговор"))).toBe(true);
  });

  it("разговор с готовым HTTPS не навязывает лишний шаг", () => {
    const plan = buildPlan({ ...BASE, wantTalk: "yes", hasHTTPS: "yes" });
    expect(plan.steps.some((s) => s.title.includes("HTTPS"))).toBe(false);
  });

  it("отказ от звука честно уводит go2rtc в «можно пропустить»", () => {
    const plan = buildPlan(BASE);
    expect(plan.steps.some((s) => s.title.includes("go2rtc"))).toBe(false);
    expect(plan.skipped.some((s) => s.includes("go2rtc"))).toBe(true);
  });

  it("RTSP-шаг помечен опциональным и предупреждает об ответственности", () => {
    const plan = buildPlan({ ...BASE, wantRtsp: "yes" });
    const rtsp = plan.steps.find((s) => s.title.includes("RTSP"));
    expect(rtsp?.optional).toBe(true);
    expect(rtsp?.detail).toContain("ответственности");
  });

  it("план не просит вводить данные аккаунта на сайте", () => {
    const plan = buildPlan({ ...BASE, wantTalk: "yes", hasHTTPS: "dontknow" });
    const text = plan.steps.map((s) => s.title + s.detail).join(" ");
    expect(text).toContain("только внутри вашего Home Assistant");
  });
});
