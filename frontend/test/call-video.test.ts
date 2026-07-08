import { describe, expect, it } from "vitest";

import { pickCameraEntity } from "../src/components/call-video.js";

const cfg = { camera: "camera.intercom_call", doorbell_camera: "camera.podyezd_2" };

describe("pickCameraEntity", () => {
  it("active (video=call) → камера вызова (видео+звук)", () => {
    expect(pickCameraEntity("call", cfg)).toBe("camera.intercom_call");
  });

  it("ringing (video=doorbell) → камера домофона", () => {
    expect(pickCameraEntity("doorbell", cfg)).toBe("camera.podyezd_2");
  });

  it("doorbell без doorbell_camera → падает на camera", () => {
    expect(pickCameraEntity("doorbell", { camera: "camera.x" })).toBe("camera.x");
  });

  it("video=none → ничего", () => {
    expect(pickCameraEntity("none", cfg)).toBeUndefined();
  });
});
