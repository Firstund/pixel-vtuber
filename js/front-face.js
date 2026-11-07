// Frontal rowdy face. The body, hair, and open eyes stay on the neutral
// painting. Closed lids and mouth shapes are patches aligned to that painting.
// Yaw, pitch, and roll are tracked but not drawn: the sheets have no turned head.

export const FRONT_EYES = Object.freeze({
  L: { x0: 188, y0: 176, x1: 238, y1: 214 },
  R: { x0: 268, y0: 170, x1: 322, y1: 208 },
});

export const FRONT_BROWS = Object.freeze({
  L: { x0: 192, y0: 164, x1: 242, y1: 186 },
  R: { x0: 270, y0: 156, x1: 326, y1: 178 },
});

export const FRONT_REST = Object.freeze({
  openL: 1, openR: 1, jaw: 0, smile: 0, frown: 0, close: 0,
  gx: 0, gy: 0, browIn: 0, browOut: 0, browDown: 0,
  yaw: 0, pitch: 0, roll: 0, wink: 'none',
});

const WHITE = [241, 218, 194, 255];

function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)); }

function ellipse(box, x, y) {
  const cx = (box.x0 + box.x1) / 2;
  const cy = (box.y0 + box.y1) / 2;
  const rx = (box.x1 - box.x0) / 2;
  const ry = (box.y1 - box.y0) / 2;
  const u = (x + 0.5 - cx) / rx;
  const v = (y + 0.5 - cy) / ry;
  return { inside: u * u + v * v <= 1, v };
}

function copyPx(out, src, i) {
  out[i] = src[i]; out[i + 1] = src[i + 1]; out[i + 2] = src[i + 2]; out[i + 3] = 255;
}

const LID_BOX = {
  L: { x0: 186, y0: 168, x1: 242, y1: 220 },
  R: { x0: 266, y0: 162, x1: 326, y1: 214 },
};

function lidIndex(open) {
  const cover = clamp((1 - (open == null ? 1 : open)) / 0.92, 0, 1);
  return clamp(Math.round(cover * 4), 0, 4);
}

function blitBox(out, patch, w, box) {
  if (!patch || !box) return;
  for (let y = box.y0; y < box.y1; y++) {
    for (let x = box.x0; x < box.x1; x++) {
      const i = (y * w + x) * 4;
      if (patch[i + 3] < 128) continue;
      copyPx(out, patch, i);
    }
  }
}

function paintEyes(out, parts, w, state) {
  const neutral = parts && parts.lidsN;
  const happy = parts && parts.lidsH;
  if (!neutral || !neutral.length) return;
  const boxes = (parts && parts.boxes) || LID_BOX;
  const smile = state.smile || 0;
  for (const key of ['L', 'R']) {
    const idx = lidIndex(key === 'L' ? state.openL : state.openR);
    if (idx <= 0) continue;
    const happyLid = smile > 0.55 && idx >= 2 && happy && happy[idx];
    blitBox(out, happyLid || neutral[idx], w, boxes[key]);
  }
}

function paintGaze(out, neutral, iris, w, state, parts) {
  if (!iris) return;
  const gaze = (parts && parts.gazePx) || 2;
  const dyMax = (parts && parts.gazePy) || 1;
  const dx = clamp(Math.round(-(state.gx || 0) * gaze), -gaze, gaze);
  const dy = clamp(Math.round(-(state.gy || 0) * dyMax), -dyMax, dyMax);
  const sclera = (parts && parts.sclera) || WHITE;
  if (dx === 0 && dy === 0) return;
  const n = w * w;
  const from = [];
  for (let p = 0; p < n; p++) {
    if (iris[p * 4 + 3] < 128) continue;
    const i = p * 4;
    if (out[i] !== neutral[i] || out[i + 1] !== neutral[i + 1] || out[i + 2] !== neutral[i + 2]) continue;
    from.push(p);
  }
  const placed = new Map();
  for (const p of from) {
    const x = p % w;
    const y = (p / w) | 0;
    let nx = x + dx;
    let ny = y + dy;
    const np = ny * w + nx;
    const inside = nx >= 0 && ny >= 0 && nx < w && ny < w && iris[np * 4 + 3] >= 128;
    const dest = inside ? np : p;
    if (!placed.has(dest)) placed.set(dest, p);
  }
  for (const p of from) {
    if (placed.has(p)) continue;
    const i = p * 4;
    out[i] = sclera[0]; out[i + 1] = sclera[1]; out[i + 2] = sclera[2]; out[i + 3] = 255;
  }
  for (const [dest, src] of placed) {
    if (dest === src) continue;
    const si = src * 4;
    const di = dest * 4;
    out[di] = neutral[si]; out[di + 1] = neutral[si + 1]; out[di + 2] = neutral[si + 2]; out[di + 3] = 255;
  }
}

function blitPatch(out, patch, w) {
  if (!patch) return;
  const n = w * w;
  for (let p = 0; p < n; p++) {
    if (patch[p * 4 + 3] < 128) continue;
    copyPx(out, patch, p * 4);
  }
}

// Aperture 0 is empty, so the painted smile stays exact. Other cells are that
// same lip opened into a round speech shape, a wider smile, or a rounder O.
// Cheek puff is not a face parameter here.
export function mouthOpenAmount(state) {
  const jaw = clamp(state.jaw || 0, 0, 1);
  const smile = clamp(state.smile || 0, 0, 1);
  const funnel = clamp(state.funnel || 0, 0, 1);
  const close = clamp(state.close || 0, 0, 1);
  let open = jaw * (1 - close);
  if (close < 0.45) {
    open = Math.max(open, Math.max(0, smile - 0.4) * 0.2);
    open = Math.max(open, Math.max(0, funnel - 0.35) * 0.45);
  }
  return clamp(open, 0, 1);
}

export function mouthShape(state) {
  const smile = clamp(state.smile || 0, 0, 1);
  const funnel = clamp(state.funnel || 0, 0, 1);
  const close = clamp(state.close || 0, 0, 1);
  if (close > 0.45) return 0;
  if (funnel > smile + 0.12) return -clamp(funnel, 0, 1);
  if (smile > funnel + 0.12) return clamp(smile, 0, 1);
  return clamp(smile - funnel, -1, 1);
}

export function mouthCell(state, grid) {
  const A = (grid && grid.aperture) || 1;
  const S = (grid && grid.shapes) || 1;
  const ai = clamp(Math.round(mouthOpenAmount(state) * (A - 1)), 0, A - 1);
  if (ai <= 0) return 0;
  const si = clamp(Math.round((mouthShape(state) + 1) / 2 * (S - 1)), 0, S - 1);
  return ai * S + si;
}

// Pose families for the 256 mouth. Rest is the only empty frame.
// These are blendshape shapes, not recognized speech sounds.
export function selectMouthPose(state) {
  const jaw = clamp(state.jaw || 0, 0, 1);
  const smile = clamp(state.smile || 0, 0, 1);
  const funnel = clamp(state.funnel || 0, 0, 1);
  const pucker = clamp(state.pucker || 0, 0, 1);
  const stretch = clamp(state.stretch || 0, 0, 1);
  const close = clamp(state.close || 0, 0, 1);
  const frown = clamp(state.frown || 0, 0, 1);
  const asym = clamp(state.smileAsym || 0, -1, 1);
  if (jaw < 0.06 && smile < 0.12 && funnel < 0.12 && pucker < 0.12 && stretch < 0.12 && close < 0.2 && frown < 0.2) {
    return { id: 'rest', open: 0, asym: 0 };
  }
  if (close > 0.5 && jaw * (1 - close) < 0.22 && Math.max(smile, funnel, pucker, stretch) < 0.4) {
    return { id: 'press', open: close, asym: 0 };
  }
  const sPuck = pucker;
  const sO = Math.max(0, funnel - pucker * 0.55);
  const sI = stretch * (1 - smile * 0.5);
  const sLaugh = smile > 0.55 && jaw > 0.55 ? Math.min(smile, jaw) : 0;
  const sSmile = sLaugh > 0 ? 0 : smile * (1 - Math.max(funnel, pucker) * 0.45);
  const sA = jaw * (1 - Math.max(sPuck, sO, sI, sSmile, sLaugh) * 0.85);
  const scores = [
    ['pucker', sPuck], ['O', sO], ['I', sI], ['laugh', sLaugh], ['smile', sSmile], ['A', sA],
  ];
  let id = 'A';
  let best = -1;
  for (const [name, sc] of scores) if (sc > best) { best = sc; id = name; }
  if (best < 0.12 && jaw < 0.18) return { id: 'rest', open: 0, asym: 0 };
  if (id === 'A' && jaw < 0.28 && smile < 0.2) id = 'part';
  let open = jaw;
  if (id === 'O') open = Math.max(jaw, funnel);
  else if (id === 'pucker') open = Math.max(jaw * 0.45, pucker);
  else if (id === 'I') open = Math.max(stretch, jaw * 0.4);
  else if (id === 'smile') open = Math.max(jaw, smile * 0.4);
  else if (id === 'laugh') open = Math.max(jaw, 0.65);
  else if (id === 'part') open = Math.max(jaw, 0.3);
  let corner = 0;
  if ((id === 'smile' || id === 'laugh' || id === 'A') && Math.abs(asym) > 0.35) corner = asym > 0 ? 1 : -1;
  return { id, open: clamp(open, 0, 1), asym: corner };
}

function poseIndex(state, poses) {
  const want = selectMouthPose(state);
  const pick = (asym) => {
    let best = -1;
    let score = 1e9;
    for (let i = 0; i < poses.length; i++) {
      const p = poses[i];
      if (p.id !== want.id || (p.asym || 0) !== asym) continue;
      const d = Math.abs((p.open || 0) - want.open);
      if (d < score) { score = d; best = i; }
    }
    return best;
  };
  const exact = pick(want.asym || 0);
  if (exact >= 0) return exact;
  const mid = pick(0);
  return mid >= 0 ? mid : 0;
}

function paintMouth(out, parts, w, state) {
  const frames = parts && parts.mouths;
  if (!frames || !frames.length) return;
  let idx;
  if (parts.mouthPoses && parts.mouthPoses.length === frames.length) idx = poseIndex(state, parts.mouthPoses);
  else if (parts.mouthGrid) idx = mouthCell(state, parts.mouthGrid);
  else idx = clamp(Math.round(mouthOpenAmount(state) * (frames.length - 1)), 0, frames.length - 1);
  blitPatch(out, frames[idx], w);
}

function paintBrows(out, neutral, w, state, parts) {
  const maxDy = (parts && parts.browPx) || 1;
  const lift = clamp((state.browOut || 0) - (state.browDown || 0), -1, 1);
  const dy = clamp(Math.round(-lift * maxDy), -maxDy, maxDy);
  if (dy === 0) return;
  const boxes = (parts && parts.brows) || FRONT_BROWS;
  for (const box of Object.values(boxes)) {
    const marks = [];
    for (let y = box.y0; y < box.y1; y++) {
      for (let x = box.x0; x < box.x1; x++) {
        const i = (y * w + x) * 4;
        const r = out[i], g = out[i + 1], b = out[i + 2];
        if (r > 90 || g > 80) continue;
        const bi = (Math.min(w - 1, y + 2) * w + x) * 4;
        if (out[bi] < 220) continue;
        marks.push([x, y, r, g, b]);
      }
    }
    for (const [x, y] of marks) {
      const i = (y * w + x) * 4;
      const si = (Math.min(w - 1, y + 1) * w + x) * 4;
      copyPx(out, neutral, i);
      out[i] = neutral[si]; out[i + 1] = neutral[si + 1]; out[i + 2] = neutral[si + 2];
    }
    for (const [x, y, r, g, b] of marks) {
      const ny = clamp(y + dy, 0, w - 1);
      const i = (ny * w + x) * 4;
      out[i] = r; out[i + 1] = g; out[i + 2] = b; out[i + 3] = 255;
    }
  }
}

export function renderFront(neutral, parts, w, h, state) {
  const s = state || FRONT_REST;
  const out = new Uint8ClampedArray(neutral);
  paintEyes(out, parts || {}, w, s);
  paintGaze(out, neutral, parts && parts.iris, w, s, parts);
  paintMouth(out, parts || {}, w, s);
  paintBrows(out, neutral, w, s, parts);
  return out;
}

export function countAlpha(buf) {
  let n = 0;
  for (let i = 3; i < buf.length; i += 4) if (buf[i] > 128) n++;
  return n;
}
