// Layered edits on the approved rowdy portrait.
// The painted smile and half-lidded eyes are the identity. Rest tracking
// (open eyes, jaw 0, no gaze) does not change a pixel. Blink covers only the
// measured eye opening. A wider jaw paints an interior under the existing
// teeth. The whole sprite may shift by a couple of pixels; the face is not
// rubber-warped.

export const ROWDY_REST = Object.freeze({
  openL: 1, openR: 1, jaw: 0, smile: 0, frown: 0, close: 0,
  gx: 0, gy: 0, browIn: 0, browOut: 0, browDown: 0,
  yaw: 0, pitch: 0, roll: 0, wink: 'none',
});

// Each row is [y, [x0, x1], ...] over the painted eye opening.
// Dark lashes are left out, so a blink covers the opening and keeps the lid line.
// Image-left eye sits lower. Measured from plus-512.png.
const EYE_L = [
  [196, [201, 204], [213, 219]],
  [197, [199, 205], [209, 221]],
  [198, [197, 205], [208, 225]],
  [199, [195, 205], [208, 224]],
  [200, [195, 205], [208, 224]],
  [201, [194, 224]],
  [202, [194, 224]],
  [203, [188, 224]],
  [204, [189, 223]],
  [205, [193, 223]],
  [206, [195, 222]],
  [207, [198, 221]],
  [208, [199, 220]],
  [209, [202, 216]],
  [210, [204, 212]],
];
const EYE_R = [
  [177, [295, 301]],
  [178, [295, 302]],
  [179, [286, 291], [295, 302]],
  [180, [280, 292], [296, 302]],
  [181, [279, 293], [296, 302]],
  [182, [278, 304]],
  [183, [271, 303]],
  [184, [269, 302]],
  [185, [267, 301]],
  [186, [263, 299]],
  [187, [265, 298]],
  [188, [266, 297]],
  [189, [268, 295]],
  [190, [268, 295]],
  [191, [269, 294]],
  [192, [270, 289]],
  [193, [270, 277], [280, 285]],
  [194, [271, 274]],
];

const BROW_L = { x0: 196, y0: 178, x1: 226, y1: 194 };
const BROW_R = { x0: 266, y0: 156, x1: 318, y1: 176 };
const TEETH = { x0: 230, y0: 226, x1: 286, y1: 256 };

const IRIS = [219, 149, 108];
const WHITE = [245, 219, 190];
const SKIN = [251, 209, 173];
const LASH = [61, 48, 42];
const MOUTH = [87, 36, 50];
const GUM = [147, 83, 67];

function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)); }
function near(r, g, b, t, tol) {
  return Math.abs(r - t[0]) <= tol && Math.abs(g - t[1]) <= tol && Math.abs(b - t[2]) <= tol;
}
function isIris(r, g, b) { return near(r, g, b, IRIS, 16) && r < 235; }
function isTooth(r, g, b) { return near(r, g, b, WHITE, 8) && r > 230; }
function isSkin(r, g, b) { return r > 240 && g > 190 && b > 155 && b < 195; }
function isDark(r, g, b) { return r < 90 && g < 80 && b < 70; }
function put(out, w, x, y, rgb) {
  const i = (y * w + x) * 4;
  out[i] = rgb[0]; out[i + 1] = rgb[1]; out[i + 2] = rgb[2]; out[i + 3] = 255;
}
function get(src, w, x, y) {
  const i = (y * w + x) * 4;
  return [src[i], src[i + 1], src[i + 2], src[i + 3]];
}

function coverEyes(out, src, w, state) {
  const eyes = [['eyeL', EYE_L, state.openL], ['eyeR', EYE_R, state.openR]];
  const dx = clamp(Math.round(-(state.gx || 0) * 2), -2, 2);
  const dy = clamp(Math.round(-(state.gy || 0)), -1, 1);
  for (const [, spans, openRaw] of eyes) {
    const open = clamp(openRaw == null ? 1 : openRaw, 0, 1);
    const cover = clamp((1 - open) / 0.85, 0, 1);
    const coverRows = Math.round(cover * spans.length);
    const gaze = coverRows < spans.length && (dx !== 0 || dy !== 0);
    if (coverRows === 0 && !gaze) continue;
    const openKeys = new Set();
    const visit = (fn) => {
      spans.forEach((row, i) => {
        const y = row[0];
        for (let r = 1; r < row.length; r++) {
          const [x0, x1] = row[r];
          for (let x = x0; x <= x1; x++) fn(x, y, i);
        }
      });
    };
    visit((x, y, i) => { if (i >= coverRows) openKeys.add(`${x},${y}`); });
    const placed = new Map();
    const from = new Set();
    if (gaze) {
      for (const key of openKeys) {
        const [xs, ys] = key.split(',').map(Number);
        const [r, g, b, a] = get(src, w, xs, ys);
        if (a < 200 || !isIris(r, g, b)) continue;
        let nx = xs + dx, ny = ys + dy;
        if (!openKeys.has(`${nx},${ny}`)) { nx = xs; ny = ys; }
        placed.set(`${nx},${ny}`, [r, g, b]);
        from.add(key);
      }
    }
    visit((x, y, i) => {
      if (i < coverRows) {
        const lid = coverRows < spans.length && i === coverRows - 1;
        put(out, w, x, y, lid ? LASH : SKIN);
        return;
      }
      const key = `${x},${y}`;
      if (placed.has(key)) put(out, w, x, y, placed.get(key));
      else if (from.has(key)) put(out, w, x, y, WHITE);
    });
  }
}

function paintMouth(out, src, w, h, state) {
  const jaw = clamp(state.jaw || 0, 0, 1);
  const close = clamp(state.close || 0, 0, 1);
  const shut = close > 0.4 && jaw < 0.28;
  const extra = jaw > 0.2 ? clamp((jaw - 0.2) / 0.8, 0, 1) : 0;
  if (!shut && extra <= 0) return;
  const box = TEETH;
  const cols = [];
  for (let x = box.x0; x < box.x1; x++) {
    let top = -1, bottom = -1;
    for (let y = box.y0; y < box.y1; y++) {
      const [r, g, b, a] = get(src, w, x, y);
      if (a > 200 && isTooth(r, g, b)) {
        if (top < 0) top = y;
        bottom = y;
      }
    }
    if (top >= 0) cols.push({ x, top, bottom });
  }
  if (!cols.length) return;
  if (shut) {
    for (const { x, top, bottom } of cols) {
      for (let y = top; y <= bottom; y++) put(out, w, x, y, y === top ? MOUTH : SKIN);
    }
    return;
  }
  const minX = cols[0].x, maxX = cols[cols.length - 1].x;
  const mid = (minX + maxX) / 2;
  const half = Math.max(1, (maxX - minX) / 2);
  const gapMax = Math.round(extra * 7);
  for (const { x, bottom } of cols) {
    const taper = 1 - Math.abs(x - mid) / half;
    const gap = Math.max(1, Math.round(gapMax * (0.25 + 0.75 * taper)));
    for (let k = 1; k <= gap; k++) {
      const y = bottom + k;
      if (y < 0 || y >= h) continue;
      const [r, g, b, a] = get(src, w, x, y);
      if (a < 200 || isDark(r, g, b) || !isSkin(r, g, b)) continue;
      put(out, w, x, y, k === gap ? GUM : MOUTH);
    }
  }
}

function paintBrows(out, src, w, state) {
  const lift = clamp((state.browOut || 0) - (state.browDown || 0), -1, 1);
  const asym = clamp((state.browIn || 0) * 0.5, 0, 0.5);
  for (const [box, side] of [[BROW_L, -1], [BROW_R, 1]]) {
    const dy = clamp(Math.round((-lift + side * asym) * 1), -1, 1);
    if (dy === 0) continue;
    const marks = [];
    for (let y = box.y0; y < box.y1; y++) {
      for (let x = box.x0; x < box.x1; x++) {
        const [r, g, b, a] = get(src, w, x, y);
        if (a < 200 || !isDark(r, g, b)) continue;
        const below = get(src, w, x, Math.min(w - 1, y + 2));
        if (isSkin(below[0], below[1], below[2])) marks.push([x, y, r, g, b]);
      }
    }
    for (const [x, y] of marks) put(out, w, x, y, SKIN);
    for (const [x, y, r, g, b] of marks) {
      const ny = clamp(y + dy, 0, w - 1);
      put(out, w, x, ny, [r, g, b]);
    }
  }
}

function shiftWhole(src, w, h, state) {
  const yaw = state.yaw || 0, pitch = state.pitch || 0, roll = state.roll || 0;
  const dx = Math.abs(yaw) < 8 ? 0 : clamp(Math.round(-yaw / 16), -2, 2);
  const dy = Math.abs(pitch) < 6 ? 0 : clamp(Math.round(pitch / 14), -2, 2);
  const rollOn = Math.abs(roll) >= 7;
  if (dx === 0 && dy === 0 && !rollOn) return src;
  const out = new Uint8ClampedArray(w * h * 4);
  for (let y = 0; y < h; y++) {
    const shear = rollOn ? clamp(Math.round((y - h / 2) * -roll / 900), -2, 2) : 0;
    for (let x = 0; x < w; x++) {
      const sx = x - dx - shear, sy = y - dy;
      if (sx < 0 || sy < 0 || sx >= w || sy >= h) continue;
      const di = (y * w + x) * 4, si = (sy * w + sx) * 4;
      out[di] = src[si]; out[di + 1] = src[si + 1]; out[di + 2] = src[si + 2]; out[di + 3] = src[si + 3];
    }
  }
  return out;
}

export function renderRowdy(src, w, h, state) {
  const s = state || ROWDY_REST;
  const out = new Uint8ClampedArray(src);
  coverEyes(out, src, w, s);
  paintMouth(out, src, w, h, s);
  paintBrows(out, src, w, s);
  return shiftWhole(out, w, h, s);
}

export function countIris(buf, w, spans) {
  let n = 0;
  for (const row of spans) {
    const y = row[0];
    for (let r = 1; r < row.length; r++) {
      const [x0, x1] = row[r];
      for (let x = x0; x <= x1; x++) {
        const [cr, cg, cb] = get(buf, w, x, y);
        if (isIris(cr, cg, cb)) n++;
      }
    }
  }
  return n;
}

export const ROWDY_EYES = Object.freeze({ L: EYE_L, R: EYE_R });
