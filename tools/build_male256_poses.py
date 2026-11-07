"""Distinct 256 mouth poses. The resting frame is empty.

Open shapes do not keep the original smirk. Each family has its own
corners, width, and curve. The old smile pixels are covered when a new
shape is drawn, so a second mouth does not sit under the first.
"""
from pathlib import Path
import json
import math
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
NEU_PATH = ROOT / 'assets' / 'male256' / 'neutral.png'
OUT = ROOT / 'assets' / 'male256' / 'expr'
MANIFEST = ROOT / 'assets' / 'male256' / 'manifest.json'

# Painted smile on the 256 master. Covered when any other pose is shown.
SMILE = {
    121: (124, 125), 122: (124, 125),
    **{x: (125, 125) for x in range(123, 129)},
    129: (125, 125), 130: (125, 125), 131: (124, 124),
    **{x: (124, 124) for x in range(132, 138)},
    138: (123, 124), 139: (123, 123), 140: (122, 123),
}

LIP = (208, 125, 85)
LIP_MID = (167, 104, 77)
LIP_DARK = (101, 61, 45)
CORNER = (78, 49, 37)
CAVITY = (78, 36, 32)
TOOTH = (243, 226, 210)
TONGUE = (210, 112, 82)
TONGUE_EDGE = (176, 86, 64)


def is_skin(rgb):
    r, g, b = int(rgb[0]), int(rgb[1]), int(rgb[2])
    return r > 220 and g > 170 and b > 130 and g + 5 > b


def skin_at(neu, x, y):
    h, w = neu.shape[:2]
    for dy in range(2, 7):
        yy = y - dy
        if 0 <= yy < h and 0 <= x < w and is_skin(neu[yy, x]):
            return tuple(int(v) for v in neu[yy, x][:3])
    return (247, 195, 153)


def put(patch, x, y, rgb):
    h, w = patch.shape[:2]
    if 0 <= x < w and 0 <= y < h:
        patch[y, x] = (int(rgb[0]), int(rgb[1]), int(rgb[2]), 255)


def cover_smile(patch, neu):
    for x, (y0, y1) in SMILE.items():
        for y in range(y0, y1 + 1):
            put(patch, x, y, skin_at(neu, x, y))


def bow(u, kind):
    if u <= 0 or u >= 1:
        return 0.0
    if kind in ('O', 'pucker'):
        x = abs(2 * u - 1)
        return math.sqrt(max(0.0, 1 - x * x))
    # A lens, not a flat-bottomed slot.
    return math.sin(math.pi * u) ** (0.75 if kind == 'I' else 1.0)


def spec_for(kind, t, asym):
    """Corners and opening. asym -1/0/1 lifts one corner."""
    a = int(asym)
    if kind == 'press':
        inset = int(round((1 - t) * 4))
        return dict(x0=116 + inset, x1=144 - inset, yL=126, yR=126, yC=126, drop=0, thick=1 if t > 0.8 else 2, teeth=False, tongue=False)
    if kind == 'part':
        return dict(x0=118, x1=142, yL=126 + a, yR=126 - a, yC=125, drop=2 + int(round(t * 2)), thick=1, teeth=False, tongue=False)
    if kind == 'A':
        return dict(x0=118, x1=142, yL=126 + a, yR=126 - a, yC=123, drop=6 + int(round(t * 8)), thick=1, teeth=t > 0.5, tongue=t > 0.7)
    if kind == 'O':
        half = 5 + int(round(t * 4))
        return dict(x0=130 - half, x1=130 + half, yL=125, yR=125, yC=124, drop=half + 2, thick=2, teeth=False, tongue=t > 0.55)
    if kind == 'pucker':
        half = 3 + int(round(t * 2))
        return dict(x0=130 - half, x1=130 + half, yL=124, yR=124, yC=123, drop=max(2, half), thick=3, teeth=False, tongue=False)
    if kind == 'I':
        extra = int(round(t * 6))
        return dict(x0=110 - extra, x1=150 + extra, yL=125, yR=125, yC=125, drop=2 + int(round(t * 2)), thick=1, teeth=False, tongue=False)
    if kind == 'smile':
        return dict(x0=108, x1=152, yL=120 + a, yR=120 - a, yC=126, drop=2 + int(round(t * 6)), thick=1, teeth=t > 0.35, tongue=t > 0.7)
    if kind == 'laugh':
        return dict(x0=104, x1=156, yL=118 + a, yR=118 - a, yC=125, drop=8 + int(round(t * 4)), thick=1, teeth=True, tongue=True)
    raise KeyError(kind)


def y_upper(x, s):
    span = max(1, s['x1'] - s['x0'])
    u = (x - s['x0']) / span
    y_edge = s['yL'] + (s['yR'] - s['yL']) * u
    bell = 1 - (2 * u - 1) ** 2
    y_mid = (s['yL'] + s['yR']) / 2
    return int(round(y_edge + (s['yC'] - y_mid) * bell))


def build(neu, kind, t, asym):
    h, w = neu.shape[:2]
    patch = np.zeros((h, w, 4), np.uint8)
    if kind == 'rest':
        return patch
    cover_smile(patch, neu)
    s = spec_for(kind, t, asym)
    x0, x1 = s['x0'], s['x1']
    thick = s['thick']
    for x in range(x0, x1 + 1):
        span = max(1, x1 - x0)
        u = (x - x0) / span
        b = bow(u, kind)
        yu = y_upper(x, s)
        at_end = u < 0.08 or u > 0.92
        if s['drop'] <= 0 or b < 0.08:
            col = CORNER if at_end else LIP_DARK
            for k in range(thick):
                put(patch, x, yu + k, col if k == 0 else LIP)
            continue
        inner = max(1, int(round(s['drop'] * b)))
        for k in range(thick):
            put(patch, x, yu - (thick - 1 - k), CORNER if at_end else (LIP_DARK if k == thick - 1 else LIP_MID))
        for k in range(inner):
            put(patch, x, yu + 1 + k, interior(u, k, inner, s, at_end))
        for k in range(thick):
            put(patch, x, yu + 1 + inner + k, CORNER if at_end else (LIP if k == thick - 1 else LIP_DARK))
    return patch


def interior(u, depth, inner, s, at_end):
    if at_end:
        return CORNER
    if s['teeth'] and depth == 0 and 0.32 < u < 0.68 and inner >= 4:
        return TOOTH
    if s['tongue'] and inner >= 5:
        tongue_h = max(1, inner // 3)
        if depth >= inner - tongue_h and abs(u - 0.5) < 0.22:
            return TONGUE_EDGE if depth == inner - tongue_h or abs(u - 0.5) > 0.14 else TONGUE
    return CAVITY


def poses():
    out = [('rest', 0, 0)]
    for t in (0.4, 0.75, 1.0):
        out.append(('press', t, 0))
    for t in (0.3, 0.55, 0.8):
        out.append(('part', t, 0))
    for t in (0.35, 0.6, 0.85, 1.0):
        out.append(('A', t, 0))
    for t in (0.6, 1.0):
        out.append(('A', t, -1))
        out.append(('A', t, 1))
    for t in (0.35, 0.6, 0.85, 1.0):
        out.append(('O', t, 0))
    for t in (0.4, 0.7, 1.0):
        out.append(('pucker', t, 0))
    for t in (0.35, 0.6, 0.85, 1.0):
        out.append(('I', t, 0))
    for t in (0.25, 0.5, 0.75, 1.0):
        out.append(('smile', t, 0))
    for t in (0.5, 1.0):
        out.append(('smile', t, -1))
        out.append(('smile', t, 1))
    for t in (0.55, 0.8, 1.0):
        out.append(('laugh', t, 0))
    for t in (0.8, 1.0):
        out.append(('laugh', t, -1))
        out.append(('laugh', t, 1))
    return out


def main():
    neu = np.asarray(Image.open(NEU_PATH).convert('RGBA'))
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob('m-*.png'):
        old.unlink()
    for old in OUT.glob('pose-*.png'):
        old.unlink()
    records = []
    for kind, t, asym in poses():
        tag = {0: 'c', -1: 'l', 1: 'r'}[asym]
        name = f'pose-{kind}-{int(round(t * 100)):02d}-{tag}.png'
        Image.fromarray(build(neu, kind, t, asym)).save(OUT / name)
        records.append({'id': kind, 'open': t, 'asym': asym, 'file': f'expr/{name}'})
        if asym == 0:
            n = int((np.asarray(Image.open(OUT / name))[:, :, 3] > 0).sum())
            print(f'{name} px {n}')
    manifest = json.loads(MANIFEST.read_text())
    manifest['mouths'] = [r['file'] for r in records]
    manifest['mouthPoses'] = records
    manifest.pop('mouthGrid', None)
    manifest['mouthModel'] = 'poses'
    manifest['note'] = (
        'Native 256 frontal hoodie. Mouth poses are separate shapes '
        '(rest, press, part, A, O, pucker, I, smile, laugh), not one smile stretched. '
        'Rest matches the painting. Head angles are not drawn. Cheek puff is not drawn. '
        'Generated concept, not hand-drawn.'
    )
    MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')
    print('poses', len(records))


if __name__ == '__main__':
    main()
