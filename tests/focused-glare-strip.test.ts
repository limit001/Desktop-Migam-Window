import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const sprite = readFileSync(new URL("../src/pet/sprite.ts", import.meta.url), "utf8");
const strip = readFileSync(
  new URL("../images/characters/gamjabot/extra/frames/focused-glare-strip-v1.png", import.meta.url),
);

function pngSize(file: Buffer): { width: number; height: number } {
  expect(file.subarray(1, 4).toString("ascii")).toBe("PNG");
  return { width: file.readUInt32BE(16), height: file.readUInt32BE(20) };
}

describe("집중 눈동자 스트립", () => {
  const holds = JSON.parse(
    (/const FOCUSED_FRAME_HOLDS = (\[[^\]]*\])/.exec(sprite)?.[1] ?? "[]")
      .replace(/\s+/g, " ")
      .replace(/,\s*\]/, "]"),
  ) as number[];
  const TICK_MS = 120;
  const SCRUNCH_HOLD = 4;

  it("표시 프레임의 정확히 2배 해상도로 집중 프레임을 담는다", () => {
    const { width, height } = pngSize(strip);
    expect(holds.length).toBeGreaterThan(0);
    expect(width).toBe(93 * holds.length * 2);
    expect(height).toBe(104 * 2);
  });

  it("스프라이트 정의가 스트립 기하와 어긋나지 않는다", () => {
    const definition = sprite.slice(sprite.indexOf("  focused: {"), sprite.indexOf("  dancing:"));
    expect(definition).toContain("focusedGlareStrip");
    expect(definition).toContain("frames: FOCUSED_FRAME_HOLDS.length");
    expect(definition).toContain("holds: FOCUSED_FRAME_HOLDS");
    expect(sprite).toContain("const FOCUSED_FRAME_WIDTH = 93;");
  });

  it("찡그림 사이 간격이 3초 안팎이다", () => {
    // 미간이 가장 세게 조이는 프레임(SCRUNCH_HOLD) 사이의 tick 간격을 잰다.
    const peaks = holds.flatMap((hold, index) => (hold === SCRUNCH_HOLD ? [index] : []));
    expect(peaks.length).toBeGreaterThanOrEqual(4);
    const gaps = peaks.slice(1).map((peak, order) =>
      holds.slice(peaks[order], peak).reduce((total, hold) => total + hold, 0),
    );
    for (const gap of gaps) {
      expect(gap * TICK_MS).toBeGreaterThanOrEqual(2_700);
      expect(gap * TICK_MS).toBeLessThanOrEqual(3_300);
    }
  });

  it("찡그림은 짧게 지나가고 나머지는 가만히 있는다", () => {
    const ticks = holds.reduce((total, hold) => total + hold, 0);
    const stillTicks = holds
      .filter((hold) => hold >= 8)
      .reduce((total, hold) => total + hold, 0);
    expect(stillTicks / ticks).toBeGreaterThanOrEqual(0.6);
    expect(Math.max(...holds) * TICK_MS).toBeGreaterThanOrEqual(2_000);
    expect(SCRUNCH_HOLD * TICK_MS).toBeLessThanOrEqual(1_000);
  });
});
