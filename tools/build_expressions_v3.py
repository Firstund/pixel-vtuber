"""Rounded mouth manifold and eyelid frames for the frontal male face.

The closed smile on neutral.png stays the lip anchor. Frame aperture 0 is
empty, so a resting face is the painting. Later frames open that same line
into an ellipse (speech), a wider smile, or a rounder O. Teeth follow the
upper curve. The tongue sits inside the opening and grows with it.

Eyelids are drawn on the open eye: the lash curve comes down, skin above it
is the pixel just above the original lash, and a full close hides the iris.
Happy eyes use an upward arc. Cheek puff is not drawn.
"""
from pathlib import Path
import math
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
NEUTRAL_PATH = ROOT / 'assets' / 'male1' / 'neutral.png'
OUT = ROOT / 'assets' / 'male1' / 'expr'

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
for x in range(255, 264):
    t = (x - 254) / 10
    y = int(round(244 + (243 - 244) * t))
    MEASURED[x] = (y, y)

EYES = {
    'L': (188, 176, 238, 214),
    'R': (268, 170, 322, 208),
}

LIP = (222, 169, 133)
LIP_MID = (190, 112, 86)
LIP_DARK = (132, 64, 52)
CORNER = (64, 46, 39)
CAVITY = (96, 44, 38)
CAVITY_DEEP = (72, 34, 30)
TOOTH = (255, 236, 220)
TOOTH_SHADE = (232, 206, 186)
TONGUE = (214, 120, 98)
TONGUE_LIGHT = (226, 146, 122)
TONGUE_SHADE = (180, 96, 80)

APERTURE = 13
SHAPES = 5


def smile_top(x):
    if x < X0:
        return MEASURED[X0][0]
    if x > X1:
        return MEASURED[X1][0]
    return MEASURED[x][0]


def smile_bot(x):
    if x < X0:
        return MEASURED[X0][1]
    if x > X1:
        return MEASURED[X1][1]
    return MEASURED[x][1]


def is_skin(rgb):
    r, g, b = int(rgb[0]), int(rgb[1]), int(rgb[2])
    return r > 226 and g > 175 and b > 140 and (r - b) < 100 and g > b


def skin_at(neu, x, y):
    h, w = neu.shape[:2]
    for dy in range(2, 8):
        yy = y - dy
        if 0 <= yy < h and 0 <= x < w and is_skin(neu[yy, x]):
            return tuple(int(v) for v in neu[yy, x][:3])
    return (248, 204, 169)


def ellipse_bow(u):
    x = abs(2 * u - 1)
    if x >= 1:
        return 0.0
    return math.sqrt(max(0.0, 1 - x * x))


def shape_params(si, ai):
    """si 0..4 is O, mild O, speech, mild smile, wide smile."""
    t = ai / (APERTURE - 1)
    s = (si - 2) / 2  # -1 .. 1
    extra = int(round(t * (3 + s * 6)))
    gap = int(round(t * (15 - max(0, s) * 3 + max(0, -s) * 2)))
    lift = int(round(max(0, s) * t * 2))
    return extra, max(0, gap), lift


def build_mouth(neu, si, ai):
    h, w = neu.shape[:2]
    patch = np.zeros((h, w, 4), np.uint8)
    if ai <= 0:
        return patch
    extra, gap, lift = shape_params(si, ai)
    s = (si - 2) / 2
    left, right = X0 - extra, X1 + extra
    span = max(1, right - left)
    covered = set()
    for x in range(left, right + 1):
        u = (x - left) / span
        bow = ellipse_bow(u)
        open_px = int(round(gap * bow))
        end_w = max(0.0, 1 - bow)
        y_anchor = smile_top(x) - int(round(lift * end_w))
        y_bot_smile = smile_bot(x)
        on_smile = X0 <= x <= X1
        # Split a 2px smile. A 1px smile stays and the hole starts under it.
        if on_smile and extra >= 0 and y_bot_smile > smile_top(x) and open_px > 0 and abs(y_anchor - smile_top(x)) <= 1:
            interior_y = y_bot_smile
        else:
            interior_y = y_anchor + 1
        at_end = bow < 0.18
        if open_px <= 0:
            continue
        if not on_smile or at_end:
            put(patch, x, y_anchor, CORNER)
        elif x not in MEASURED or MEASURED[x][0] != y_anchor:
            # Bare center, or the lip moved. Draw the same lip color.
            col = LIP if bow > 0.35 else CORNER
            if gap >= 6 and bow > 0.45:
                col = LIP_MID
            put(patch, x, y_anchor, col)
        elif gap >= 8 and bow > 0.55:
            put(patch, x, y_anchor, LIP_MID)
        covered.add((x, y_anchor))
        for k in range(open_px):
            col = shade(u, k, open_px, gap, at_end, s)
            put(patch, x, interior_y + k, col)
            covered.add((x, interior_y + k))
        lip_n = 2 if open_px >= 5 else 1
        for k in range(lip_n):
            y = interior_y + open_px + k
            if at_end:
                col = CORNER
            elif lip_n == 2 and k == 0:
                col = LIP_DARK
            else:
                col = LIP if bow > 0.4 else LIP_MID
            put(patch, x, y, col)
            covered.add((x, y))
    # If the opening moved inside the old smile, cover the abandoned lip
    # with the skin above it so the old line does not sit beside the new one.
    if extra < 0 or lift > 0:
        for x, (y0, y1) in MEASURED.items():
            for y in range(y0, y1 + 1):
                if (x, y) in covered:
                    continue
                if left - 1 <= x <= right + 1:
                    put(patch, x, y, skin_at(neu, x, y))
    return patch


def shade(u, depth, open_px, gap, at_end, shape):
    if at_end:
        return CORNER
    if depth == 0:
        return LIP_DARK
    tooth = tooth_row(u, depth, open_px, gap)
    if tooth:
        return tooth
    tongue = tongue_at(u, depth, open_px, gap, shape)
    if tongue:
        return tongue
    if depth <= 2:
        return CAVITY
    return CAVITY_DEEP


def tooth_row(u, depth, open_px, gap):
    if gap < 8 or open_px < 6:
        return None
    # Widen across the upper curve over a few aperture steps. One pixel tall,
    # plus a second only in the middle of a large opening.
    widen = min(1.0, (gap - 8) / 4)
    half = 0.10 + 0.22 * widen
    if abs(u - 0.5) >= half:
        return None
    if depth == 1:
        return TOOTH
    if depth == 2 and gap >= 12 and abs(u - 0.5) < half * 0.55:
        return TOOTH_SHADE
    return None


def tongue_at(u, depth, open_px, gap, shape):
    if gap < 7 or open_px < 5:
        return None
    tongue_h = min(open_px - 3, max(1, gap - 6))
    start = open_px - tongue_h
    if depth < start:
        return None
    # Horizontal inset so the tongue never touches the corners.
    half = 0.16 + 0.10 * min(1, tongue_h / 8) + 0.04 * max(0, shape)
    if abs(u - 0.5) > half:
        return None
    edge = depth == start or abs(u - 0.5) > half - 0.05
    if depth > start + tongue_h * 0.45 and abs(u - 0.5) < half * 0.45:
        return TONGUE_LIGHT
    return TONGUE_SHADE if edge else TONGUE


def put(patch, x, y, rgb):
    h, w = patch.shape[:2]
    if 0 <= x < w and 0 <= y < h:
        patch[y, x] = (rgb[0], rgb[1], rgb[2], 255)


def is_dark(rgb):
    r, g, b = int(rgb[0]), int(rgb[1]), int(rgb[2])
    return r < 120 and g < 95 and b < 80


def is_cheek(rgb):
    r, g, b = int(rgb[0]), int(rgb[1]), int(rgb[2])
    return r > 242 and g > 198 and b > 160


def smooth_series(vals, radius=2):
    out = []
    for i in range(len(vals)):
        sl = vals[max(0, i - radius):i + radius + 1]
        out.append(int(round(sum(sl) / len(sl))))
    return out


def eye_columns(neu):
    """Smooth lash/bottom curves. Columns whose lash is outside the eye band are dropped."""
    bands = {
        'L': dict(x0=198, x1=234, y0=178, y1=214, top_lo=181, top_hi=192),
        'R': dict(x0=274, x1=318, y0=170, y1=208, top_lo=174, top_hi=186),
    }
    eyes = {}
    for side, b in bands.items():
        raw = []
        for x in range(b['x0'], b['x1'] + 1):
            top = None
            run = 0
            for y in range(b['y0'], b['y1']):
                if is_dark(neu[y, x]):
                    if top is None:
                        top = y
                    run += 1
                elif top is not None:
                    break
            if top is None or run < 3 or not (b['top_lo'] <= top <= b['top_hi']):
                continue
            # Skip the sclera just under the lash. The cheek below the iris
            # is the real bottom; the eye-white is higher and must stay inside.
            bot = top + run + 8
            for y in range(top + 14, min(b['y1'], top + 30)):
                if is_cheek(neu[y, x]):
                    bot = y - 1
                    break
                bot = y
            lash = tuple(int(v) for v in neu[top, x][:3])
            skin_y = max(0, top - 2)
            skin = tuple(int(v) for v in neu[skin_y, x][:3])
            if is_dark(skin) or not (skin[0] > 180):
                skin = (243, 205, 173)
            raw.append((x, top, bot, lash, skin))
        if len(raw) < 8:
            eyes[side] = []
            continue
        filled = []
        for i, p in enumerate(raw):
            if i:
                prev = raw[i - 1]
                for x in range(prev[0] + 1, p[0]):
                    t = (x - prev[0]) / (p[0] - prev[0])
                    top = int(round(prev[1] + (p[1] - prev[1]) * t))
                    bot = int(round(prev[2] + (p[2] - prev[2]) * t))
                    filled.append((x, top, bot, p[3], p[4]))
            filled.append(p)
        raw = filled
        tops = smooth_series([p[1] for p in raw], 3)
        bots = smooth_series([p[2] for p in raw], 3)
        eyes[side] = [
            {'x': p[0], 'top': tops[i], 'bot': max(tops[i] + 6, bots[i]), 'lash': p[3], 'skin': p[4]}
            for i, p in enumerate(raw)
        ]
    return eyes


def build_lid(neu, level, happy):
    """level 0..4. 0 is empty. 4 is a full close with no iris."""
    h, w = neu.shape[:2]
    patch = np.zeros((h, w, 4), np.uint8)
    if level <= 0:
        return patch
    t = level / 4
    for cols in eye_columns(neu).values():
        if not cols:
            continue
        x0, x1 = cols[0]['x'], cols[-1]['x']
        planned = []
        for info in cols:
            u = 0 if x1 == x0 else (info['x'] - x0) / (x1 - x0)
            span = max(4, info['bot'] - info['top'])
            if happy:
                base = 0.42
                curve = -int(round(math.sin(math.pi * u) * (2 + 3 * t)))
            else:
                base = 0.78
                curve = int(round(math.sin(math.pi * u) * (2 + 2 * t)))
            y_closed = info['top'] + int(round(span * base)) + curve
            y_lid = info['top'] + int(round(t * (y_closed - info['top'])))
            y_lid = max(info['top'] + (1 if 0 < t < 0.97 else 0), min(info['bot'] - 1, y_lid))
            planned.append(y_lid)
        planned = smooth_series(planned, 2)
        for info, y_lid in zip(cols, planned):
            y_lid = max(info['top'], min(info['bot'] - 1, y_lid))
            x = info['x']
            above = info['skin']
            below = row_skin(neu, min(neu.shape[0] - 1, info['bot'] + 2), x0, x1)
            for y in range(info['top'], y_lid):
                fade = 0 if y_lid == info['top'] else (y - info['top']) / (y_lid - info['top'])
                put(patch, x, y, mix(above, below, fade * 0.45))
            put(patch, x, y_lid, (54, 42, 37))
            if y_lid + 1 < info['bot']:
                put(patch, x, y_lid + 1, (84, 60, 50))
            if t >= 0.97:
                for y in range(y_lid + 2, info['bot'] + 3):
                    put(patch, x, y, below)
    return patch


def mix(a, b, t):
    t = max(0.0, min(1.0, t))
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


def row_skin(neu, y, x0, x1):
    h, w = neu.shape[:2]
    y = max(0, min(h - 1, y))
    for d in range(1, 18):
        for xx in (x0 - d, x1 + d):
            if 0 <= xx < w and (is_cheek(neu[y, xx]) or is_skin(neu[y, xx])):
                return tuple(int(v) for v in neu[y, xx][:3])
    return (248, 204, 169)


def main():
    neu = np.asarray(Image.open(NEUTRAL_PATH).convert('RGBA'))
    OUT.mkdir(parents=True, exist_ok=True)
    names = []
    for ai in range(APERTURE):
        for si in range(SHAPES):
            patch = build_mouth(neu, si, ai)
            name = f'm-{ai:02d}-{si}.png'
            Image.fromarray(patch).save(OUT / name)
            names.append(f'expr/{name}')
            if si in (0, 2, 4):
                n = int((patch[:, :, 3] > 0).sum())
                print(f'{name} px {n}')
    for style, happy in (('n', False), ('h', True)):
        for level in range(5):
            patch = build_lid(neu, level, happy)
            name = f'lid-{style}-{level}.png'
            Image.fromarray(patch).save(OUT / name)
            print(f'{name} px {int((patch[:, :, 3] > 0).sum())}')
    print('mouths', len(names))
    return names


if __name__ == '__main__':
    main()
