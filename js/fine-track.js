// Continuous face channels for a portrait that is not a sprite sheet.
// Fox sheets stay on the old quantised path. This does not deform a 3D mesh.

export const FOX92_SHEET = Object.freeze({
  S: 256,
  yawSteps: 5,
  pitchSteps: 3,
  rollSteps: 3,
  eyelidSteps: 3,
  mouthSteps: 6,
  gazePx: 4,
  poseHoldMs: 100,
  yawDead: 4,
});

// 512 is twice fox92's 256 base frame. Gaze pixels are not doubled: the
// portrait has no separate iris layer, so a large shift tears the paint.
export const MALE1_TRACK = Object.freeze({
  S: 512,
  yawSteps: 9,
  pitchSteps: 5,
  rollSteps: 5,
  eyelidSteps: 5,
  mouthSteps: 8,
  browSteps: 5,
  gazePx: 2,
  blinkCompress: 0.85,
  mouthScale: 0.18,
  mouthOpenPx: 14,
  browPx: 2,
  smilePx: 2,
  poseHoldMs: 40,
  yawDead: 1.2,
  pitchDead: 1.0,
  rollDead: 0.8,
  mouthDead: 0.035,
  eyelidDead: 0.06,
});

export const FINE_FIELDS = Object.freeze([
  'jaw', 'smile', 'frown', 'funnel', 'close',
  'openL', 'openR', 'gx', 'gy',
  'browIn', 'browOut', 'browDown',
  'yaw', 'pitch', 'roll',
]);

const TAU = { eyes: 0.03, mouth: 0.04, gaze: 0.035, brow: 0.045, pose: 0.055 };

export function createFineTrack() {
  return {
    jaw: 0, smile: 0, frown: 0, funnel: 0, close: 0,
    openL: 1, openR: 1, gx: 0, gy: 0,
    browIn: 0, browOut: 0, browDown: 0,
    yaw: 0, pitch: 0, roll: 0,
    wink: 'none',
    q: {
      yaw: null, pitch: null, roll: null, mouth: null,
      eyelidL: null, eyelidR: null, brow: null,
      hold: { yaw: 0, pitch: 0, roll: 0 },
    },
  };
}

function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)); }
function mix(cur, target, dt, tau) {
  const a = 1 - Math.exp(-dt / Math.max(0.008, tau));
  return cur + (target - cur) * a;
}

export function stepFine(track, raw, dt, sens = 1) {
  const s = clamp(sens || 1, 0.35, 2);
  const d = clamp(dt || 0, 0, 0.1);
  const tau = t => t / s;
  const r = raw || {};
  const blinkL = r.blinkL != null ? r.blinkL : (r.blink || 0);
  const blinkR = r.blinkR != null ? r.blinkR : (r.blink || 0);
  track.jaw = mix(track.jaw, clamp(r.jaw || 0, 0, 1), d, tau(TAU.mouth));
  track.close = mix(track.close, clamp(r.close || 0, 0, 1), d, tau(TAU.mouth));
  track.smile = mix(track.smile, clamp(r.smile || 0, 0, 1), d, tau(TAU.mouth));
  track.frown = mix(track.frown, clamp(r.frown || 0, 0, 1), d, tau(TAU.mouth));
  track.funnel = mix(track.funnel, clamp(r.funnel || 0, 0, 1), d, tau(TAU.mouth));
  track.openL = mix(track.openL, clamp(1 - blinkL, 0, 1), d, tau(TAU.eyes));
  track.openR = mix(track.openR, clamp(1 - blinkR, 0, 1), d, tau(TAU.eyes));
  track.gx = mix(track.gx, clamp(r.gx || 0, -1, 1), d, tau(TAU.gaze));
  track.gy = mix(track.gy, clamp(r.gy || 0, -1, 1), d, tau(TAU.gaze));
  track.browIn = mix(track.browIn, clamp(r.brow || 0, 0, 1), d, tau(TAU.brow));
  track.browOut = mix(track.browOut, clamp(r.browOuter || 0, 0, 1), d, tau(TAU.brow));
  track.browDown = mix(track.browDown, clamp(r.browDown || 0, 0, 1), d, tau(TAU.brow));
  track.yaw = mix(track.yaw, clamp(r.yaw || 0, -70, 70), d, tau(TAU.pose));
  track.pitch = mix(track.pitch, clamp(r.pitch || 0, -40, 40), d, tau(TAU.pose));
  track.roll = mix(track.roll, clamp(r.roll || 0, -35, 35), d, tau(TAU.pose));
  if (track.openL < 0.35 && track.openR > 0.72) track.wink = 'L';
  else if (track.openR < 0.35 && track.openL > 0.72) track.wink = 'R';
  else track.wink = 'none';
  return track;
}

function sticky(continuous, prev, slack) {
  const n = Math.round(continuous);
  if (prev == null || !Number.isFinite(prev)) return n;
  if (Math.abs(continuous - prev) <= slack) return prev;
  return n;
}

function holdIndex(track, key, next, now, holdMs) {
  const q = track.q;
  if (q[key] == null) { q[key] = next; q.hold[key] = now; return next; }
  if (next === q[key]) return q[key];
  if (now - (q.hold[key] || 0) < holdMs) return q[key];
  q[key] = next; q.hold[key] = now; return next;
}

export function quantizeFine(track, spec = MALE1_TRACK, nowMs = 0) {
  const yawSpan = 70, pitSpan = 40, rollSpan = 40;
  const yawC = (track.yaw + yawSpan / 2) / yawSpan * (spec.yawSteps - 1);
  const pitC = (track.pitch + pitSpan / 2) / pitSpan * (spec.pitchSteps - 1);
  const rollC = (track.roll + rollSpan / 2) / rollSpan * (spec.rollSteps - 1);
  const yawSlack = spec.yawDead / (yawSpan / (spec.yawSteps - 1));
  const pitSlack = spec.pitchDead / (pitSpan / (spec.pitchSteps - 1));
  const rollSlack = spec.rollDead / (rollSpan / (spec.rollSteps - 1));
  const yaw = holdIndex(track, 'yaw', sticky(yawC, track.q.yaw, yawSlack), nowMs, spec.poseHoldMs);
  const pitch = holdIndex(track, 'pitch', sticky(pitC, track.q.pitch, pitSlack), nowMs, spec.poseHoldMs);
  const roll = holdIndex(track, 'roll', sticky(rollC, track.q.roll, rollSlack), nowMs, spec.poseHoldMs);
  const mouthC = track.jaw * (spec.mouthSteps - 1);
  const mouthSlack = spec.mouthDead * (spec.mouthSteps - 1);
  const mouth = sticky(mouthC, track.q.mouth, mouthSlack);
  track.q.mouth = mouth;
  const lid = (open, prev) => {
    const c = (1 - open) * (spec.eyelidSteps - 1);
    const slack = spec.eyelidDead * (spec.eyelidSteps - 1);
    return sticky(c, prev, slack);
  };
  const eyelidL = lid(track.openL, track.q.eyelidL);
  const eyelidR = lid(track.openR, track.q.eyelidR);
  track.q.eyelidL = eyelidL;
  track.q.eyelidR = eyelidR;
  const mid = (spec.browSteps - 1) / 2;
  const browC = mid + (track.browOut - track.browDown) * mid;
  const brow = sticky(browC, track.q.brow, 0.35);
  track.q.brow = brow;
  let mouthShape = 'neutral';
  if (track.smile > track.frown + 0.12) mouthShape = 'smile';
  else if (track.frown > track.smile + 0.12) mouthShape = 'frown';
  return {
    yaw: clamp(yaw, 0, spec.yawSteps - 1),
    pitch: clamp(pitch, 0, spec.pitchSteps - 1),
    roll: clamp(roll, 0, spec.rollSteps - 1),
    mouth: clamp(mouth, 0, spec.mouthSteps - 1),
    mouthShape,
    eyelidL: clamp(eyelidL, 0, spec.eyelidSteps - 1),
    eyelidR: clamp(eyelidR, 0, spec.eyelidSteps - 1),
    brow: clamp(brow, 0, spec.browSteps - 1),
    wink: track.wink,
  };
}

export function packFine(track) {
  const o = {};
  for (const k of FINE_FIELDS) o[k] = Math.round((track[k] || 0) * 1000) / 1000;
  o.wink = track.wink || 'none';
  return o;
}

export function applyPackedFine(track, packed) {
  if (!packed) return track;
  for (const k of FINE_FIELDS) if (typeof packed[k] === 'number') track[k] = packed[k];
  if (packed.wink === 'L' || packed.wink === 'R' || packed.wink === 'none') track.wink = packed.wink;
  return track;
}
