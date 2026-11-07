"""Build the native 256 frontal hoodie.

The master is the supplied 256 painting, not a scaled 512. The gray
background is flooded off. Mouth and eyelids are measured on this image.
The closed frame is empty, so rest tracking matches the cutout exactly.
Yaw, pitch, and a separate hair layer are not invented: this file is one
painted layer. Generated concept art, not a hand drawing.
"""
from pathlib import Path
from collections import deque
import math
import json
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SRC = Path('/tmp/rowdy256/neutral-256.png')
OUT = ROOT / 'assets' / 'male256'
BG = np.array([91, 91, 91])

# Darker-than-skin smile on neutral-256.png. x=129..131 is bare skin.
MEASURED = {
    121: (124, 125),
    122: (124, 125),
    **{x: (125, 125) for x in range(123, 129)},
    **{x: (124, 124) for x in range(132, 138)},
    138: (123, 124),
    139: (123, 123),
    140: (122, 123),
}
for _x, _t in ((129, 0.33), (130, 0.66), (131, 1.0)):
    _y = int(round(125 + (124 - 125) * _t))
    MEASURED[_x] = (_y, _y)
X0, X1 = 121, 140

LIP = (208, 125, 85)
LIP_MID = (167, 104, 77)
LIP_DARK = (125, 64, 46)
CORNER = (78, 49, 37)
CAVITY = (92, 44, 38)
CAVITY_DEEP = (62, 32, 28)
TOOTH = (243, 224, 206)
TONGUE = (210, 112, 82)
TONGUE_SHADE = (176, 86, 64)
SCLERA = (243, 212, 180)

APERTURE = 9
SHAPES = 5

EYE_WINDOWS = {
    'L': dict(x0=96, x1=118, y0=90, y1=110, top_lo=93, top_hi=102),
    'R': dict(x0=140, x1=168, y0=84, y1=108, top_lo=86, top_hi=98),
}
BROWS = {
    'L': {'x0': 98, 'y0': 86, 'x1': 122, 'y1': 95},
    'R': {'x0': 142, 'y0': 82, 'x1': 168, 'y1': 93},
}
BOXES = {
    'L': {'x0': 96, 'y0': 88, 'x1': 120, 'y1': 110},
    'R': {'x0': 140, 'y0': 82, 'x1': 166, 'y1': 108},
}


def flood_cutout(rgb, tol=30):
    h, w = rgb.shape[:2]
    seen = np.zeros((h, w), bool)
    bg = np.zeros((h, w), bool)
    q = deque()
    for x in range(w):
        q.append((0, x))
        q.append((h - 1, x))
    for y in range(h):
        q.append((y, 0))
        q.append((y, w - 1))
    while q:
        y, x = q.popleft()
        if y < 0 or x < 0 or y >= h or x >= w or seen[y, x]:
            continue
        seen[y, x] = True
        if np.abs(rgb[y, x].astype(int) - BG).sum() > tol:
            continue
        bg[y, x] = True
        q.extend(((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)))
    out = np.zeros((h, w, 4), np.uint8)
    out[:, :, :3] = rgb
    out[:, :, 3] = np.where(bg, 0, 255)
    return out


def is_dark(rgb):
    r, g, b = int(rgb[0]), int(rgb[1]), int(rgb[2])
    return r < 90 and g < 70 and b < 65


def is_cheek(rgb):
    r, g, b = int(rgb[0]), int(rgb[1]), int(rgb[2])
    return r > 235 and g > 185 and b > 145


def is_skin(rgb):
    r, g, b = int(rgb[0]), int(rgb[1]), int(rgb[2])
    return r > 220 and g > 170 and b > 130 and g > b


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


def skin_at(neu, x, y):
    h, w = neu.shape[:2]
    for dy in range(2, 8):
        yy = y - dy
        if 0 <= yy < h and 0 <= x < w and is_skin(neu[yy, x]):
            return tuple(int(v) for v in neu[yy, x][:3])
    return (247, 195, 153)


def ellipse_bow(u):
    x = abs(2 * u - 1)
    if x >= 1:
        return 0.0
    return math.sqrt(max(0.0, 1 - x * x))


def shape_params(si, ai):
    t = ai / (APERTURE - 1)
    s = (si - 2) / 2
    extra = int(round(t * (1 + s * 2)))
    gap = int(round(t * (8 - max(0, s) * 2 + max(0, -s))))
    lift = int(round(max(0, s) * t))
    return extra, max(0, gap), lift


def put(patch, x, y, rgb):
    h, w = patch.shape[:2]
    if 0 <= x < w and 0 <= y < h:
        patch[y, x] = (rgb[0], rgb[1], rgb[2], 255)


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
        y_split = smile_bot(x)
        on_smile = X0 <= x <= X1
        if on_smile and extra >= 0 and y_split > smile_top(x) and open_px > 0 and abs(y_anchor - smile_top(x)) <= 1:
            interior_y = y_split
        else:
            interior_y = y_anchor + 1
        at_end = bow < 0.22
        if open_px <= 0:
            continue
        if not on_smile or at_end or x not in MEASURED or MEASURED[x][0] != y_anchor:
            col = CORNER if at_end or bow < 0.3 else (LIP_MID if gap >= 5 and bow > 0.5 else LIP)
            put(patch, x, y_anchor, col)
        elif gap >= 6 and bow > 0.6:
            put(patch, x, y_anchor, LIP_MID)
        covered.add((x, y_anchor))
        for k in range(open_px):
            put(patch, x, interior_y + k, shade(u, k, open_px, gap, at_end, s))
            covered.add((x, interior_y + k))
        lip_n = 2 if open_px >= 4 else 1
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
    if extra < 0 or lift > 0:
        for x, (y0, y1) in MEASURED.items():
            for y in range(y0, y1 + 1):
                if (x, y) not in covered and left - 1 <= x <= right + 1:
                    put(patch, x, y, skin_at(neu, x, y))
    return patch


def shade(u, depth, open_px, gap, at_end, shape):
    if at_end or depth == 0:
        return CORNER if at_end else LIP_DARK
    if gap >= 5 and open_px >= 4 and depth == 1 and abs(u - 0.5) < 0.12 + 0.16 * min(1, (gap - 5) / 3):
        return TOOTH
    if gap >= 5 and open_px >= 4:
        tongue_h = min(open_px - 2, max(1, gap - 4))
        start = open_px - tongue_h
        half = 0.18 + 0.06 * max(0, shape)
        if depth >= start and abs(u - 0.5) <= half:
            return TONGUE_SHADE if depth == start or abs(u - 0.5) > half - 0.05 else TONGUE
    return CAVITY if depth <= 2 else CAVITY_DEEP


def smooth(vals, radius=2):
    out = []
    for i in range(len(vals)):
        sl = vals[max(0, i - radius):i + radius + 1]
        out.append(int(round(sum(sl) / len(sl))))
    return out


# Measured on neutral-256. Center of each eye is higher; corners sit lower.
EYE_CURVES = {
    'L': dict(x0=98, x1=118, top_mid=94, top_end=100, bot_mid=107, bot_end=103),
    'R': dict(x0=142, x1=164, top_mid=86, top_end=93, bot_mid=107, bot_end=101),
}


def eye_columns(neu):
    eyes = {}
    for side, c in EYE_CURVES.items():
        cols = []
        span = max(1, c['x1'] - c['x0'])
        for x in range(c['x0'], c['x1'] + 1):
            bow = math.sin(math.pi * (x - c['x0']) / span)
            top = int(round(c['top_end'] + (c['top_mid'] - c['top_end']) * bow))
            bot = int(round(c['bot_end'] + (c['bot_mid'] - c['bot_end']) * bow))
            skin_y = max(0, top - 2)
            skin = tuple(int(v) for v in neu[skin_y, x][:3])
            if is_dark(skin) or skin[2] < 140:
                skin = (247, 195, 153)
            cols.append({'x': x, 'top': top, 'bot': max(top + 4, bot), 'skin': skin})
        eyes[side] = cols
    return eyes


def row_skin(neu, y, x0, x1):
    h, w = neu.shape[:2]
    y = max(0, min(h - 1, y))
    for d in range(1, 14):
        for xx in (x0 - d, x1 + d):
            if 0 <= xx < w and (is_cheek(neu[y, xx]) or is_skin(neu[y, xx])):
                return tuple(int(v) for v in neu[y, xx][:3])
    return (247, 195, 153)


def mix(a, b, t):
    t = max(0.0, min(1.0, t))
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


def build_lid(neu, level, happy, columns):
    h, w = neu.shape[:2]
    patch = np.zeros((h, w, 4), np.uint8)
    if level <= 0:
        return patch
    t = level / 4
    for cols in columns.values():
        if not cols:
            continue
        x0, x1 = cols[0]['x'], cols[-1]['x']
        planned = []
        for info in cols:
            u = 0 if x1 == x0 else (info['x'] - x0) / (x1 - x0)
            span = max(3, info['bot'] - info['top'])
            if happy:
                base, curve = 0.42, -int(round(math.sin(math.pi * u) * (1 + 2 * t)))
            else:
                base, curve = 0.78, int(round(math.sin(math.pi * u) * (1 + t)))
            y_closed = info['top'] + int(round(span * base)) + curve
            y_lid = info['top'] + int(round(t * (y_closed - info['top'])))
            y_lid = max(info['top'], min(info['bot'] - 1, y_lid))
            planned.append(y_lid)
        planned = smooth(planned, 1)
        for info, y_lid in zip(cols, planned):
            y_lid = max(info['top'], min(info['bot'] - 1, y_lid))
            x = info['x']
            for y in range(info['top'], y_lid):
                put(patch, x, y, row_skin(neu, y, x0, x1))
            put(patch, x, y_lid, (41, 30, 24))
            if t >= 0.97:
                for y in range(y_lid + 1, info['bot'] + 1):
                    put(patch, x, y, row_skin(neu, y, x0, x1))
                put(patch, x, y_lid, (41, 30, 24))
    return patch


def build_iris(neu, columns):
    h, w = neu.shape[:2]
    iris = np.zeros((h, w, 4), np.uint8)
    for cols in columns.values():
        for info in cols:
            x = info['x']
            for y in range(info['top'] + 1, info['bot']):
                r, g, b = [int(v) for v in neu[y, x][:3]]
                if r > 160 and 70 < g < 180 and b < 150 and r > g + 8 and not is_skin(neu[y, x]):
                    iris[y, x] = (r, g, b, 255)
    return iris


def main():
    rgb = np.asarray(Image.open(SRC).convert('RGB'))
    neu = flood_cutout(rgb)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'ref').mkdir(exist_ok=True)
    Image.fromarray(neu).save(OUT / 'neutral.png')
    Image.open('/tmp/rowdy256/neutral-256.png').save(OUT / 'ref' / 'neutral-256.png')
    Image.open('/tmp/rowdy256/neutral-preview-1024.png').save(OUT / 'ref' / 'neutral-preview-1024.png')
    Image.open('/tmp/rowdy256/generated-original-1024.jpg').save(OUT / 'ref' / 'generated-original-1024.jpg')
    expr = OUT / 'expr'
    expr.mkdir(exist_ok=True)
    names = []
    for ai in range(APERTURE):
        for si in range(SHAPES):
            patch = build_mouth(neu, si, ai)
            name = f'm-{ai:02d}-{si}.png'
            Image.fromarray(patch).save(expr / name)
            names.append(f'expr/{name}')
    columns = eye_columns(neu)
    for side, cols in columns.items():
        if cols:
            print(side, 'x', cols[0]['x'], cols[-1]['x'], 'n', len(cols),
                  'mid', cols[len(cols) // 2]['top'], cols[len(cols) // 2]['bot'])
        else:
            print(side, 'EMPTY')
    for style, happy in (('n', False), ('h', True)):
        for level in range(5):
            Image.fromarray(build_lid(neu, level, happy, columns)).save(expr / f'lid-{style}-{level}.png')
    iris = build_iris(neu, columns)
    Image.fromarray(iris).save(OUT / 'iris.png')
    print('iris', int((iris[:, :, 3] > 0).sum()), 'opaque', int((neu[:, :, 3] > 0).sum()))
    manifest = {
        'name': '악동 후디 256',
        'S': 256,
        'mode': 'fine',
        'art': 'portrait',
        'renderer': 'front',
        'artRevision': 'rowdy-256',
        'sourceNote': 'Generated concept painting supplied as neutral-256.png. Not hand-drawn.',
        'texture': 'neutral.png',
        'mouths': names,
        'mouthGrid': {'aperture': APERTURE, 'shapes': SHAPES},
        'lids': {
            'neutral': [f'expr/lid-n-{i}.png' for i in range(5)],
            'happy': [f'expr/lid-h-{i}.png' for i in range(5)],
        },
        'iris': 'iris.png',
        'sclera': list(SCLERA),
        'boxes': BOXES,
        'brows': BROWS,
        'layers': [],
        'regions': {'mouth': [X0 - 4, 118, X1 + 6, 136]},
        'track': {
            'S': 256,
            'gazePx': 1,
            'gazePy': 1,
            'browPx': 1,
            'blinkCompress': 0.92,
            'poseHoldMs': 40,
        },
        'note': 'Native 256 frontal hoodie. Mouth and lids are measured on this painting. Head angles are not drawn. Cheek puff is not drawn. Generated concept, not hand-drawn.',
    }
    (OUT / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print('mouths', len(names))


if __name__ == '__main__':
    main()
