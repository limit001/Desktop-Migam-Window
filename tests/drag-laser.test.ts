import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const commands = readFileSync(
  new URL("../src-tauri/src/presentation/commands.rs", import.meta.url),
  "utf8",
);
const sprite = readFileSync(new URL("../src/pet/sprite.ts", import.meta.url), "utf8");
const styles = readFileSync(new URL("../src/styles.css", import.meta.url), "utf8");

const SPRITE_WIDTH = 96;
const SPRITE_HEIGHT = 104;

function rustConst(name: string): number {
  // 다른 상수를 그대로 참조하는 경우도 따라간다.
  const found = new RegExp(`const ${name}: u32 = (\\w+);`).exec(commands);
  expect(found, `${name} not found`).not.toBeNull();
  const value = found?.[1] ?? "";
  return /^\d+$/.test(value) ? Number(value) : rustConst(value);
}

function laserBlock(): string {
  return styles.slice(styles.indexOf(".pet-laser {"), styles.indexOf(".pet-laser[hidden]"));
}

function eyes(): { x: number; y: number }[] {
  const start = sprite.indexOf("const DRAG_EYES = [");
  const block = sprite.slice(start, sprite.indexOf("] as const;", start));
  return [...block.matchAll(/x: (\d+), y: (\d+)/g)].map((match) => ({
    x: Number(match[1]),
    y: Number(match[2]),
  }));
}

function beamLength(): number {
  return Number(/width: (\d+)px;/.exec(laserBlock())?.[1]);
}

function beamAngle(): number {
  return Number(/transform: rotate\((-?\d+)deg\);/.exec(laserBlock())?.[1]);
}

describe("드래그 레이저", () => {
  it("빔이 넓힌 펫 창 안에 들어온다", () => {
    const width = rustConst("DRAG_LASER_WIDTH");
    const height = rustConst("DRAG_LASER_HEIGHT");
    const length = beamLength();
    const angle = beamAngle();
    const origins = eyes();

    expect(origins).toHaveLength(2);
    expect(length).toBeGreaterThan(0);
    // 두 빔 모두 왼쪽으로 곧게 나간다.
    expect(angle).toBe(180);

    // 스프라이트는 셸 하단 중앙에 놓인다.
    const offsetX = (width - SPRITE_WIDTH) / 2;
    const offsetY = height - SPRITE_HEIGHT;

    for (const eye of origins) {
      const radians = (angle * Math.PI) / 180;
      const endX = offsetX + eye.x + Math.cos(radians) * length;
      const endY = offsetY + eye.y + Math.sin(radians) * length;
      expect(endX).toBeGreaterThanOrEqual(0);
      expect(endX).toBeLessThanOrEqual(width);
      expect(endY).toBeGreaterThanOrEqual(0);
      expect(endY).toBeLessThanOrEqual(height);
    }
  });

  it("드래그를 벗어나면 창을 원래 크기로 되돌린다", () => {
    const runtime = readFileSync(
      new URL("../src/pet/tauri-motion-runtime.ts", import.meta.url),
      "utf8",
    );
    expect(runtime).toContain('if (nextMode.kind !== "dragged" && dragLaserActive)');
    expect(commands).toContain("pub fn set_drag_laser_expanded");
  });
});
