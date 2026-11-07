"""Relay tests: separate processes, rooms, one audible player, late join, reconnect."""
import json
import os
import struct
import subprocess
import sys
import textwrap
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import vtuber_relay as relay  # noqa: E402


def vtuber_payload(**over):
    b = {k: 0 for k in relay.BLEND_KEYS}
    b.update(over.pop('b', {}))
    base = {
        'kind': 'vtuber', 'seq': 1, 'face': True, 'b': b,
        'micOn': False, 'micScore': 0, 'expr': 'auto', 'react': None,
    }
    base.update(over)
    return base


def player_payload(**over):
    base = {
        'kind': 'player', 'playing': True, 'ci': 0, 'ti': 0, 'oi': 0,
        'catId': 'opening', 'catName': '출근 도장',
        'file': 'audio/opening/opening_B_3min_loop.mp3',
        'title': '문이 열리는 시간', 'order': [0], 'shuffle': True,
        'vol': 0.5, 'offset': 3.25, 'dur': 180, 'sentAt': 1_700_000_000_000,
    }
    base.update(over)
    return base


class DefaultCharTests(unittest.TestCase):
    def test_default_is_fox92_and_explicit_ids_remain(self):
        self.assertEqual(relay.DEFAULT_CHAR, 'fox92')
        text = relay._urls(8765)
        self.assertIn('/?role=track&char=fox92', text)
        self.assertIn('/?role=display&obs=1&char=fox92', text)
        self.assertNotIn('char=fox91', text)
        self.assertNotIn('char=fox93', text)
        for key in ('fox91', 'fox92', 'fox93'):
            self.assertIn(key, relay.CHARS)
            manifest = json.loads((ROOT / 'assets' / key / 'manifest.json').read_text())
            self.assertEqual(manifest['mode'], 'face')
            self.assertTrue(manifest['layers'])
        html = (ROOT / 'index.html').read_text()
        self.assertIn('value="fox92" selected', html)
        self.assertNotIn('value="fox91" selected', html)
        self.assertIn('value="fox91"', html)
        self.assertIn('value="fox93"', html)
        app = (ROOT / 'js/app.js').read_text()
        self.assertIn('DEFAULT_CHAR', app)
        self.assertNotIn('CHARS.fox91', app)
        self.assertIn("fox91: 'assets/fox91/'", app)
        self.assertIn("fox93: 'assets/fox93/'", app)

    def test_resolutions(self):
        def wh(path):
            blob = (ROOT / path).read_bytes()
            return struct.unpack('>II', blob[16:24])
        self.assertEqual(wh('assets/fox92/base.png')[0], 256)
        self.assertEqual(wh('assets/male1/neutral.png'), (512, 512))
        self.assertEqual(wh('assets/male1/source-1024.png'), (1024, 1024))
        # Rest pose matches the frontal painting. Pose angles do not move pixels.
        script = r'''
import { readFileSync } from "node:fs";
import { renderFront, FRONT_REST } from "./js/front-face.js";
const read = (name) => new Uint8ClampedArray(readFileSync(name));
const src = read("/tmp/male-neutral.rgba");
const mouths = [];
for (let a = 0; a < 13; a++) for (let s = 0; s < 5; s++) mouths.push(read(`/tmp/male-m-${String(a).padStart(2,'0')}-${s}.rgba`));
const lidsN = [], lidsH = [];
for (let i = 0; i < 5; i++) {
  lidsN.push(read(`/tmp/male-lid-n-${i}.rgba`));
  lidsH.push(read(`/tmp/male-lid-h-${i}.rgba`));
}
const parts = {
  iris: read("/tmp/male-iris.rgba"),
  mouths, lidsN, lidsH,
  mouthGrid: { aperture: 13, shapes: 5 },
};
const rest = renderFront(src, parts, 512, 512, FRONT_REST);
for (let i = 0; i < src.length; i++) if (src[i] !== rest[i]) process.exit(2);
const turned = renderFront(src, parts, 512, 512, { ...FRONT_REST, yaw: 30, pitch: 20, roll: 15 });
for (let i = 0; i < src.length; i++) if (src[i] !== turned[i]) process.exit(3);
function irisCount(buf) {
  let n = 0;
  for (let i = 0; i < parts.iris.length; i += 4) {
    if (parts.iris[i + 3] < 128) continue;
    if (Math.abs(buf[i] - src[i]) < 8 && Math.abs(buf[i + 1] - src[i + 1]) < 8) n++;
  }
  return n;
}
const restIris = irisCount(src);
if (restIris < 40) process.exit(4);
let prev = restIris;
for (const open of [0.85, 0.55, 0.3, 0.12, 0]) {
  const frame = renderFront(src, parts, 512, 512, { ...FRONT_REST, openL: open, openR: open });
  const n = irisCount(frame);
  if (n > prev) process.exit(5);
  prev = n;
}
// The iris mask also covers the amber lid crease above the lash, so a full
// close does not drive that count to zero. The disk itself is covered.
if (prev > restIris * 0.5) process.exit(6);
const back = renderFront(src, parts, 512, 512, FRONT_REST);
for (let i = 0; i < src.length; i++) if (src[i] !== back[i]) process.exit(7);
const wink = renderFront(src, parts, 512, 512, { ...FRONT_REST, openL: 0, openR: 1 });
let leftGone = 0, rightKept = 0;
for (let y = 176; y < 214; y++) for (let x = 188; x < 238; x++) {
  const i = (y * 512 + x) * 4;
  if (parts.iris[i + 3] > 128 && Math.abs(wink[i] - src[i]) > 20) leftGone++;
}
for (let y = 170; y < 208; y++) for (let x = 268; x < 322; x++) {
  const i = (y * 512 + x) * 4;
  if (parts.iris[i + 3] > 128 && wink[i] === src[i]) rightKept++;
}
if (leftGone < 10 || rightKept < 10) process.exit(8);
function changed(buf) {
  let n = 0;
  for (let i = 0; i < src.length; i += 4) if (buf[i] !== src[i] || buf[i + 1] !== src[i + 1] || buf[i + 2] !== src[i + 2]) n++;
  return n;
}
function bounds(buf) {
  let x0 = 999, y0 = 999, x1 = -1, y1 = -1, n = 0;
  for (let y = 220; y < 290; y++) for (let x = 200; x < 330; x++) {
    const i = (y * 512 + x) * 4;
    if (buf[i] !== src[i] || buf[i + 1] !== src[i + 1] || buf[i + 2] !== src[i + 2]) {
      n++; if (x < x0) x0 = x; if (y < y0) y0 = y; if (x > x1) x1 = x; if (y > y1) y1 = y;
    }
  }
  return { n, x0, y0, x1, y1 };
}
const tiny = bounds(renderFront(src, parts, 512, 512, { ...FRONT_REST, jaw: 0.05 }));
const mid = bounds(renderFront(src, parts, 512, 512, { ...FRONT_REST, jaw: 0.45 }));
const wide = bounds(renderFront(src, parts, 512, 512, { ...FRONT_REST, jaw: 1 }));
if (!(tiny.n > 20 && mid.n > tiny.n && wide.n > mid.n)) process.exit(9);
// The opening stays on the painted smile (top near y=239) and grows downward.
if (tiny.y0 < 238 || wide.y0 < 236 || wide.y1 <= mid.y1 || mid.y1 <= tiny.y1) process.exit(14);
const shut = bounds(renderFront(src, parts, 512, 512, { ...FRONT_REST, jaw: 0.8, close: 1 }));
if (shut.n !== 0) process.exit(15);
const smiled = bounds(renderFront(src, parts, 512, 512, { ...FRONT_REST, smile: 0.9 }));
if (!(smiled.n > 20 && smiled.n < wide.n)) process.exit(16);
const round = bounds(renderFront(src, parts, 512, 512, { ...FRONT_REST, jaw: 0.85, funnel: 0.9 }));
const grin = bounds(renderFront(src, parts, 512, 512, { ...FRONT_REST, jaw: 0.85, smile: 0.9 }));
if (!(grin.x1 - grin.x0 > wide.x1 - wide.x0 && round.x1 - round.x0 < wide.x1 - wide.x0)) process.exit(19);
const puff = renderFront(src, parts, 512, 512, { ...FRONT_REST, puff: 1 });
for (let i = 0; i < src.length; i++) if (src[i] !== puff[i]) process.exit(20);
const half = irisCount(renderFront(src, parts, 512, 512, { ...FRONT_REST, openL: 0.5, openR: 0.5 }));
if (!(half < restIris && half > prev)) process.exit(21);
const happyShut = renderFront(src, parts, 512, 512, { ...FRONT_REST, openL: 0, openR: 0, smile: 0.8 });
const plainShut = renderFront(src, parts, 512, 512, { ...FRONT_REST, openL: 0, openR: 0 });
let lidDiff = 0;
for (let i = 0; i < src.length; i += 4) if (happyShut[i] !== plainShut[i]) lidDiff++;
if (lidDiff < 20) process.exit(22);
function mouthParts(buf) {
  const diff = new Uint8Array(512 * 512);
  for (let y = 220; y < 300; y++) for (let x = 180; x < 340; x++) {
    const i = (y * 512 + x) * 4;
    if (buf[i] !== src[i] || buf[i + 1] !== src[i + 1] || buf[i + 2] !== src[i + 2]) diff[y * 512 + x] = 1;
  }
  const seen = new Uint8Array(512 * 512);
  let ncomp = 0;
  for (let y = 220; y < 300; y++) for (let x = 180; x < 340; x++) {
    const p = y * 512 + x;
    if (!diff[p] || seen[p]) continue;
    ncomp++;
    const q = [p];
    seen[p] = 1;
    while (q.length) {
      const c = q.pop();
      const cy = (c / 512) | 0, cx = c % 512;
      for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++) {
        const ny = cy + dy, nx = cx + dx;
        if (ny < 220 || ny >= 300 || nx < 180 || nx >= 340) continue;
        const np = ny * 512 + nx;
        if (diff[np] && !seen[np]) { seen[np] = 1; q.push(np); }
      }
    }
  }
  return ncomp;
}
for (const state of [
  { jaw: 0.05 }, { jaw: 0.25 }, { jaw: 0.55 }, { jaw: 1 },
  { jaw: 0.7, smile: 0.8 }, { jaw: 0.6, openL: 0, openR: 1 },
  { smile: 0.9 }, { jaw: 0.15, close: 0.2 },
]) {
  const buf = renderFront(src, parts, 512, 512, { ...FRONT_REST, ...state });
  if (mouthParts(buf) !== 1) process.exit(17);
}
const returned = renderFront(src, parts, 512, 512, { ...FRONT_REST, jaw: 0, smile: 0, close: 0 });
for (let i = 0; i < src.length; i++) if (src[i] !== returned[i]) process.exit(18);
const hair = (40 * 512 + 250) * 4;
const wideBuf = renderFront(src, parts, 512, 512, { ...FRONT_REST, jaw: 1, openL: 0 });
if (wideBuf[hair] !== src[hair]) process.exit(10);
if (src[3] !== 0 || src[(511 * 512 + 511) * 4 + 3] !== 0) process.exit(11);
const gazed = renderFront(src, parts, 512, 512, { ...FRONT_REST, gx: 1 });
let shift = 0;
for (let i = 0; i < src.length; i += 4) if (parts.iris[i + 3] > 128 && gazed[i] !== src[i]) shift++;
if (shift < 8) process.exit(12);
'''
        try:
            from PIL import Image
        except ImportError:
            self.skipTest('Pillow is not installed')
        def dump(name, rel):
            raw = Image.open(ROOT / rel).convert('RGBA').tobytes()
            Path(name).write_bytes(raw)
        dump('/tmp/male-neutral.rgba', 'assets/male1/neutral.png')
        dump('/tmp/male-iris.rgba', 'assets/male1/iris.png')
        for a in range(13):
            for s in range(5):
                dump(f'/tmp/male-m-{a:02d}-{s}.rgba', f'assets/male1/expr/m-{a:02d}-{s}.png')
        for i in range(5):
            dump(f'/tmp/male-lid-n-{i}.rgba', f'assets/male1/expr/lid-n-{i}.png')
            dump(f'/tmp/male-lid-h-{i}.rgba', f'assets/male1/expr/lid-h-{i}.png')
        run = subprocess.run(['node', '--input-type=module', '-e', script], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stderr[-500:] + run.stdout[-500:])


    def test_male256_is_native_and_rest_is_exact(self):
        self.assertIn('male256', relay.CHARS)
        self.assertEqual(relay.DEFAULT_CHAR, 'fox92')
        self.assertIn('value="male256"', (ROOT / 'index.html').read_text())
        def wh(path):
            blob = (ROOT / path).read_bytes()
            return struct.unpack('>II', blob[16:24])
        self.assertEqual(wh('assets/male256/neutral.png'), (256, 256))
        script = r'''
import { readFileSync } from "node:fs";
import { renderFront, FRONT_REST } from "./js/front-face.js";
const read = (name) => new Uint8ClampedArray(readFileSync(name));
const src = read("/tmp/m256-neutral.rgba");
const mouths = [];
for (let a = 0; a < 9; a++) for (let s = 0; s < 5; s++) mouths.push(read(`/tmp/m256-m-${String(a).padStart(2,"0")}-${s}.rgba`));
const lidsN = [], lidsH = [];
for (let i = 0; i < 5; i++) { lidsN.push(read(`/tmp/m256-lid-n-${i}.rgba`)); lidsH.push(read(`/tmp/m256-lid-h-${i}.rgba`)); }
const parts = {
  iris: read("/tmp/m256-iris.rgba"), mouths, lidsN, lidsH,
  mouthGrid: { aperture: 9, shapes: 5 },
  gazePx: 1, gazePy: 1, browPx: 1, sclera: [243, 212, 180],
  boxes: { L: {x0:96,y0:88,x1:120,y1:110}, R: {x0:140,y0:82,x1:166,y1:108} },
};
const rest = renderFront(src, parts, 256, 256, FRONT_REST);
for (let i = 0; i < src.length; i++) if (src[i] !== rest[i]) process.exit(2);
const turned = renderFront(src, parts, 256, 256, { ...FRONT_REST, yaw: 25, pitch: 15, roll: 10 });
for (let i = 0; i < src.length; i++) if (src[i] !== turned[i]) process.exit(3);
const puff = renderFront(src, parts, 256, 256, { ...FRONT_REST, puff: 1 });
for (let i = 0; i < src.length; i++) if (src[i] !== puff[i]) process.exit(4);
function changed(buf) {
  let n = 0;
  for (let i = 0; i < src.length; i += 4) if (buf[i] !== src[i] || buf[i+1] !== src[i+1] || buf[i+2] !== src[i+2]) n++;
  return n;
}
const tiny = changed(renderFront(src, parts, 256, 256, { ...FRONT_REST, jaw: 0.12 }));
const wide = changed(renderFront(src, parts, 256, 256, { ...FRONT_REST, jaw: 1 }));
const grin = changed(renderFront(src, parts, 256, 256, { ...FRONT_REST, jaw: 0.8, smile: 0.9 }));
const round = changed(renderFront(src, parts, 256, 256, { ...FRONT_REST, jaw: 0.8, funnel: 0.9 }));
if (!(tiny > 8 && wide > tiny)) process.exit(5);
if (!(grin > 0 && round > 0)) process.exit(6);
const shut = changed(renderFront(src, parts, 256, 256, { ...FRONT_REST, jaw: 0.9, close: 1 }));
if (shut !== 0) process.exit(7);
const back = renderFront(src, parts, 256, 256, FRONT_REST);
for (let i = 0; i < src.length; i++) if (src[i] !== back[i]) process.exit(8);
if (src[3] !== 0 || src[(255 * 256 + 255) * 4 + 3] !== 0) process.exit(9);
const blink = changed(renderFront(src, parts, 256, 256, { ...FRONT_REST, openL: 0, openR: 0 }));
const half = changed(renderFront(src, parts, 256, 256, { ...FRONT_REST, openL: 0.5, openR: 0.5 }));
const wink = renderFront(src, parts, 256, 256, { ...FRONT_REST, openL: 0, openR: 1 });
if (!(blink > half && half > 10)) process.exit(10);
let left = 0, right = 0;
for (let y = 90; y < 110; y++) for (let x = 98; x < 118; x++) {
  const i = (y * 256 + x) * 4;
  if (wink[i] !== src[i]) left++;
}
for (let y = 84; y < 108; y++) for (let x = 142; x < 164; x++) {
  const i = (y * 256 + x) * 4;
  if (wink[i] !== src[i]) right++;
}
if (left < 15 || right !== 0) process.exit(11);
'''
        try:
            from PIL import Image
        except ImportError:
            self.skipTest('Pillow is not installed')
        def dump(name, rel):
            Path(name).write_bytes(Image.open(ROOT / rel).convert('RGBA').tobytes())
        dump('/tmp/m256-neutral.rgba', 'assets/male256/neutral.png')
        dump('/tmp/m256-iris.rgba', 'assets/male256/iris.png')
        for a in range(9):
            for s in range(5):
                dump(f'/tmp/m256-m-{a:02d}-{s}.rgba', f'assets/male256/expr/m-{a:02d}-{s}.png')
        for i in range(5):
            dump(f'/tmp/m256-lid-n-{i}.rgba', f'assets/male256/expr/lid-n-{i}.png')
            dump(f'/tmp/m256-lid-h-{i}.rgba', f'assets/male256/expr/lid-h-{i}.png')
        run = subprocess.run(['node', '--input-type=module', '-e', script], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stderr[-400:] + run.stdout[-200:])


class SanitizeTests(unittest.TestCase):
    def test_fine_state_is_optional_and_stripped(self):
        old = vtuber_payload()
        clean = relay.sanitize_state('vtuber', old)
        self.assertNotIn('fine', clean)
        self.assertEqual(set(clean['b']), set(relay.BLEND_KEYS))
        raw = vtuber_payload()
        raw['fine'] = {'jaw': 0.42, 'openL': 0.15, 'openR': 0.9, 'wink': 'L', 'yaw': 12.2, 'gx': 0.4, 'image': 'nope'}
        fine = relay.sanitize_state('vtuber', raw)['fine']
        self.assertEqual(fine['jaw'], 0.42)
        self.assertEqual(fine['wink'], 'L')
        self.assertEqual(fine['yaw'], 12.2)
        self.assertEqual(fine['close'], 0)
        self.assertNotIn('image', fine)
        self.assertIn('male1', relay.CHARS)
        self.assertEqual(relay.DEFAULT_CHAR, 'fox92')

    def test_strips_frames_and_audio_blobs(self):
        raw = vtuber_payload(b={'jaw': 0.42, 'yaw': 33})
        raw['image'] = 'a' * 5000
        raw['pcm'] = [1, 2, 3]
        clean = relay.sanitize_state('vtuber', raw)
        self.assertNotIn('image', clean)
        self.assertNotIn('pcm', clean)
        self.assertEqual(clean['b']['jaw'], 0.42)
        self.assertEqual(clean['b']['yaw'], 33)

    def test_rejects_path_escape_and_huge_title(self):
        self.assertIsNone(relay.sanitize_state('player', player_payload(file='../secret.mp3')))
        self.assertIsNone(relay.sanitize_state('player', player_payload(title='x' * 500)))
        ok = relay.sanitize_state('player', player_payload())
        self.assertEqual(ok['vol'], 0.5)
        self.assertEqual(ok['file'], 'audio/opening/opening_B_3min_loop.mp3')

    def test_one_audible_player(self):
        def c(i, role, media='unknown'):
            return type('C', (), {'id': i, 'role': role, 'room': 'player', 'media': media})()
        a, b, ctrl = c('a', 'display'), c('b', 'display'), c('c', 'control')
        self.assertEqual(relay.choose_audible([a, b, ctrl]), 'a')
        a.media = 'blocked'
        self.assertEqual(relay.choose_audible([a, b, ctrl]), 'b')
        b.media = 'blocked'
        self.assertEqual(relay.choose_audible([a, b, ctrl]), 'c')
        self.assertIsNone(relay.choose_audible([type('C', (), {'id': 't', 'role': 'track', 'room': 'vtuber', 'media': 'unknown'})()]))


class SocketTests(unittest.TestCase):
    def setUp(self):
        self.httpd, self.hub = relay.serve_background(0)
        self.port = self.httpd.server_address[1]
        self.clients = []

    def tearDown(self):
        for c in self.clients:
            c.close()
        self.httpd.shutdown()
        self.httpd.server_close()

    def client(self, **kw):
        c = relay.SyncClient(self.port, **kw)
        self.clients.append(c)
        return c

    def test_cross_process_and_rooms(self):
        env = os.environ.copy()
        env['PYTHONPATH'] = str(ROOT / 'tools')
        code = textwrap.dedent(r'''
            import json, sys, time
            import vtuber_relay as r
            role, port, room = sys.argv[1], int(sys.argv[2]), sys.argv[3]
            c = r.SyncClient(port)
            c.send_json({"type": "hello", "role": role, "room": room})
            c.recv_type("welcome", 5)
            if role == "display":
                print("READY", flush=True)
                msg = c.recv_type("state", 8)
                print(json.dumps({"jaw": msg["payload"]["b"]["jaw"], "room": msg["room"], "mic": msg["payload"]["micScore"]}), flush=True)
                time.sleep(0.4)
            else:
                c.recv_type("peers", 5)
                b = {k: 0 for k in r.BLEND_KEYS}
                b["jaw"] = 0.77
                c.send_json({"type": "state", "room": "vtuber", "payload": {
                    "kind": "vtuber", "seq": 4, "face": True, "b": b,
                    "micOn": True, "micScore": 0.4, "expr": "happy", "react": None}})
                time.sleep(0.4)
            c.close()
        ''')
        display = subprocess.Popen(
            [sys.executable, '-c', code, 'display', str(self.port), 'vtuber'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env,
        )
        ready = display.stdout.readline().strip()
        self.assertEqual(ready, 'READY')
        track = subprocess.Popen(
            [sys.executable, '-c', code, 'track', str(self.port), 'vtuber'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env,
        )
        line = display.stdout.readline().strip()
        track.wait(timeout=5)
        display.wait(timeout=5)
        track_err = track.stderr.read()
        display_err = display.stderr.read()
        for stream in (display.stdout, display.stderr, track.stdout, track.stderr):
            stream.close()
        self.assertEqual(track.returncode, 0, track_err)
        self.assertEqual(display.returncode, 0, display_err)
        got = json.loads(line)
        self.assertEqual(got['jaw'], 0.77)
        self.assertEqual(got['mic'], 0.4)
        self.assertEqual(got['room'], 'vtuber')

    def test_late_join_replay_and_player_audible(self):
        control = self.client()
        control.send_json({'type': 'hello', 'role': 'control', 'room': 'player'})
        control.recv_type('welcome')
        first = control.recv_type('peers')
        self.assertTrue(first['youAudible'])
        self.assertEqual(first['roles']['display'], 0)
        control.send_json({'type': 'state', 'room': 'player', 'payload': player_payload(playing=False, offset=12)})
        # bad payload must not replace the snapshot
        control.send_json({'type': 'state', 'room': 'player', 'payload': {'kind': 'player', 'file': '../x', 'playing': True}})
        time.sleep(0.05)
        display = self.client()
        display.send_json({'type': 'hello', 'role': 'display', 'room': 'player'})
        display.recv_type('welcome')
        peers = display.recv_type('peers')
        state = display.recv_type('state')
        self.assertTrue(state.get('replay'))
        self.assertEqual(state['payload']['offset'], 12)
        self.assertFalse(state['payload']['playing'])
        self.assertTrue(peers['youAudible'])
        control_peers = control.recv_type('peers')
        self.assertFalse(control_peers['youAudible'])
        self.assertEqual(control_peers['audibleRole'], 'display')
        other = self.client()
        other.send_json({'type': 'hello', 'role': 'display', 'room': 'player'})
        other.recv_type('welcome')
        other_peers = other.recv_type('peers')
        self.assertFalse(other_peers['youAudible'])
        self.assertGreaterEqual(other_peers['roles']['display'], 2)
        joined = control.recv_type('peers')
        self.assertFalse(joined['youAudible'])
        self.assertEqual(joined['audibleRole'], 'display')
        # First display blocked → the other display is the only audible client.
        display.send_json({'type': 'media', 'audio': 'blocked'})
        moved = control.recv_type('peers')
        self.assertFalse(moved['youAudible'])
        self.assertEqual(moved['audibleRole'], 'display')
        self.assertNotEqual(moved['audibleId'], peers['clientId'])
        other.send_json({'type': 'media', 'audio': 'blocked'})
        back = control.recv_type('peers')
        self.assertTrue(back['youAudible'])
        self.assertEqual(back['audibleRole'], 'control')

    def test_room_isolation_and_foreign_origin(self):
        watch = self.client()
        watch.send_json({'type': 'hello', 'role': 'display', 'room': 'player'})
        watch.recv_type('welcome')
        track = self.client()
        track.send_json({'type': 'hello', 'role': 'track', 'room': 'vtuber'})
        track.recv_type('welcome')
        b = {k: 0 for k in relay.BLEND_KEYS}
        b['smile'] = 0.9
        track.send_json({'type': 'state', 'room': 'vtuber', 'payload': vtuber_payload(b={'smile': 0.9})})
        watch.sock.settimeout(0.3)
        with self.assertRaises(Exception):
            watch.recv_type('state', 0.3)
        with self.assertRaises(ConnectionError):
            relay.SyncClient(self.port, origin='https://firstund.github.io')

    def test_reconnect_gets_new_state(self):
        display = self.client()
        display.send_json({'type': 'hello', 'role': 'display', 'room': 'vtuber'})
        display.recv_type('welcome')
        track = self.client()
        track.send_json({'type': 'hello', 'role': 'track', 'room': 'vtuber'})
        track.recv_type('welcome')
        track.send_json({'type': 'state', 'room': 'vtuber', 'payload': vtuber_payload(b={'jaw': 0.2})})
        self.assertEqual(display.recv_type('state')['payload']['b']['jaw'], 0.2)
        track.close()
        self.clients.remove(track)
        track2 = self.client()
        track2.send_json({'type': 'hello', 'role': 'track', 'room': 'vtuber'})
        track2.recv_type('welcome')
        track2.send_json({'type': 'state', 'room': 'vtuber', 'payload': vtuber_payload(b={'jaw': 0.55}, seq=2)})
        self.assertEqual(display.recv_type('state')['payload']['b']['jaw'], 0.55)

    def test_artwork_untouched(self):
        for key in ('fox91', 'fox92', 'fox93'):
            manifest = json.loads((ROOT / 'assets' / key / 'manifest.json').read_text())
            for layer in manifest['layers']:
                self.assertTrue((ROOT / 'assets' / key / f'{layer}.png').is_file(), layer)
        player = (ROOT / 'player' / 'player.js').read_text()
        self.assertIn('listen', player)
        self.assertNotIn('getUserMedia', player)
        self.assertNotIn('BroadcastChannel', player)
        link = (ROOT / 'js' / 'link.js').read_text()
        self.assertNotIn('new BroadcastChannel', link)
        self.assertNotIn('localStorage.getItem', link)
        self.assertNotIn('localStorage.setItem', link)


if __name__ == '__main__':
    unittest.main()
