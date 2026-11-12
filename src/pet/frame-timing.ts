export interface FrameStep {
  frame: number;
  ticks: number;
}

/**
 * 프레임마다 머무는 tick 수를 다르게 준다. `holds`가 없으면 매 tick마다 넘어간다.
 * 시선처럼 한참 멈췄다가 짧게 움직이는 연출에 쓴다.
 */
export function nextFrameStep(
  step: FrameStep,
  frames: number,
  holds?: readonly number[],
): FrameStep {
  const hold = Math.max(1, Math.floor(holds?.[step.frame] ?? 1));
  const ticks = step.ticks + 1;
  if (ticks < hold) return { frame: step.frame, ticks };
  return { frame: (step.frame + 1) % frames, ticks: 0 };
}
