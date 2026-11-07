// Local warp of one flattened portrait. Neutral parameters sample the
// source pixel exactly. There is no invented eye, brow, or mouth layer.

function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)); }

export function warpPortrait(src, w, h, regions, state, limits) {
  const out = new Uint8ClampedArray(src);
  const lim = limits || {};
  const gazePx = lim.gazePx ?? 3;
  const blinkK = lim.blinkCompress ?? 0.55;
  const mouthK = lim.mouthScale ?? 0.18;
  const browPx = lim.browPx ?? 3;
  const smilePx = lim.smilePx ?? 2;
  for (const name of Object.keys(regions)) {
    const box = regions[name];
    const x0 = box[0], y0 = box[1], x1 = box[2], y1 = box[3];
    const cx = (x0 + x1) / 2, cy = (y0 + y1) / 2;
    const rx = Math.max(1, (x1 - x0) / 2), ry = Math.max(1, (y1 - y0) / 2);
    for (let y = y0; y < y1; y++) {
      for (let x = x0; x < x1; x++) {
        const u = (x + 0.5 - cx) / rx;
        const v = (y + 0.5 - cy) / ry;
        const r2 = u * u + v * v;
        if (r2 >= 1) continue;
        const weight = (1 - r2) * (1 - r2);
        let sx = x + 0.5, sy = y + 0.5;
        if (name === 'eyeL' || name === 'eyeR') {
          const open = name === 'eyeL' ? state.openL : state.openR;
          const k = (1 - clamp(open, 0, 1)) * blinkK * weight;
          sy = y + 0.5 - (y + 0.5 - y0) * k;
          sx += -(state.gx || 0) * gazePx * weight;
          sy += -(state.gy || 0) * gazePx * 0.65 * weight;
        } else if (name === 'browL' || name === 'browR') {
          const lift = ((state.browOut || 0) - (state.browDown || 0)) * browPx * weight;
          sy -= lift;
        } else if (name === 'mouth') {
          const open = (state.jaw || 0) * mouthK * weight;
          sy = cy + (y + 0.5 - cy) * (1 + open);
          const smile = clamp((state.smile || 0) - (state.frown || 0), -1, 1);
          sx += u * smile * smilePx * weight;
        }
        const ix = clamp(Math.round(sx - 0.5), 0, w - 1);
        const iy = clamp(Math.round(sy - 0.5), 0, h - 1);
        const di = (y * w + x) * 4;
        const si = (iy * w + ix) * 4;
        out[di] = src[si]; out[di + 1] = src[si + 1]; out[di + 2] = src[si + 2]; out[di + 3] = src[si + 3];
      }
    }
  }
  return out;
}

export function buffersEqual(a, b) {
  if (a.length !== b.length) return false;
  for (let i = 0; i < a.length; i++) if (a[i] !== b[i]) return false;
  return true;
}
