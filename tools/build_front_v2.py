"""Align front-v2 expression tiles onto neutral-work-512 and preview patches."""
import numpy as np
from PIL import Image

SRC = '/workspace/assets/male1/ref'
NEU_PATH = SRC + '/neutral-work-512.png'

def gray(arr):
    a = arr.astype(np.float64)
    return a[:, :, 0] * 0.3 + a[:, :, 1] * 0.5 + a[:, :, 2] * 0.2

def load(path):
    return np.asarray(Image.open(path).convert('RGB'))

def resize_nearest(arr, s):
    im = Image.fromarray(arr.astype(np.uint8) if arr.dtype != np.uint8 else arr)
    if arr.ndim == 2:
        im = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    w = max(8, int(round(im.width * s)))
    h = max(8, int(round(im.height * s)))
    return np.asarray(im.resize((w, h), Image.NEAREST))

def find_template(image, templ):
    t = templ.astype(np.float64)
    t = t - t.mean()
    score = np.fft.irfft2(np.fft.rfft2(image) * np.conj(np.fft.rfft2(t, s=image.shape)))
    h, w = templ.shape
    score = score[: image.shape[0] - h + 1, : image.shape[1] - w + 1]
    iy, ix = np.unravel_index(np.argmax(score), score.shape)
    return float(score[iy, ix]) / (h * w), int(ix), int(iy), w, h

neu = load(NEU_PATH)
gneu = gray(neu)
# Eye templates include lash + iris. Origins are top-left.
EYE_BOX = {
    'L': (185, 172, 240, 214),
    'R': (265, 165, 325, 210),
}
BROW_BOX = {
    'L': (190, 168, 238, 190),
    'R': (270, 158, 322, 184),
}

def templates_from(boxes):
    out = {}
    for k, (x0, y0, x1, y1) in boxes.items():
        out[k] = gneu[y0:y1, x0:x1]
    return out

EYE_T = templates_from(EYE_BOX)
BROW_T = templates_from(BROW_BOX)

def locate(path, temps, boxes):
    img = gray(load(path))
    names = list(temps)
    odx = boxes['R'][0] - boxes['L'][0]
    ody = boxes['R'][1] - boxes['L'][1]
    best = None
    for s in np.linspace(0.55, 1.05, 26):
        hits = {}
        ok = True
        for name, t0 in temps.items():
            t = resize_nearest(t0, s).astype(np.float64)
            if t.shape[0] >= img.shape[0] - 2 or t.shape[1] >= img.shape[1] - 2:
                ok = False
                break
            hits[name] = find_template(img, t)
        if not ok or len(hits) < 2:
            continue
        L, R = hits['L'], hits['R']
        dx, dy = R[1] - L[1], R[2] - L[2]
        err = abs(dx - odx * s) + abs(dy - ody * s) * 2
        rec = (err, -(L[0] + R[0]), float(s), hits)
        if best is None or rec < best:
            best = rec
    return best

def locate_auto(path):
    eye = locate(path, EYE_T, EYE_BOX)
    brow = locate(path, BROW_T, BROW_BOX)
    # Prefer the higher combined score when the geometric error is sane.
    def quality(rec):
        return rec[1]  # negative score sum; smaller is better match
    # If the open-eye template scores poorly, the eyes are closed.
    eye_score = -(eye[1])
    if eye_score < 7000:
        return brow, 'brow', BROW_BOX
    return eye, 'eye', EYE_BOX

# Map expression pixel -> neutral pixel using the left anchor, scale s.
def make_sampler(path, rec, boxes):
    err, neg, s, hits = rec
    src = load(path)
    # Per-eye anchors so each eye lands on its own neutral box.
    anchors = {}
    for name in ('L', 'R'):
        ex, ey = hits[name][1], hits[name][2]
        nx, ny = boxes[name][0], boxes[name][1]
        anchors[name] = (ex, ey, nx, ny, s)
    def sample(npx, npy, name):
        ex, ey, nx, ny, s = anchors[name]
        # n = n0 + (e - e0) / s  => e = e0 + (n - n0) * s
        fx = ex + (npx - nx) * s
        fy = ey + (npy - ny) * s
        ix, iy = int(round(fx)), int(round(fy))
        if 0 <= ix < src.shape[1] and 0 <= iy < src.shape[0]:
            return src[iy, ix]
        return None
    return sample, s, hits

def cutout(arr):
    h, w = arr.shape[:2]
    border = np.concatenate([arr[0], arr[-1], arr[:, 0], arr[:, -1]], 0)
    bg = np.median(border, 0)
    d = np.abs(arr.astype(np.int16) - bg.astype(np.int16)).sum(2)
    # flood from edges through near-bg
    from collections import deque
    vis = np.zeros((h, w), bool)
    q = deque()
    for x in range(w):
        q.append((x, 0)); q.append((x, h - 1))
    for y in range(h):
        q.append((0, y)); q.append((w - 1, y))
    while q:
        x, y = q.popleft()
        if x < 0 or y < 0 or x >= w or y >= h or vis[y, x]:
            continue
        if d[y, x] > 48:
            continue
        vis[y, x] = True
        q.append((x + 1, y)); q.append((x - 1, y)); q.append((x, y + 1)); q.append((x, y - 1))
    rgba = np.zeros((h, w, 4), np.uint8)
    rgba[:, :, :3] = arr
    rgba[:, :, 3] = np.where(vis, 0, 255)
    # drop one-pixel fringe that still looks like bg
    return rgba

def is_dark(p):
    return p[0] < 110 and p[1] < 95 and p[2] < 90

def is_skin(p):
    return p[0] > 210 and p[1] > 170 and p[2] > 140 and p[0] > p[2]

# Cheek skin sampled beside the left eye.
CHEEK = neu[220, 230]

SOCKET = {
    # tight content boxes measured on the neutral grid
    'L': (188, 176, 238, 214),
    'R': (268, 170, 322, 208),
}

def eye_mask(side):
    x0, y0, x1, y1 = SOCKET[side]
    m = np.zeros(neu.shape[:2], bool)
    # ellipse
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    rx, ry = (x1 - x0) / 2, (y1 - y0) / 2
    ys, xs = np.mgrid[y0:y1, x0:x1]
    u = (xs - cx) / rx
    v = (ys - cy) / ry
    m[y0:y1, x0:x1] = (u * u + v * v) <= 1
    return m

def build_closed_eyes(path, tag):
    rec, kind, boxes = locate_auto(path)
    sample, s, hits = make_sampler(path, rec, boxes)
    out = neu.copy()
    for side in ('L', 'R'):
        mask = eye_mask(side)
        ys, xs = np.where(mask)
        for y, x in zip(ys, xs):
            p = sample(x, y, side)
            if p is None:
                continue
            if is_dark(p):
                out[y, x] = p
            else:
                # lid skin in the master's own cheek color
                out[y, x] = CHEEK
        # also copy dark lash pixels in a pad around the socket so the line can extend
        x0, y0, x1, y1 = SOCKET[side]
        for y in range(y0 - 4, y1 + 6):
            for x in range(x0 - 4, x1 + 6):
                p = sample(x, y, side)
                if p is not None and is_dark(p):
                    out[y, x] = p
    return out, kind, rec

def build_one_eye(path, side_closed):
    """Wink: replace only one eye. side_closed is L or R in IMAGE space."""
    rec, kind, boxes = locate_auto(path)
    sample, s, hits = make_sampler(path, rec, boxes)
    out = neu.copy()
    mask = eye_mask(side_closed)
    ys, xs = np.where(mask)
    for y, x in zip(ys, xs):
        p = sample(x, y, side_closed)
        if p is None:
            continue
        if is_dark(p):
            out[y, x] = p
        else:
            out[y, x] = CHEEK
    x0, y0, x1, y1 = SOCKET[side_closed]
    for y in range(y0 - 4, y1 + 6):
        for x in range(x0 - 4, x1 + 6):
            p = sample(x, y, side_closed)
            if p is not None and is_dark(p):
                out[y, x] = p
    return out, kind, rec

# Mouth stays on the neutral lip. Only the oval around that lip may change.
MOUTH_C = (256, 249)
MOUTH_RX, MOUTH_RY = 36, 20

def in_mouth(x, y):
    u = (x - MOUTH_C[0]) / MOUTH_RX
    v = (y - MOUTH_C[1]) / MOUTH_RY
    return u * u + v * v <= 1

def build_mouth(path):
    rec, kind, boxes = locate_auto(path)
    sample, s, hits = make_sampler(path, rec, boxes)
    out = neu.copy()
    # Remove the closed smile so its corners do not sit beside an open mouth.
    for y in range(MOUTH_C[1] - 14, MOUTH_C[1] + 12):
        for x in range(MOUTH_C[0] - 42, MOUTH_C[0] + 43):
            u = (x - MOUTH_C[0]) / 42
            v = (y - MOUTH_C[1]) / 12
            if u * u + v * v > 1:
                continue
            if is_dark(neu[y, x]) or (neu[y, x, 0] < 170 and neu[y, x, 1] < 130):
                out[y, x] = CHEEK
    changed = np.zeros(neu.shape[:2], bool)
    x0 = MOUTH_C[0] - MOUTH_RX
    x1 = MOUTH_C[0] + MOUTH_RX + 1
    y0 = MOUTH_C[1] - MOUTH_RY
    y1 = MOUTH_C[1] + MOUTH_RY + 1
    for y in range(y0, y1):
        for x in range(x0, x1):
            if not in_mouth(x, y):
                continue
            side = 'L' if x < MOUTH_C[0] else 'R'
            p = sample(x, y, side)
            if p is None or is_skin(p):
                continue
            out[y, x] = p
            changed[y, x] = True
    return out, int(changed.sum()), kind


def write_assets(out_dir):
    from pathlib import Path
    out = Path(out_dir)
    base = cutout(neu)
    Image.fromarray(base).save(out / 'neutral.png')
    master = Image.open(SRC + '/neutral-master-1024.png').convert('RGB')
    master.save(out / 'source-1024.png')
    closed, _, _ = build_closed_eyes(SRC + '/expression-03-closed-blink.png', 'closed')
    Image.fromarray(closed).save('/tmp/front-closed-check.png')
    patch = np.zeros((*neu.shape[:2], 4), np.uint8)
    diff = np.any(closed != neu, axis=2)
    patch[:, :, :3] = closed
    patch[:, :, 3] = np.where(diff, 255, 0)
    Image.fromarray(patch).save(out / 'eyes-closed.png')
    iris = np.zeros((*neu.shape[:2], 4), np.uint8)
    for side, (x0, y0, x1, y1) in SOCKET.items():
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        rx, ry = (x1 - x0) / 2, (y1 - y0) / 2
        for y in range(y0, y1):
            for x in range(x0, x1):
                u = (x - cx) / rx; v = (y - cy) / ry
                if u * u + v * v > 1:
                    continue
                r, g, b = neu[y, x]
                if 175 < r < 235 and 95 < g < 180 and 45 < b < 145 and r > g + 8 and g > b:
                    iris[y, x] = (r, g, b, 255)
    Image.fromarray(iris).save(out / 'iris.png')
    print('iris', int((iris[:, :, 3] > 0).sum()), 'closed', int(diff.sum()))
    # Rounded mouth grid and eyelid curves. Do not stamp expression tiles.
    from build_expressions_v3 import main as build_expressions
    build_expressions()

if __name__ == '__main__':
    write_assets('/workspace/assets/male1')
