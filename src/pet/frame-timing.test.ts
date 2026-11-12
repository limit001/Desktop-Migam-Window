import { describe, expect, it } from "vitest";
import { nextFrameStep } from "./frame-timing";

describe("frame timing", () => {
  it("holds가 없으면 매 tick마다 다음 프레임으로 넘어간다", () => {
    expect(nextFrameStep({ frame: 0, ticks: 0 }, 3)).toEqual({ frame: 1, ticks: 0 });
    expect(nextFrameStep({ frame: 2, ticks: 0 }, 3)).toEqual({ frame: 0, ticks: 0 });
  });

  it("지정한 tick 수만큼 같은 프레임에 머문다", () => {
    const holds = [3, 1];
    expect(nextFrameStep({ frame: 0, ticks: 0 }, 2, holds)).toEqual({ frame: 0, ticks: 1 });
    expect(nextFrameStep({ frame: 0, ticks: 1 }, 2, holds)).toEqual({ frame: 0, ticks: 2 });
    expect(nextFrameStep({ frame: 0, ticks: 2 }, 2, holds)).toEqual({ frame: 1, ticks: 0 });
    expect(nextFrameStep({ frame: 1, ticks: 0 }, 2, holds)).toEqual({ frame: 0, ticks: 0 });
  });

  it("hold 값이 없거나 1보다 작아도 프레임이 멈추지 않는다", () => {
    expect(nextFrameStep({ frame: 1, ticks: 0 }, 2, [4])).toEqual({ frame: 0, ticks: 0 });
    expect(nextFrameStep({ frame: 0, ticks: 0 }, 2, [0, 0])).toEqual({ frame: 1, ticks: 0 });
  });
});
