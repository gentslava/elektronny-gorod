import { describe, expect, it } from "vitest";

import { pickStageContent } from "../src/components/call-stage.js";

describe("pickStageContent", () => {
  it("live → видео", () => {
    expect(pickStageContent("live")).toBe("video");
  });
  it("camera_off → плейсхолдер камеры", () => {
    expect(pickStageContent("camera_off")).toBe("placeholder-camera");
  });
  it("connection_lost → плейсхолдер связи", () => {
    expect(pickStageContent("connection_lost")).toBe("placeholder-connection");
  });
  it("ended → видео с затемнением", () => {
    expect(pickStageContent("ended")).toBe("video-dimmed");
  });
});
