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

function paintEyes(out, closed, w, state) {
  if (!closed) return;
  const covers = {
    L: clamp((1 - (state.openL == null ? 1 : state.openL)) / 0.92, 0, 1),
    R: clamp((1 - (state.openR == null ? 1 : state.openR)) / 0.92, 0, 1),
  };
  if (covers.L <= 0 && covers.R <= 0) return;
  const n = w * w;
  for (let p = 0; p < n; p++) {
    const a = closed[p * 4 + 3];
    if (a < 128) continue;
    const x = p % w;
    const y = (p / w) | 0;
    let side = null;
    let info = null;
    for (const key of ['L', 'R']) {
      const hit = ellipse(FRONT_EYES[key], x, y);
      if (hit.inside) { side = key; info = hit; break; }
    }
    if (!side) {
      if (covers.L > 0.97 || covers.R > 0.97) copyPx(out, closed, p * 4);
      continue;
    }
    const edge = -1 + 2 * covers[side];
    if (covers[side] > 0.97 || info.v < edge) copyPx(out, closed, p * 4);
  }
}

function paintGaze(out, neutral, iris, w, state) {
  if (!iris) return;
  const dx = clamp(Math.round(-(state.gx || 0) * 2), -2, 2);
  const dy = clamp(Math.round(-(state.gy || 0)), -1, 1);
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
    out[i] = WHITE[0]; out[i + 1] = WHITE[1]; out[i + 2] = WHITE[2]; out[i + 3] = 255;
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

// One mouth. Frame 0 is empty (the painted smile). Each later frame is that
// same lip line opened one pixel further. No crossfade and no second shape.
export function mouthOpenAmount(state) {
  const jaw = clamp(state.jaw || 0, 0, 1);
  const smile = clamp(state.smile || 0, 0, 1);
  const close = clamp(state.close || 0, 0, 1);
  let open = jaw * (1 - close);
  if (close < 0.45) open = Math.max(open, Math.max(0, smile - 0.42) * 0.22);
  return clamp(open, 0, 1);
}

export function mouthFrameIndex(state, count) {
  if (!count) return 0;
  return clamp(Math.round(mouthOpenAmount(state) * (count - 1)), 0, count - 1);
}

function paintMouth(out, parts, w, state) {
  const frames = parts && parts.mouths;
  if (!frames || !frames.length) return;
  blitPatch(out, frames[mouthFrameIndex(state, frames.length)], w);
}

function paintBrows(out, neutral, w, state) {
  const lift = clamp((state.browOut || 0) - (state.browDown || 0), -1, 1);
  const dy = clamp(Math.round(-lift), -1, 1);
  if (dy === 0) return;
  for (const box of Object.values(FRONT_BROWS)) {
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
  paintEyes(out, parts && parts.closed, w, s);
  paintGaze(out, neutral, parts && parts.iris, w, s);
  paintMouth(out, parts || {}, w, s);
  paintBrows(out, neutral, w, s);
  return out;
}

export function countAlpha(buf) {
  let n = 0;
  for (let i = 3; i < buf.length; i += 4) if (buf[i] > 128) n++;
  return n;
}
