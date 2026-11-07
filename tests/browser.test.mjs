import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { once } from 'node:events';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import test from 'node:test';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const tools = path.join(root, 'tools');
const shots = '/opt/cursor/artifacts';
fs.mkdirSync(shots, { recursive: true });

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

function startRelay() {
  const proc = spawn('python3', ['-c', `
import vtuber_relay as r
httpd, hub = r.serve_background(0)
print(httpd.server_address[1], flush=True)
import time
time.sleep(99999)
`], { cwd: root, env: { ...process.env, PYTHONPATH: tools } });
  let buf = '';
  const portReady = new Promise((resolve, reject) => {
    const t = setTimeout(() => reject(new Error('relay did not start\n' + buf)), 8000);
    proc.stdout.on('data', chunk => {
      buf += chunk.toString();
      const line = buf.split('\n').map(s => s.trim()).find(s => /^\d+$/.test(s));
      if (line) { clearTimeout(t); resolve(Number(line)); }
    });
  });
  proc.stderr.on('data', c => { buf += c.toString(); });
  return { proc, portReady };
}

async function launchChrome(port, dir) {
  fs.rmSync(dir, { recursive: true, force: true });
  fs.mkdirSync(dir, { recursive: true });
  const proc = spawn('google-chrome', [
    '--headless=new', '--no-sandbox', '--disable-gpu', '--disable-dev-shm-usage',
    '--remote-allow-origins=*',
    '--autoplay-policy=no-user-gesture-required',
    '--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream',
    `--remote-debugging-port=${port}`, `--user-data-dir=${dir}`, 'about:blank',
  ], { stdio: 'ignore' });
  for (let i = 0; i < 50; i++) {
    try {
      const r = await fetch(`http://127.0.0.1:${port}/json/version`);
      if (r.ok) return proc;
    } catch { /* chrome still booting */ }
    await sleep(100);
  }
  proc.kill();
  throw new Error('chrome did not open a debug port');
}

function cdp(wsUrl) {
  const ws = new WebSocket(wsUrl);
  let n = 0;
  const pending = new Map();
  ws.addEventListener('message', ev => {
    const m = JSON.parse(ev.data);
    if (m.id && pending.has(m.id)) {
      const { resolve, reject } = pending.get(m.id);
      pending.delete(m.id);
      if (m.error) reject(new Error(JSON.stringify(m.error)));
      else resolve(m.result);
    }
  });
  const ready = new Promise((resolve, reject) => {
    ws.addEventListener('open', () => resolve());
    ws.addEventListener('error', () => reject(new Error('cdp socket')));
  });
  function send(method, params = {}) {
    const id = ++n;
    return new Promise((resolve, reject) => {
      pending.set(id, { resolve, reject });
      ws.send(JSON.stringify({ id, method, params }));
    });
  }
  return { ws, send, ready };
}

async function newTab(port, url) {
  let res = await fetch(`http://127.0.0.1:${port}/json/new?${encodeURIComponent(url)}`, { method: 'PUT' });
  if (!res.ok) res = await fetch(`http://127.0.0.1:${port}/json/new?${encodeURIComponent(url)}`);
  if (!res.ok) throw new Error('json/new ' + res.status);
  return res.json();
}

async function evaljs(c, expression) {
  const result = await c.send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true });
  if (result.exceptionDetails) throw new Error(JSON.stringify(result.exceptionDetails).slice(0, 600));
  return result.result?.value;
}

async function waitFor(c, expression, timeout = 8000) {
  const start = Date.now();
  let last;
  while (Date.now() - start < timeout) {
    last = await evaljs(c, expression);
    if (last) return last;
    await sleep(100);
  }
  throw new Error('timeout ' + expression + ' last=' + last);
}

async function shot(c, name) {
  const result = await c.send('Page.captureScreenshot', { format: 'png' });
  fs.writeFileSync(path.join(shots, name), Buffer.from(result.data, 'base64'));
}

test('display page takes no camera and follows the other browser', { timeout: 120000 }, async () => {
  const relay = startRelay();
  const httpPort = await relay.portReady;
  const base = `http://127.0.0.1:${httpPort}`;
  const dirA = fs.mkdtempSync(path.join(os.tmpdir(), 'vtuber-a-'));
  const dirB = fs.mkdtempSync(path.join(os.tmpdir(), 'vtuber-b-'));
  const chromeA = await launchChrome(9333, dirA);
  const chromeB = await launchChrome(9334, dirB);
  const tabA = await newTab(9333, 'about:blank');
  const tabB = await newTab(9334, 'about:blank');
  const a = cdp(tabA.webSocketDebuggerUrl);
  const b = cdp(tabB.webSocketDebuggerUrl);
  await Promise.all([a.ready, b.ready]);
  await a.send('Page.enable');
  await b.send('Page.enable');
  try {
    await b.send('Page.navigate', { url: `${base}/?role=track` });
    await waitFor(b, `window.__char === 'fox92' && document.getElementById('char').value === 'fox92'`);
    const trackUrl = await evaljs(b, `document.getElementById('urlTrack').value`);
    const displayUrl = await evaljs(b, `document.getElementById('urlDisplay').value`);
    assert.match(trackUrl, /char=fox92/);
    assert.match(displayUrl, /role=display/);
    assert.match(displayUrl, /obs=1/);
    assert.match(displayUrl, /char=fox92/);
    await shot(b, 'vtuber-track-panel.png');

    await a.send('Page.navigate', { url: `${base}/?role=display&obs=1` });
    await waitFor(a, `window.__char === 'fox92'`);
    const pixels92 = await evaljs(a, `(() => { const c = document.getElementById('c'); const d = c.getContext('2d').getImageData(0,0,c.width,c.height).data; let n=0; for (let i=3;i<d.length;i+=4) if (d[i]>0) n++; return n; })()`);
    assert.ok(pixels92 > 50, 'fox92 pixels ' + pixels92);
    await a.send('Page.navigate', { url: `${base}/?role=display&obs=1&char=fox91` });
    await waitFor(a, `window.__char === 'fox91'`);
    await a.send('Page.navigate', { url: `${base}/?role=display&obs=1&char=fox93` });
    await waitFor(a, `window.__app && window.__char === 'fox93'`);
    const media = await evaljs(a, `(async () => {
      let name = '';
      try { await navigator.mediaDevices.getUserMedia({ video: true, audio: true }); name = 'allowed'; }
      catch (e) { name = e.name; }
      return { calls: window.__mediaRequests, name, role: document.documentElement.dataset.role };
    })()`);
    assert.equal(media.calls, 0);
    assert.equal(media.name, 'NotAllowedError');
    assert.equal(media.role, 'display');
    await b.send('Page.navigate', { url: 'about:blank' });

    const pub = new WebSocket(`ws://127.0.0.1:${httpPort}/ws`);
    await once(pub, 'open');
    pub.send(JSON.stringify({ type: 'hello', role: 'track', room: 'vtuber' }));
    const blend = { jaw: 0.2, funnel: 0, smile: 0.1, blink: 0, blinkL: 0.05, blinkR: 0.9, gx: 0.4, gy: 0, browDown: 0, browOuter: 0, brow: 0, wide: 0, yaw: 40, pitch: 0, roll: 0, stretch: 0, smileAsym: 0, puff: 0, squint: 0 };
    const timer = setInterval(() => {
      pub.send(JSON.stringify({
        type: 'state', room: 'vtuber',
        payload: { kind: 'vtuber', seq: 1, face: true, b: blend, micOn: true, micScore: 0.85, expr: 'auto', react: null, cfg: { char: 'fox93', mirror: true, choppy: true, breath: true, autoBlink: true, micExpr: true, props: ['coffee'] } },
      }));
    }, 50);
    const pose = await waitFor(a, `window.__app && window.__app.pose.shown.k === -2 && window.__app.mic.score > 0.5`, 6000);
    assert.ok(pose);
    const pixels = await evaljs(a, `(() => { const c = document.getElementById('c'); const d = c.getContext('2d').getImageData(0,0,c.width,c.height).data; let n=0; for (let i=3;i<d.length;i+=4) if (d[i]>0) n++; return n; })()`);
    assert.ok(pixels > 50, 'canvas pixels ' + pixels);
    const gum = await evaljs(a, `window.__mediaRequests`);
    assert.equal(gum, 0);
    await shot(a, 'vtuber-display-fox93.png');
    clearInterval(timer);
    pub.close();

    await a.send('Page.navigate', { url: `${base}/?role=display&obs=1&char=male1` });
    await waitFor(a, `window.__char === 'male1' && document.getElementById('char').value === 'male1'`, 20000);
    const maleNeutral = await evaljs(a, `(() => { const c = document.getElementById('c'); const d = c.getContext('2d').getImageData(0,0,c.width,c.height).data; let n=0; for (let i=0;i<d.length;i+=16) n = (n + d[i] + d[i+1] + d[i+2]) >>> 0; return n; })()`);
    const malePub = new WebSocket(`ws://127.0.0.1:${httpPort}/ws`);
    await once(malePub, 'open');
    malePub.send(JSON.stringify({ type: 'hello', role: 'track', room: 'vtuber' }));
    const maleFine = { jaw: 0.9, smile: 0.4, frown: 0, funnel: 0, close: 0, openL: 0, openR: 1, gx: 0.8, gy: 0, browIn: 0, browOut: 0.2, browDown: 0, yaw: 18, pitch: 4, roll: 0, wink: 'L' };
    const maleTimer = setInterval(() => {
      malePub.send(JSON.stringify({
        type: 'state', room: 'vtuber',
        payload: {
          kind: 'vtuber', seq: 3, face: true,
          b: { jaw: 0.9, funnel: 0, smile: 0.4, blink: 0.5, blinkL: 1, blinkR: 0, gx: 0.8, gy: 0, browDown: 0, browOuter: 0.2, brow: 0, wide: 0, yaw: 18, pitch: 4, roll: 0, stretch: 0, smileAsym: 0, puff: 0, squint: 0 },
          fine: maleFine, micOn: false, micScore: 0, expr: 'auto', react: null,
          cfg: { char: 'male1', mirror: false, choppy: true, breath: true, autoBlink: true, micExpr: false, props: [] },
        },
      }));
    }, 40);
    await waitFor(a, `document.getElementById('pose').textContent.includes('18.0')`, 6000);
    const maleMoved = await evaljs(a, `(() => { const c = document.getElementById('c'); const d = c.getContext('2d').getImageData(0,0,c.width,c.height).data; let n=0; for (let i=0;i<d.length;i+=16) n = (n + d[i] + d[i+1] + d[i+2]) >>> 0; return n; })()`);
    assert.notEqual(maleMoved, maleNeutral);
    assert.equal(await evaljs(a, `window.__mediaRequests`), 0);
    const maleUrls = await evaljs(a, `window.__linkUrls`);
    assert.match(maleUrls.track, /char=male1/);
    assert.match(maleUrls.display, /role=display/);
    assert.match(maleUrls.display, /char=male1/);
    await shot(a, 'vtuber-display-male1.png');
    clearInterval(maleTimer);
    malePub.close();

    await b.send('Page.navigate', { url: `${base}/player/?role=control&shuffle=0&vol=0.5&cat=opening` });
    await a.send('Page.navigate', { url: `${base}/player/?role=display&obs=1` });
    await waitFor(b, `window.__pv && document.getElementById('title').textContent.includes('문이 열리는 시간')`);
    await evaljs(b, `localStorage.setItem('pvp_only_control', 'chrome-b')`);
    await waitFor(a, `document.documentElement.dataset.track && document.documentElement.dataset.track.includes('문이 열리는 시간')`, 8000);
    const secret = await evaljs(a, `localStorage.getItem('pvp_only_control')`);
    assert.equal(secret, null);
    const listen = await waitFor(a, `document.getElementById('cover').classList.contains('listen')`, 4000);
    assert.equal(listen, true);
    await evaljs(b, `(() => { const v = document.getElementById('vol'); v.value = '0.2'; v.oninput({ target: v }); })()`);
    await waitFor(a, `Math.abs(parseFloat(document.getElementById('vol').value) - 0.2) < 0.02`);
    const owners = await evaljs(a, `document.documentElement.dataset.audible`);
    const ownerB = await evaljs(b, `document.documentElement.dataset.audible`);
    assert.equal(Number(owners === '1') + Number(ownerB === '1'), 1, `display ${owners} control ${ownerB}`);
    const displayMuted = await evaljs(a, `window.__pv.audio.muted`);
    const controlMuted = await evaljs(b, `window.__pv.audio.muted`);
    assert.notEqual(displayMuted, controlMuted);
    await shot(a, 'player-display.png');
    await shot(b, 'player-control.png');
    await b.send('Page.navigate', { url: `${base}/?demo=1&char=test` });
    await waitFor(b, `window.__frames > 5`);
    const demoPixels = await evaljs(b, `(() => { const c = document.getElementById('c'); const d = c.getContext('2d').getImageData(0,0,c.width,c.height).data; let n=0; for (let i=3;i<d.length;i+=4) if (d[i]>0) n++; return n; })()`);
    assert.ok(demoPixels > 20, 'demo pixels ' + demoPixels);
  } finally {
    a.ws.close();
    b.ws.close();
    chromeA.kill();
    chromeB.kill();
    relay.proc.kill();
    await Promise.race([once(relay.proc, 'exit'), sleep(1000)]);
  }
});
