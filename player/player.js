import { createLink, expectedOffset, splitPageUrls, wsUrlFromLocation } from '../js/link.js?v=20261106-link';

const $ = id => document.getElementById(id), P = new URLSearchParams(location.search);
const ROLE = P.get('role') || '';
const OBS = P.get('obs') === '1';
if (OBS) document.body.classList.add('obs');
document.body.classList.add(ROLE === 'display' ? 'role-display' : ROLE === 'control' ? 'role-control' : 'role-standalone');
document.documentElement.dataset.role = ROLE || 'standalone';
// 오프닝은 카테고리 이름이 아니다. 쓰시던 ?cat=오프닝 은 출근 도장(id=opening)으로 본다.
const CAT_ALIAS = { '오프닝': 'opening' };
const catWant = raw => (raw && CAT_ALIAS[raw]) || raw;
const LS = {
  get: k => { try { return localStorage.getItem('pvp_' + k); } catch (e) { return null; } },
  set: (k, v) => { try { localStorage.setItem('pvp_' + k, v); } catch (e) {} },
};
const audio = new Audio();
audio.preload = 'auto';
let youAudible = ROLE !== 'display';
let audioBlocked = false;
let peersReady = ROLE !== 'control' && ROLE !== 'display';
let link = null, linkOpen = false, lastSnap = null, pendingSnap = null;
let cats = [], ci = 0, ti = 0, order = [], oi = 0, shuffle = P.get('shuffle') === '1';
const volFallback = ROLE === 'display' ? '0.6' : (LS.get('vol') ?? '0.6');
let vol = parseFloat(P.get('vol') ?? volFallback);
if (isNaN(vol)) vol = 0.6;
vol = Math.min(1, Math.max(0, vol));
const CARD = P.get('skin') !== 'classic';
if (CARD) document.body.classList.add('skin-card');
let fadeT = null, playing = false;
const N = CARD ? 12 : 30;
$('bar').innerHTML = '<i></i>'.repeat(N);
const cells = [...$('bar').children];
const fmt = s => { s = Math.floor(s || 0); return String(Math.floor(s / 60)).padStart(2, '0') + ':' + String(s % 60).padStart(2, '0'); };
function fade(to, ms = 600) {
  return new Promise(r => {
    clearInterval(fadeT);
    const from = audio.volume, t0 = performance.now();
    fadeT = setInterval(() => {
      const k = Math.min(1, (performance.now() - t0) / ms);
      audio.volume = from + (to - from) * k;
      if (k >= 1) { clearInterval(fadeT); r(); }
    }, 30);
  });
}
(function () {
  const c = $('fox').getContext('2d'), m = ['....o......o....', '...oo......oo...', '...oco....oco...', '..oooooooooooo..', '..oooooooooooo..', '.oowwooooooowwo.', '.oowkwooooowkwo.', '.ooowwooooowwoo.', '..ooooooooooooo.', '..oowwwwwwwwoo..', '...owwwkkwwwo...', '....owwwwwwo....', '.....oooooo.....', '....pp....pp....', '...ppp....ppp...', '................'];
  const col = { o: '#ff8a4c', c: '#fff1d6', w: '#fff1d6', k: '#3a2550', p: '#ffb36b' };
  m.forEach((r, y) => [...r].forEach((ch, x) => { if (col[ch]) { c.fillStyle = col[ch]; c.fillRect(x, y, 1, 1); } }));
})();
function buildOrder() {
  const n = cats[ci]?.tracks.length || 0;
  order = [...Array(n).keys()];
  if (shuffle && ROLE !== 'display') {
    for (let i = n - 1; i > 0; i--) { const j = Math.random() * (i + 1) | 0; [order[i], order[j]] = [order[j], order[i]]; }
  }
  oi = 0;
}
function render() {
  const c = cats[ci];
  $('cat').textContent = c ? c.name : '-';
  $('tabs').innerHTML = '';
  cats.forEach((k, i) => {
    const b = document.createElement('button');
    b.textContent = (i + 1) + '. ' + k.name;
    if (i === ci) b.className = 'act';
    b.onclick = () => setCat(i, true);
    $('tabs').append(b);
  });
  const l = $('list');
  l.innerHTML = '';
  if (!c || !c.tracks.length) l.innerHTML = '<li class="empty">음악을 추가해 주세요</li>';
  else c.tracks.forEach((t, i) => {
    const li = document.createElement('li');
    li.textContent = t.title;
    if (i === ti && audio.src) li.className = 'cur';
    li.onclick = () => { if (ROLE === 'display') return; oi = order.indexOf(i); load(i, true); };
    l.append(li);
  });
  $('pp').textContent = playing ? '⏸ 일시정지' : '▶ 재생';
  $('hpp').textContent = playing ? '⏸' : '▶';
  $('shuf').checked = shuffle;
  $('vol').value = vol;
  document.documentElement.dataset.playing = playing ? '1' : '0';
  document.documentElement.dataset.audible = youAudible ? '1' : '0';
  document.documentElement.dataset.track = c?.tracks[ti]?.title || '';
  document.documentElement.dataset.cat = c?.id || '';
  coverState();
}
const DEF = 'cover/fox_cover.png', BLK = 'cover/fox_cover_blink.png';
let covDef = true;
function setCover(u) {
  const im = $('covimg');
  covDef = !u;
  im.src = u ? encodeURI(u) : DEF;
  coverState && setTimeout(coverState);
  im.onerror = () => { if (!covDef) { covDef = true; im.src = DEF; } };
}
const HAP = 'cover/fox_cover_happy.png';
function coverState() {
  if (!CARD) return;
  const L = covDef && playing, cv = $('cover'), im = $('covimg');
  cv.classList.toggle('listen', L);
  if (covDef) { const w = L ? HAP : DEF; if (!im.src.endsWith(w)) im.src = w; }
}
if (CARD) {
  setCover();
  [BLK, HAP].forEach(u => new Image().src = u);
  (function blink() {
    setTimeout(() => {
      const im = $('covimg');
      if (covDef && !playing) { im.src = BLK; setTimeout(() => { if (covDef && !playing) im.src = DEF; }, 150); }
      blink();
    }, 2500 + Math.random() * 3000);
  })();
  (function note() {
    setTimeout(() => {
      const n = $('note');
      if (covDef && playing) {
        n.style.left = (Math.random() < .5 ? 2 + Math.random() * 8 : 90 + Math.random() * 8 | 0) + 'px';
        n.classList.remove('up'); void n.offsetWidth; n.classList.add('up');
      }
      note();
    }, 2200 + Math.random() * 2500);
  })();
}
function setTitle(t) {
  const mq = $('mq'), s = $('title');
  s.textContent = t;
  mq.classList.remove('run');
  requestAnimationFrame(() => {
    if (s.scrollWidth > mq.clientWidth) { mq.style.setProperty('--d', (s.scrollWidth / 40 + 4) + 's'); mq.classList.add('run'); }
  });
}
function snapshot() {
  const c = cats[ci], t = c?.tracks[ti];
  return {
    kind: 'player', playing, ci, ti, oi,
    catId: c?.id || '', catName: c?.name || '',
    file: t?.file || '', title: t?.title || '',
    order: order.slice(), shuffle, vol,
    offset: audio.currentTime || 0,
    dur: Number.isFinite(audio.duration) ? audio.duration : 0,
    sentAt: Date.now(),
  };
}
function publish() {
  if (ROLE !== 'control' || !link?.connected) return false;
  return link.send({ type: 'state', room: 'player', payload: snapshot() });
}
function reportMedia(state) {
  if (ROLE !== 'display' || !link?.connected) return;
  link.send({ type: 'media', room: 'player', audio: state });
}
function applyAudible() {
  const wasMuted = audio.muted;
  audio.muted = !youAudible;
  document.documentElement.dataset.audible = youAudible ? '1' : '0';
  document.body.classList.toggle('audio-blocked', !!(audioBlocked && youAudible));
  if (!youAudible) { clearInterval(fadeT); audio.volume = 0; }
  else if (playing) {
    audio.volume = vol;
    if (wasMuted && navigator.userActivation && !navigator.userActivation.hasBeenActive) $('start').classList.remove('hidden');
  }
}
function hasFile(file) {
  if (!file || !audio.src) return false;
  try { return decodeURIComponent(audio.src).endsWith(file); }
  catch { return audio.src.endsWith(file); }
}
function waitMeta() {
  return new Promise(res => {
    if (audio.readyState >= 1) return res();
    const t = setTimeout(res, 2500);
    const done = () => { clearTimeout(t); res(); };
    audio.addEventListener('loadedmetadata', done, { once: true });
    audio.addEventListener('error', done, { once: true });
  });
}
let applyChain = Promise.resolve();
function applyRemote(s) {
  if (!s) return;
  lastSnap = s;
  applyChain = applyChain.then(() => applyRemoteNow(s)).catch(e => console.warn('player sync', e));
}
async function applyRemoteNow(s) {
  if (s.kind !== 'player') return;
  if (!cats.length || !peersReady) { pendingSnap = s; return; }
  if (pendingSnap === s) pendingSnap = null;
  const want = s.catId || s.catName;
  let i = cats.findIndex(c => c.id === want || c.name === want);
  if (i < 0) i = Math.max(0, Math.min(Math.max(cats.length - 1, 0), s.ci | 0));
  const n = cats[i]?.tracks.length || 0;
  ci = i;
  shuffle = !!s.shuffle;
  if (Array.isArray(s.order) && n && s.order.length === n) order = s.order.slice();
  else if (order.length !== n) buildOrder();
  ti = n ? Math.max(0, Math.min(n - 1, s.ti | 0)) : 0;
  oi = Math.max(0, order.indexOf(ti));
  vol = Math.max(0, Math.min(1, Number(s.vol) || 0));
  playing = !!s.playing;
  const track = n ? cats[ci].tracks[ti] : null;
  if (CARD && track) setCover(track.cover || cats[ci].cover);
  if (track && !hasFile(track.file)) {
    audio.src = encodeURI(track.file);
    audio.volume = 0;
    await waitMeta();
  }
  let exp = expectedOffset(s, Date.now());
  if (Number.isFinite(audio.duration) && audio.duration > 0) {
    exp = Math.min(exp, Math.max(0, audio.duration - 0.05));
    if (Math.abs((audio.currentTime || 0) - exp) > 0.35) {
      try { audio.currentTime = exp; } catch { /* metadata not ready yet */ }
    }
  }
  setTitle(track ? (s.title || track.title) : '음악을 추가해 주세요');
  render();
  if (playing && audio.paused) {
    if (youAudible && audioBlocked) $('start').classList.remove('hidden');
    else await start(false);
  } else if (!playing && !audio.paused) audio.pause();
  else applyAudible();
}
async function load(i, play) {
  const c = cats[ci];
  if (!c || !c.tracks.length) {
    audio.pause(); audio.removeAttribute('src'); playing = false;
    setTitle('음악을 추가해 주세요'); $('dur').textContent = '00:00'; $('cur').textContent = '00:00';
    upd(); render(); publish(); return;
  }
  if (playing && !audio.paused) await fade(0, 500);
  ti = i;
  const t = c.tracks[i];
  if (CARD) setCover(t.cover || c.cover);
  const w = $('widget');
  w.classList.remove('swap'); void w.offsetWidth; w.classList.add('swap');
  setTimeout(() => setTitle(t.title), 300);
  audio.src = encodeURI(t.file);
  audio.volume = 0;
  render();
  if (play) await start(false);
  else publish();
}
async function start(fromGesture) {
  if (!audio.src) return;
  if (fromGesture) audioBlocked = false;
  audio.muted = !youAudible;
  try {
    await audio.play();
    if (ROLE !== 'display') playing = true;
    $('start').classList.add('hidden');
    if (youAudible) {
      audioBlocked = false;
      fade(vol, 800);
      if (ROLE === 'display') reportMedia('ok');
    } else audio.volume = 0;
    document.documentElement.dataset.audioBlocked = '0';
  } catch (e) {
    if (ROLE !== 'display') playing = false;
    if (youAudible) {
      audioBlocked = true;
      $('start').classList.remove('hidden');
      document.documentElement.dataset.audioBlocked = '1';
      if (ROLE === 'display') reportMedia('blocked');
      const note = $('obsNote');
      if (note) note.textContent = '소리가 막혔습니다. OBS 소스 우클릭 → 상호작용 → 재생을 한 번 누르세요.';
    }
  }
  document.body.classList.toggle('audio-blocked', !!(audioBlocked && youAudible));
  render();
  publish();
}
async function pause() {
  if (ROLE === 'display') return;
  playing = false; render();
  await fade(0, 500);
  audio.pause();
  publish();
}
function toggle() { playing ? pause() : (audio.src ? start(true) : load(order[oi] ?? 0, true)); }
function step(d) {
  if (ROLE === 'display') return;
  const n = order.length;
  if (!n) return;
  oi = (oi + d + n) % n;
  if (d > 0 && oi === 0 && shuffle) buildOrder();
  load(order[oi], true);
}
function setCat(i, play) {
  if (ROLE === 'display' || !cats[i]) return;
  ci = i;
  LS.set('cat', cats[i].id);
  buildOrder();
  load(order[0] ?? 0, play ?? playing);
}
function setVol(v) {
  vol = Math.round(Math.min(1, Math.max(0, v)) * 100) / 100;
  if (ROLE !== 'display') LS.set('vol', vol);
  clearInterval(fadeT);
  if (playing && youAudible) audio.volume = vol;
  render();
  publish();
}
function upd() {
  const d = audio.duration || 0, t = audio.currentTime || 0;
  $('cur').textContent = fmt(t);
  $('dur').textContent = fmt(d);
  const on = d ? Math.floor(t / d * N) : 0;
  cells.forEach((c, i) => c.classList.toggle('on', i < on));
  if (CARD) placeSun(on);
}
function placeSun(on) {
  const c = cells[Math.max(0, Math.min(N, on) - 1)], sn = $('sun'), ir = sn.parentNode.getBoundingClientRect(), r = c.getBoundingClientRect();
  sn.style.left = Math.round(r.left - ir.left + r.width / 2 - 6) + 'px';
  sn.style.top = Math.round(r.top - ir.top + r.height / 2 - 6) + 'px';
}
audio.addEventListener('timeupdate', upd);
audio.addEventListener('loadedmetadata', upd);
audio.addEventListener('ended', () => { if (ROLE !== 'display') step(1); });
audio.addEventListener('error', () => {
  console.warn('재생 실패:', audio.src);
  if (ROLE === 'display') return;
  if (order.length > 1) setTimeout(() => step(1), 1000);
});
document.addEventListener('click', e => {
  const a = e.target.closest('[data-a]')?.dataset.a;
  if (!a || ROLE === 'display') return;
  ({ prev: () => step(-1), next: () => step(1), toggle, cat: () => setCat((ci + 1) % cats.length, playing) })[a]();
});
$('shuf').onchange = e => {
  if (ROLE === 'display') { e.target.checked = shuffle; return; }
  shuffle = e.target.checked;
  buildOrder();
  oi = Math.max(0, order.indexOf(ti));
  publish();
};
$('vol').oninput = e => { if (ROLE === 'display') return; setVol(+e.target.value); };
$('start').onclick = async () => {
  // A click is the user gesture Chromium needs before it will unmute.
  if (ROLE === 'display' && link?.connected) link.send({ type: 'media', room: 'player', audio: 'ok' });
  await new Promise(r => setTimeout(r, 80));
  start(true);
};
document.addEventListener('keydown', e => {
  if (ROLE === 'display') return;
  if (e.target.tagName === 'INPUT' && e.target.type !== 'checkbox' && e.target.type !== 'range') return;
  if (e.code === 'Space') { e.preventDefault(); toggle(); }
  else if (e.key === 'ArrowRight') step(1);
  else if (e.key === 'ArrowLeft') step(-1);
  else if (e.key === 'ArrowUp') { e.preventDefault(); setVol(vol + .05); }
  else if (e.key === 'ArrowDown') { e.preventDefault(); setVol(vol - .05); }
  else if (/^[1-9]$/.test(e.key)) setCat(+e.key - 1, true);
});
function setupLink() {
  const urls = splitPageUrls(location, { port: location.port || '8765' });
  if ($('urlControl')) $('urlControl').value = urls.control;
  if ($('urlDisplay')) $('urlDisplay').value = urls.playerDisplay;
  const local = ['127.0.0.1', 'localhost', '::1'].includes(location.hostname);
  const steps = '음악 플레이어는 카메라를 쓰지 않습니다. OBS와 크롬은 저장소·단축키가 따로라 곡 정보가 넘어가지 않습니다. ① start-vtuber.bat 또는 py -3 tools/vtuber_relay.py ② 크롬은 조작 주소 ③ OBS 브라우저 소스에는 OBS 주소. 소리는 연결된 OBS 창 하나만 냅니다. 방송에 넣으려면 그 소스의 "OBS에서 오디오 제어"(Control audio via OBS)를 켜세요.';
  if ($('linkHelp')) $('linkHelp').textContent = (local ? '' : 'GitHub Pages에서는 로컬 중계 접속이 막힙니다. 아래 127.0.0.1 주소를 쓰세요. ') + steps;
  const copy = async (id, label) => {
    const text = $(id)?.value || '';
    try { await navigator.clipboard.writeText(text); if ($('linkStatus')) $('linkStatus').textContent = label; }
    catch { if ($('linkHelp')) $('linkHelp').textContent = text; }
  };
  if ($('copyControl')) $('copyControl').onclick = () => copy('urlControl', '조작 주소를 복사했습니다');
  if ($('copyDisplay')) $('copyDisplay').onclick = () => copy('urlDisplay', 'OBS 주소를 복사했습니다');
  if (ROLE !== 'control' && ROLE !== 'display') {
    if ($('linkStatus')) { $('linkStatus').textContent = '단독 재생'; $('linkStatus').className = 'ok'; }
    return;
  }
  const ws = wsUrlFromLocation(location, P);
  if (!ws) {
    if ($('linkStatus')) { $('linkStatus').textContent = '로컬 중계 주소가 아닙니다'; $('linkStatus').className = 'bad'; }
    document.body.classList.add('link-bad');
    const note = $('obsNote');
    if (note) note.textContent = '127.0.0.1 로 다시 여세요. 이 주소는 중계에 연결되지 않습니다.';
    return;
  }
  link = createLink({
    url: ws, role: ROLE, room: 'player',
    onStatus(s) {
      linkOpen = s.state === 'open';
      document.documentElement.dataset.link = s.state;
      document.body.classList.toggle('link-bad', s.state === 'closed');
      document.body.classList.toggle('link-ok', s.state === 'open');
      if ($('linkStatus')) {
        $('linkStatus').className = s.state === 'open' ? 'ok' : s.state === 'closed' ? 'bad' : '';
        if (s.state !== 'open') $('linkStatus').textContent = s.state === 'closed' ? '중계 끊김 · 재연결 중' : '중계 연결 중…';
      }
      const note = $('obsNote');
      if (note && ROLE === 'display' && s.state === 'closed') note.textContent = '중계 끊김 · 재연결 중';
    },
    onMessage(msg) {
      if (msg.type === 'peers') {
        peersReady = true;
        youAudible = !!msg.youAudible;
        applyAudible();
        const n = msg.roles || {};
        if (ROLE === 'control' && linkOpen && $('linkStatus')) {
          $('linkStatus').textContent = `중계 연결됨 · 표시 ${n.display || 0} · ${youAudible ? '이 창에서 소리' : 'OBS에서 소리'}`;
          $('linkStatus').className = 'ok';
        }
        if (pendingSnap && ROLE === 'display') applyRemote(pendingSnap);
      }
      if (msg.type === 'state' && ROLE === 'display') applyRemote(msg.payload);
    },
  });
}
setupLink();
setInterval(() => {
  if (ROLE === 'control' && playing && linkOpen) publish();
  if (ROLE === 'display' && lastSnap && audio.paused) {
    const exp = expectedOffset(lastSnap, Date.now());
    const dur = Number.isFinite(audio.duration) && audio.duration > 0 ? audio.duration : (lastSnap.dur || 0);
    $('cur').textContent = fmt(exp);
    $('dur').textContent = fmt(dur);
    const on = dur ? Math.floor(Math.min(exp, dur) / dur * N) : 0;
    cells.forEach((c, i) => c.classList.toggle('on', i < on));
    if (CARD) placeSun(on);
  }
}, 400);
function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }
function waitPeers(ms) {
  if (peersReady) return Promise.resolve();
  return new Promise(res => {
    const t0 = performance.now();
    const t = setInterval(() => {
      if (peersReady || performance.now() - t0 > ms) { clearInterval(t); res(); }
    }, 30);
  });
}
fetch(P.get('tracks') || 'tracks.json', { cache: 'no-cache' }).then(r => r.json()).then(async j => {
  cats = j.categories || [];
  const raw = ROLE === 'display' ? P.get('cat') : (P.get('cat') || LS.get('cat'));
  const want = catWant(raw);
  const i = cats.findIndex(c => c.id === want || c.name === want);
  ci = i < 0 ? 0 : i;
  buildOrder();
  if (ROLE === 'control') await waitPeers(800);
  await load(order[0] ?? 0, ROLE !== 'display');
  if (pendingSnap) await applyRemoteNow(pendingSnap);
}).catch(e => { console.error('tracks.json 불러오기 실패', e); setTitle('tracks.json 오류'); });
window.__pv = {
  audio, step, role: ROLE,
  get state() { return { ci, ti, playing, youAudible, vol, shuffle, cat: cats[ci]?.id || '' }; },
};
