import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { once } from 'node:events';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import test from 'node:test';
import { createLink, DEFAULT_CHAR, expectedOffset, outputMode, splitPageUrls, wsUrlFromLocation } from '../js/link.js';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const tools = path.join(root, 'tools');

function zeroBlend(jaw = 0) {
  const keys = ['jaw', 'funnel', 'smile', 'blink', 'blinkL', 'blinkR', 'gx', 'gy', 'browDown', 'browOuter', 'brow', 'wide', 'yaw', 'pitch', 'roll', 'stretch', 'smileAsym', 'puff', 'squint'];
  const b = Object.fromEntries(keys.map(k => [k, 0]));
  b.jaw = jaw;
  return b;
}

function startRelay(port = 0) {
  const proc = spawn('python3', ['-c', `
import vtuber_relay as r
httpd, hub = r.serve_background(${port})
print(httpd.server_address[1], flush=True)
import time
time.sleep(99999)
`], { cwd: root, env: { ...process.env, PYTHONPATH: tools } });
  let buf = '';
  const portReady = new Promise((resolve, reject) => {
    const t = setTimeout(() => reject(new Error('relay did not print a port')), 5000);
    proc.stdout.on('data', chunk => {
      buf += chunk.toString();
      const line = buf.split('\n').map(s => s.trim()).find(s => /^\d+$/.test(s));
      if (line) { clearTimeout(t); resolve(Number(line)); }
    });
    proc.once('exit', code => reject(new Error('relay exited ' + code)));
  });
  return { proc, portReady };
}

if (process.argv[2] === '--child') {
  const url = process.argv[3];
  const role = process.argv[4];
  const room = process.argv[5];
  const ws = new WebSocket(url);
  ws.onopen = () => {
    ws.send(JSON.stringify({ type: 'hello', role, room }));
  };
  ws.onmessage = ev => {
    const msg = JSON.parse(ev.data);
    if (msg.type === 'welcome') console.log('WELCOME');
    if (msg.type === 'state') console.log('STATE ' + JSON.stringify(msg.payload));
    if (msg.type === 'peers') console.log('PEERS ' + JSON.stringify({ you: msg.youAudible, role: msg.audibleRole, displays: msg.roles?.display || 0 }));
  };
  setTimeout(() => {
    if (role !== 'track') return;
    ws.send(JSON.stringify({
      type: 'state', room: 'vtuber',
      payload: { kind: 'vtuber', seq: 3, face: true, b: zeroBlend(0.33), micOn: false, micScore: 0, expr: 'auto', react: null },
    }));
  }, 150);
  setTimeout(() => process.exit(0), 2500);
} else {
  test('url helpers and single audible decision', () => {
    assert.equal(DEFAULT_CHAR, 'fox92');
    const pages = splitPageUrls({ hostname: 'firstund.github.io', href: 'https://firstund.github.io/pixel-vtuber/player/?obs=1' });
    assert.equal(pages.display, 'http://127.0.0.1:8765/?role=display&obs=1&char=fox92');
    assert.equal(pages.track, 'http://127.0.0.1:8765/?role=track&char=fox92');
    assert.equal(pages.playerDisplay, 'http://127.0.0.1:8765/player/?role=display&obs=1');
    const local = splitPageUrls({ hostname: '127.0.0.1', href: 'http://127.0.0.1:9000/player/?role=control' }, { port: '9000' });
    assert.equal(local.track, 'http://127.0.0.1:9000/?role=track&char=fox92');
    const fixed = { hostname: '127.0.0.1', href: 'http://127.0.0.1:8765/' };
    assert.match(splitPageUrls(fixed, { char: 'fox91' }).display, /char=fox91$/);
    assert.match(splitPageUrls(fixed, { char: 'fox93' }).track, /char=fox93$/);
    assert.equal(wsUrlFromLocation({ hostname: 'firstund.github.io', protocol: 'https:', host: 'firstund.github.io' }, new URLSearchParams()), '');
    assert.equal(wsUrlFromLocation({ hostname: '127.0.0.1', protocol: 'http:', host: '127.0.0.1:8765' }, new URLSearchParams()), 'ws://127.0.0.1:8765/ws');
    assert.equal(outputMode({ role: '', youAudible: false }), 'local');
    assert.equal(outputMode({ role: 'control', youAudible: false }), 'mute');
    assert.equal(outputMode({ role: 'display', youAudible: true }), 'this');
    const now = 10_000;
    assert.equal(expectedOffset({ playing: true, offset: 4, sentAt: 9000 }, now), 5);
    assert.equal(expectedOffset({ playing: false, offset: 4, sentAt: 9000 }, now), 4);
  });

  test('browser WebSocket stack crosses two node processes', async () => {
    const relay = startRelay(0);
    const port = await relay.portReady;
    const url = `ws://127.0.0.1:${port}/ws`;
    const display = spawn(process.execPath, [fileURLToPath(import.meta.url), '--child', url, 'display', 'vtuber'], { stdio: ['ignore', 'pipe', 'pipe'] });
    let out = '';
    display.stdout.on('data', c => { out += c.toString(); });
    const welcome = new Promise((resolve, reject) => {
      const t = setTimeout(() => reject(new Error('no welcome ' + out)), 4000);
      display.stdout.on('data', () => { if (out.includes('WELCOME')) { clearTimeout(t); resolve(); } });
    });
    await welcome;
    const track = spawn(process.execPath, [fileURLToPath(import.meta.url), '--child', url, 'track', 'vtuber'], { stdio: ['ignore', 'pipe', 'pipe'] });
    const state = new Promise((resolve, reject) => {
      const t = setTimeout(() => reject(new Error('no state ' + out)), 4000);
      display.stdout.on('data', () => {
        if (out.includes('"jaw":0.33')) { clearTimeout(t); resolve(); }
      });
    });
    await state;
    track.kill();
    display.kill();
    relay.proc.kill();
    await once(relay.proc, 'exit').catch(() => {});
  });

  test('page client reconnects after the display socket drops', async () => {
    const relay = startRelay(0);
    const port = await relay.portReady;
    const url = `ws://127.0.0.1:${port}/ws`;
    const offsets = [];
    let audible = null;
    const link = createLink({
      url, role: 'display', room: 'player',
      onMessage(msg) {
        if (msg.type === 'state') offsets.push(msg.payload.offset);
        if (msg.type === 'peers') audible = msg.youAudible;
      },
    });
    const track = new WebSocket(url);
    await once(track, 'open');
    track.send(JSON.stringify({ type: 'hello', role: 'control', room: 'player' }));
    await new Promise(r => setTimeout(r, 150));
    const sendState = (offset, playing) => track.send(JSON.stringify({
      type: 'state', room: 'player',
      payload: {
        kind: 'player', playing, ci: 0, ti: 0, oi: 0,
        catId: 'opening', catName: '출근 도장', file: 'audio/opening/opening_B_3min_loop.mp3',
        title: '문이 열리는 시간', order: [0], shuffle: false, vol: 0.5, offset, dur: 180, sentAt: Date.now(),
      },
    }));
    const waitOffset = (n, ms = 3000) => new Promise((resolve, reject) => {
      const t = setTimeout(() => reject(new Error('missing ' + n + ' in ' + offsets.join(','))), ms);
      const tick = setInterval(() => {
        if (offsets.includes(n)) { clearInterval(tick); clearTimeout(t); resolve(); }
      }, 20);
    });
    sendState(8, false);
    await waitOffset(8);
    assert.equal(audible, true);
    assert.equal(link.send({ type: 'drop' }), true);
    await new Promise(r => setTimeout(r, 500));
    sendState(11, true);
    await waitOffset(11);
    link.close();
    track.close();
    relay.proc.kill();
    await once(relay.proc, 'exit').catch(() => {});
  });
}
