"""Open the painted smile instead of stamping a second mouth.

Frame 0 is empty, so rest tracking stays the neutral painting. Later frames
split that same lip: the top pixel stays, the lower pixel becomes the
interior, and a lower lip of the same color moves down. Teeth stay one pixel
tall. The tongue grows one pixel at a time from the lower lip. Nothing here
scales a painted patch.
"""
from pathlib import Path
import math
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
NEUTRAL = ROOT / 'assets' / 'male1' / 'neutral.png'
OUT = ROOT / 'assets' / 'male1'

# Top and bottom of the real darker-than-skin smile on neutral.png.
# x=255..263 has no dark pixel; those rows are filled by interpolation.
MEASURED = {
    240: (243, 244),
    241: (243, 245),
    242: (243, 245),
    243: (244, 245),
    **{x: (244, 245) for x in range(244, 253)},
    253: (244, 244),
    254: (244, 244),
    **{x: (243, 243) for x in range(264, 270)},
    **{x: (242, 243) for x in range(270, 274)},
    274: (240, 242),
    275: (240, 242),
    276: (240, 241),
    277: (240, 241),
    278: (239, 241),
    279: (239, 240),
}
X0, X1 = 240, 279

LIP = (222, 169, 133)
LIP_MID = (208, 144, 108)
LIP_IN = (150, 81, 63)
CAVITY = (110, 54, 41)
CORNER = (64, 46, 39)
TOOTH = (255, 232, 212)
TONGUE = (213, 118, 96)
TONGUE_SHADE = (186, 100, 80)
LOWER_IN = (180, 97, 72)

GAPS = list(range(23))
EXTRA = [min(5, i // 4) for i in GAPS]


def fill_span():
    tops, bots = {}, {}
    for x, (a, b) in MEASURED.items():
        tops[x], bots[x] = a, b
    for x in range(255, 264):
        t = (x - 254) / 10
        y = int(round(244 + (243 - 244) * t))
        tops[x] = bots[x] = y
    return tops, bots


TOP, BOT = fill_span()


def smile_top(x):
    if x < X0:
        return TOP[X0]
    if x > X1:
        return TOP[X1]
    return TOP[x]


def smile_bot(x):
    if x < X0:
        return BOT[X0]
    if x > X1:
        return BOT[X1]
    return BOT[x]


def lip_bow(u):
    # The whole lip parts together. Only the last pixels pinch into the corner.
    if u <= 0.06 or u >= 0.94:
        t = u / 0.06 if u < 0.5 else (1 - u) / 0.06
        return max(0.0, min(1.0, t))
    mid = (u - 0.5) / 0.5
    return 0.86 + 0.14 * (1 - mid * mid)


def build(gap, extra, neutral):
    patch = np.zeros_like(neutral)
    if gap <= 0:
        return patch
    left, right = X0 - extra, X1 + extra
    span = max(1, right - left)
    for x in range(left, right + 1):
        u = (x - left) / span
        bow = lip_bow(u)
        open_px = int(round(gap * bow))
        y_top = smile_top(x)
        y_bot = smile_bot(x)
        at_end = x <= left + 1 or x >= right - 1
        on_smile = X0 <= x <= X1
        # Keep a 1px upper lip. A thicker painted lip gives its lower pixel to the opening.
        if on_smile and y_bot > y_top:
            interior_y = y_bot
        else:
            interior_y = y_top + 1
        if open_px <= 0:
            continue
        # New width grows from the corner. It is attached to the opening below.
        if not on_smile:
            put(patch, x, y_top, CORNER)
        # Center of the closed smile is bare skin. Draw the same lip color there
        # so the two sides stay one mouth once it parts.
        elif x not in MEASURED:
            put(patch, x, y_top, LIP if bow > 0.2 else CORNER)
        for k in range(open_px):
            col = shade(u, k, open_px, at_end or bow < 0.2)
            put(patch, x, interior_y + k, col)
        lip_rows = 2 if open_px >= 5 else 1
        for k in range(lip_rows):
            y = interior_y + open_px + k
            if at_end or bow < 0.2:
                put(patch, x, y, CORNER)
            elif lip_rows == 2 and k == 0:
                put(patch, x, y, LOWER_IN)
            else:
                put(patch, x, y, LIP_MID if bow < 0.55 else LIP)
    return patch


def shade(u, depth, open_px, at_end):
    if at_end:
        return CORNER
    tongue_h = 0 if open_px < 6 else (open_px - 5)
    tongue_h = min(tongue_h, max(0, open_px - 2))
    tongue_at = open_px - tongue_h
    if depth == 0:
        return LIP_IN
    # Teeth are one pixel tall and widen across a few frames inside the open mouth.
    if depth == 1 and open_px >= 9:
        half = 0.08 + 0.22 * min(1, (open_px - 9) / 3)
        if abs(u - 0.5) < half:
            return TOOTH
    if tongue_h and depth >= tongue_at:
        edge = depth == tongue_at or depth == open_px - 1
        side = u < 0.38 or u > 0.62
        return TONGUE_SHADE if edge or side else TONGUE
    return CAVITY


def put(patch, x, y, rgb):
    h, w = patch.shape[:2]
    if 0 <= x < w and 0 <= y < h:
        patch[y, x] = (rgb[0], rgb[1], rgb[2], 255)


def main():
    neutral = np.asarray(Image.open(NEUTRAL).convert('RGBA'))
    OUT.mkdir(parents=True, exist_ok=True)
    for i, (gap, extra) in enumerate(zip(GAPS, EXTRA)):
        patch = build(gap, extra, neutral)
        name = f'mouth-{i:02d}.png'
        Image.fromarray(patch).save(OUT / name)
        n = int((patch[:, :, 3] > 0).sum())
        ys, xs = np.where(patch[:, :, 3] > 0)
        if len(xs):
            print(f'{name} px {n:4d} bb {xs.min()},{ys.min()} {xs.max()},{ys.max()} gap {gap} extra {extra}')
        else:
            print(f'{name} empty')
    print('count', len(GAPS))


if __name__ == '__main__':
    main()
