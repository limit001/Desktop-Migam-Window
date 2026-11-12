"""집중 상태의 쨰려보는 눈과 미간 프레임을 원본 focused 포즈에서 생성한다.

원본 `focused/00.png`는 손대지 않는다. 눈 안쪽 흰 영역과 눈동자를 자동으로 찾아
눈동자를 지우고, 반쯤 감긴 눈꺼풀과 미간 주름을 그린 뒤 프레임별로 눈동자를 다시 찍는다.
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

REPO = Path(__file__).resolve().parent.parent
BASE = REPO / "images/characters/gamjabot/extra/frames/focused/00.png"
INK = (17, 17, 17, 255)
SKIN = (255, 255, 255, 255)
PUPIL_RADIUS = 21

# 미간 단계. 0은 평소, 숫자가 커질수록 주름이 좁고 굵어지며 눈꺼풀도 조금 더 내려온다.
FURROW_LEVELS = {
    0: {"lid": 0.54, "spread": 1.00, "thickness": 16, "top_drop": 0},
    1: {"lid": 0.56, "spread": 0.86, "thickness": 18, "top_drop": 10},
    2: {"lid": 0.58, "spread": 0.72, "thickness": 21, "top_drop": 20},
}

# 애니메이션 tick은 120ms다.
REST_TICKS = 17          # 찡그림 사이에 가만히 있는 시간 (2.04초)
SCRUNCH = [(1, 2), (2, 4), (1, 2)]  # 미간을 조였다 푸는 (단계, tick). 합쳐서 0.96초
GAZE_SEQUENCE = [(0, 0), (-42, 0), (0, 0), (42, 0)]
TRANSIT_OFFSET = 0.52    # 시선 이동 중간 지점 비율


def build_frame_table():
    """(눈동자 dx, dy, 미간 단계, 유지 tick) 프레임 표를 만든다.

    한 시선마다 `쉬고 찡그리기`를 두 번 반복한 뒤 다음 시선으로 넘어간다.
    찡그림은 REST_TICKS + SCRUNCH 주기마다 시작하므로 3.0초 간격이 된다.
    """
    frames = []
    for index, (dx, dy) in enumerate(GAZE_SEQUENCE):
        for _ in range(2):
            frames.append((dx, dy, 0, REST_TICKS))
            frames.extend((dx, dy, level, hold) for level, hold in SCRUNCH)
        next_dx, next_dy = GAZE_SEQUENCE[(index + 1) % len(GAZE_SEQUENCE)]
        frames.append((
            round(dx + (next_dx - dx) * TRANSIT_OFFSET),
            round(dy + (next_dy - dy) * TRANSIT_OFFSET) - 4,
            0,
            1,
        ))
    return frames


FRAMES = build_frame_table()


def eye_masks(rgba):
    lum = rgba[..., :3].mean(axis=2)
    light = (lum > 150) & (rgba[..., 3] > 128)
    lab, n = ndimage.label(light)
    sizes = ndimage.sum(light, lab, range(1, n + 1))
    eyes = []
    for index in np.argsort(sizes)[::-1]:
        comp = index + 1
        ys, xs = np.where(lab == comp)
        # 얼굴 상단의 좌우 대칭 흰 영역 두 개가 눈이다.
        if 330 <= ys.min() <= 360 and 600 <= ys.max() <= 640 and sizes[index] > 40_000:
            eyes.append(((xs.min(), xs.max(), ys.min(), ys.max()), lab == comp))
        if len(eyes) == 2:
            break
    eyes.sort(key=lambda item: item[0][0])
    return eyes


def pupil_centers(rgba):
    lum = rgba[..., :3].mean(axis=2)
    dark = (lum < 110) & (rgba[..., 3] > 128)
    lab, n = ndimage.label(dark)
    found = []
    for comp in range(1, n + 1):
        ys, xs = np.where(lab == comp)
        if 500 < len(ys) < 2_000 and ys.mean() < 700:
            found.append((xs.mean(), ys.mean()))
    found.sort()
    return found


def lid_curve(mask, x0, x1, ratio):
    """열별 눈 안쪽 위/아래 경계에서 원본 윗선과 평행한 눈꺼풀 곡선을 만든다."""
    columns, tops, lids = [], [], []
    for x in range(x0, x1 + 1):
        rows = np.where(mask[:, x])[0]
        if rows.size < 30:
            continue
        top, bottom = rows.min(), rows.max()
        columns.append(x)
        tops.append(top)
        lids.append(top + (bottom - top) * ratio)
    if len(columns) < 30:
        raise SystemExit("lid curve failed")
    # 원본 윗선 기울기를 따르는 직선 눈꺼풀로 맞춘다. 물결지면 주름처럼 보인다.
    slope, intercept = np.polyfit(columns, lids, 1)
    straight = slope * np.array(columns, dtype=float) + intercept
    return dict(zip(columns, straight)), dict(zip(columns, tops))


def draw_furrow(draw, eyes, level):
    """두 눈 사이에 아래로 모이는 미간 주름 두 줄을 그린다.

    좌표는 검출한 눈 안쪽 경계에서 계산한다. 눈 사이 여유 폭은 아래로 갈수록
    좁아지므로 주름도 아래에서 모이게 해야 외곽선을 넘지 않는다.
    """
    settings = FURROW_LEVELS[level]
    (left_bounds, _), (right_bounds, _) = eyes
    inner_left, inner_right = left_bounds[1], right_bounds[0]
    center = (inner_left + inner_right) / 2
    half_gap = (inner_right - inner_left) / 2 * settings["spread"]
    # 이마에서 시작해 두 눈 사이 좁은 골까지 길게 내려야 주름으로 읽힌다.
    top = min(left_bounds[2], right_bounds[2]) - 45 + settings["top_drop"]
    bottom = top + 210 - settings["top_drop"]

    for side in (-1, 1):
        draw.line(
            [
                (center + side * half_gap * 0.64, top),
                (center + side * half_gap * 0.44, (top + bottom) / 2),
                (center + side * half_gap * 0.28, bottom),
            ],
            fill=INK,
            width=settings["thickness"],
            joint="curve",
        )


def build_base(image, level):
    """원본 눈동자를 지우고 눈꺼풀과 해당 단계의 미간을 그린 바탕을 만든다."""
    rgba = np.array(image)
    eyes = eye_masks(rgba)
    pupils = pupil_centers(rgba)
    if len(eyes) != 2 or len(pupils) != 2:
        raise SystemExit(f"eye/pupil detection failed: eyes={len(eyes)} pupils={len(pupils)}")

    canvas = image.copy()
    draw = ImageDraw.Draw(canvas)
    draw_furrow(draw, eyes, level)
    interiors = []

    for (bounds, mask), (px, py) in zip(eyes, pupils):
        x0, x1, y0, y1 = bounds
        # 1) 기존 눈동자를 흰 눈 안쪽 색으로 덮는다.
        draw.ellipse([px - 30, py - 30, px + 30, py + 30], fill=SKIN)

        # 2) 눈꺼풀 위쪽 눈 안쪽을 얼굴과 같은 흰색으로 덮는다.
        lid, tops = lid_curve(mask, x0, x1, FURROW_LEVELS[level]["lid"])
        for x, lid_y in lid.items():
            draw.line([(x, tops[x] - 1), (x, lid_y)], fill=SKIN)

        # 3) 원본 외곽선과 같은 두께의 눈꺼풀 선을 한 번에 그린다.
        points = [(x, float(lid[x])) for x in sorted(lid)]
        draw.line(points, fill=INK, width=16, joint="curve")

        interiors.append((mask, lid))

    return canvas, pupils, interiors


def fits(mask, lid, cx, cy):
    """눈동자 원이 눈 안쪽과 눈꺼풀 아래에 완전히 들어가는지 본다."""
    margin = PUPIL_RADIUS + 3
    for angle in range(0, 360, 15):
        x = int(round(cx + margin * np.cos(np.radians(angle))))
        y = int(round(cy + margin * np.sin(np.radians(angle))))
        if not (0 <= y < mask.shape[0] and 0 <= x < mask.shape[1]) or not mask[y, x]:
            return False
        if x in lid and y < lid[x] + 10:
            return False
    return True


def clamp_pupil(mask, lid, cx, cy):
    """목표 위치가 눈 밖이면 가장 가까운 눈 안쪽 위치로 당긴다."""
    if fits(mask, lid, cx, cy):
        return cx, cy
    best, best_distance = (cx, cy), None
    for step_x in range(-60, 61, 2):
        for step_y in range(-40, 41, 2):
            x, y = cx + step_x, cy + step_y
            if not fits(mask, lid, x, y):
                continue
            distance = step_x ** 2 + step_y ** 2
            if best_distance is None or distance < best_distance:
                best, best_distance = (x, y), distance
    return best


def draw_pupils(canvas, pupils, interiors, dx, dy):
    frame = canvas.copy()
    draw = ImageDraw.Draw(frame)
    for (px, py), (mask, lid) in zip(pupils, interiors):
        cx, cy = clamp_pupil(mask, lid, px + dx, py + dy)
        draw.ellipse(
            [cx - PUPIL_RADIUS, cy - PUPIL_RADIUS, cx + PUPIL_RADIUS, cy + PUPIL_RADIUS],
            fill=INK,
        )
    return frame


def main(out_path, frame_width=186, frame_height=208, preview=False):
    """96x104 표시 영역의 2배 해상도로 가로 스트립을 만든다."""
    image = Image.open(BASE).convert("RGBA")
    bases = {level: build_base(image, level) for level in FURROW_LEVELS}

    strip = Image.new("RGBA", (frame_width * len(FRAMES), frame_height), (0, 0, 0, 0))
    for index, (dx, dy, level, _hold) in enumerate(FRAMES):
        canvas, pupils, interiors = bases[level]
        frame = draw_pupils(canvas, pupils, interiors, dx, dy)
        frame = frame.resize((frame_width, frame_height), Image.LANCZOS)
        strip.alpha_composite(frame, (index * frame_width, 0))
    strip.save(out_path, optimize=True)

    holds = [hold for *_, hold in FRAMES]
    print(f"wrote {strip.size[0]}x{strip.size[1]} strip with {len(FRAMES)} frames to {out_path}")
    print(f"holds={holds} -> {sum(holds)} ticks, {sum(holds) * 0.12:.1f}s per loop at 120ms")

    if preview:
        for level in FURROW_LEVELS:
            canvas, pupils, interiors = bases[level]
            full = draw_pupils(canvas, pupils, interiors, -42, 0)
            full.crop((150, 250, 1050, 700)).save(f"_preview-eyes-{level}.png")
            small = full.resize((93, 104), Image.LANCZOS)
            small.resize((372, 416), Image.NEAREST).save(f"_preview-onscreen-{level}.png")


if __name__ == "__main__":
    main(sys.argv[1], preview="--preview" in sys.argv)
