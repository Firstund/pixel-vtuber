// Local-only state link. OBS CEF and Chrome do not share localStorage or BroadcastChannel.
// Payloads are small JSON (no camera frames, no audio samples).

export const BLEND_KEYS = Object.freeze([
  'jaw', 'funnel', 'smile', 'blink', 'blinkL', 'blinkR', 'gx', 'gy',
  'browDown', 'browOuter', 'brow', 'wide', 'yaw', 'pitch', 'roll',
  'stretch', 'smileAsym', 'puff', 'squint',
]);

const LOOPBACK = new Set(['127.0.0.1', 'localhost', '::1', '[::1]']);
export const DEFAULT_CHAR = 'fox92';

export function packBlend(b) {
  const o = {};
  for (const k of BLEND_KEYS) {
    const n = Number(b?.[k]);
    o[k] = Number.isFinite(n) ? Math.round(Math.max(-180, Math.min(180, n)) * 1000) / 1000 : 0;
  }
  return o;
}

/** Playback position implied by a controller snapshot. Same PC clock as the sender. */
export function expectedOffset(s, nowMs) {
  const base = Math.max(0, Number(s?.offset) || 0);
  if (!s?.playing) return base;
  const sent = Number(s.sentAt);
  if (!Number.isFinite(sent)) return base;
  const dt = (Number(nowMs) - sent) / 1000;
  if (!Number.isFinite(dt) || dt < 0) return base;
  return base + Math.min(dt, 30);
}

/**
 * Who should emit sound.
 * standalone → this page (old behavior).
 * split roles → only the client the relay marked youAudible.
 */
export function outputMode({ role, youAudible }) {
  if (role !== 'control' && role !== 'display') return 'local';
  return youAudible ? 'this' : 'mute';
}

export function wsUrlFromLocation(loc, params) {
  const relay = params?.get?.('relay') || '';
  if (relay) return relay;
  if (!LOOPBACK.has(loc.hostname)) return '';
  const proto = loc.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${proto}//${loc.host}/ws`;
}

function pageDir(loc) {
  const u = new URL(loc.href);
  u.search = '';
  u.hash = '';
  if (!u.pathname.endsWith('/')) u.pathname = u.pathname.replace(/[^/]*$/, '');
  return u.toString().replace(/\/$/, '');
}

export function splitPageUrls(loc, opt = {}) {
  const onLoop = LOOPBACK.has(loc.hostname);
  const port = opt.port || '8765';
  let root;
  if (onLoop) {
    const base = pageDir(loc);
    root = base.endsWith('/player') ? base.slice(0, -'/player'.length) : base;
  } else {
    root = `http://127.0.0.1:${port}`;
  }
  const char = encodeURIComponent(opt.char || DEFAULT_CHAR);
  return {
    root,
    track: `${root}/?role=track&char=${char}`,
    display: `${root}/?role=display&obs=1&char=${char}`,
    legacy: `${root}/?obs=1&char=${char}`,
    control: `${root}/player/?role=control&shuffle=1&vol=0.5`,
    playerDisplay: `${root}/player/?role=display&obs=1`,
  };
}

export function createLink(opts) {
  const WS = opts.WebSocket || globalThis.WebSocket;
  if (!WS) throw new Error('WebSocket unavailable');
  let ws = null;
  let stopped = false;
  let attempt = 0;
  let timer = null;
  let connected = false;

  function setStatus(state) {
    connected = state === 'open';
    opts.onStatus?.({ state, attempt, connected });
  }

  function connect() {
    if (stopped) return;
    setStatus('connecting');
    let sock;
    try { sock = new WS(opts.url); }
    catch { schedule(); return; }
    ws = sock;
    sock.onopen = () => {
      attempt = 0;
      try { sock.send(JSON.stringify({ type: 'hello', role: opts.role, room: opts.room })); }
      catch { /* closed in the same turn */ }
      setStatus('open');
    };
    sock.onmessage = (ev) => {
      if (typeof ev.data !== 'string') return;
      let msg;
      try { msg = JSON.parse(ev.data); }
      catch { return; }
      opts.onMessage?.(msg);
    };
    sock.onerror = () => {};
    sock.onclose = () => {
      if (ws === sock) ws = null;
      setStatus('closed');
      schedule();
    };
  }

  function schedule() {
    if (stopped) return;
    const delay = Math.min(5000, 200 * 2 ** Math.min(attempt, 5));
    attempt += 1;
    timer = setTimeout(connect, delay);
  }

  function send(obj) {
    if (!ws || ws.readyState !== 1) return false;
    try { ws.send(JSON.stringify(obj)); return true; }
    catch { return false; }
  }

  function close() {
    stopped = true;
    if (timer) clearTimeout(timer);
    timer = null;
    try { ws?.close(); } catch { /* already closed */ }
    ws = null;
    connected = false;
  }

  connect();
  return {
    send,
    close,
    get connected() { return connected; },
  };
}
