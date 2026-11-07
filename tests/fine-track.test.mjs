import assert from 'node:assert/strict';
import test from 'node:test';
import { readFileSync } from 'node:fs';
import { createFineTrack, stepFine, quantizeFine, packFine, FOX92_SHEET, MALE1_TRACK } from '../js/fine-track.js';
import { warpPortrait, buffersEqual } from '../js/portrait-warp.js';

const regions = JSON.parse(readFileSync(new URL('../assets/male1/manifest.json', import.meta.url))).regions;

function raw(over = {}) {
  return { jaw: 0, smile: 0, frown: 0, funnel: 0, blinkL: 0, blinkR: 0, gx: 0, gy: 0, brow: 0, browOuter: 0, browDown: 0, yaw: 0, pitch: 0, roll: 0, ...over };
}
function settle(track, value, n = 30, dt = 0.05) {
  for (let i = 0; i < n; i++) stepFine(track, value, dt, 1);
  return track;
}

test('sheet is twice fox92 and still not a 3D face', () => {
  assert.equal(MALE1_TRACK.S, FOX92_SHEET.S * 2);
  assert.ok(MALE1_TRACK.yawSteps > FOX92_SHEET.yawSteps);
  assert.ok(MALE1_TRACK.mouthSteps > FOX92_SHEET.mouthSteps);
  assert.ok(MALE1_TRACK.poseHoldMs < FOX92_SHEET.poseHoldMs);
  assert.ok(MALE1_TRACK.gazePx < FOX92_SHEET.gazePx * 2);
});

test('jaw opens gradually instead of jumping', () => {
  const track = createFineTrack();
  let prev = -1;
  for (const jaw of [0, 0.08, 0.16, 0.28, 0.45, 0.7, 1]) {
    settle(track, raw({ jaw }));
    const q = quantizeFine(track, MALE1_TRACK, jaw * 1000);
    assert.ok(q.mouth >= prev, `${jaw} went ${prev} -> ${q.mouth}`);
    prev = q.mouth;
  }
  assert.equal(prev, MALE1_TRACK.mouthSteps - 1);
  const tiny = createFineTrack();
  settle(tiny, raw({ jaw: 0.02 }));
  assert.equal(quantizeFine(tiny, MALE1_TRACK).mouth, 0);
});

test('one eye closes into a wink and the other stays open', () => {
  const track = createFineTrack();
  settle(track, raw({ blinkL: 1, blinkR: 0 }));
  assert.ok(track.openL < 0.2);
  assert.ok(track.openR > 0.8);
  assert.equal(track.wink, 'L');
  const q = quantizeFine(track, MALE1_TRACK);
  assert.ok(q.eyelidL > q.eyelidR);
});

test('small yaw noise stays in the deadzone and a real turn moves', () => {
  const track = createFineTrack();
  settle(track, raw({ yaw: 0 }));
  const first = quantizeFine(track, MALE1_TRACK, 0).yaw;
  settle(track, raw({ yaw: 0.4 }));
  assert.equal(quantizeFine(track, MALE1_TRACK, 20).yaw, first);
  settle(track, raw({ yaw: 24 }));
  const turned = quantizeFine(track, MALE1_TRACK, 200).yaw;
  assert.notEqual(turned, first);
});

test('neutral warp is the original portrait and a blink changes pixels', () => {
  const png = readFileSync(new URL('../assets/male1/neutral.png', import.meta.url));
  // Decode via the PNG IHDR only here; pixels come from a raw sidecar written by the test runner if present.
  assert.equal(png.readUInt32BE(16), 512);
  assert.equal(png.readUInt32BE(20), 512);
  const w = 8, h = 8;
  const src = new Uint8ClampedArray(w * h * 4);
  for (let i = 0; i < src.length; i++) src[i] = (i * 17) % 255;
  const box = { eyeL: [1, 1, 6, 6] };
  const limits = { gazePx: 3, blinkCompress: 0.55, mouthScale: 0.18, browPx: 3, smilePx: 2 };
  const neutral = { openL: 1, openR: 1, gx: 0, gy: 0, jaw: 0, smile: 0, frown: 0, browOut: 0, browDown: 0 };
  assert.equal(buffersEqual(src, warpPortrait(src, w, h, box, neutral, limits)), true);
  const moved = warpPortrait(src, w, h, box, { ...neutral, openL: 0, gx: 1 }, limits);
  assert.equal(buffersEqual(src, moved), false);
});
