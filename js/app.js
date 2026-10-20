// 픽셀 VTuber — 프레임 교체 리깅. 머리 각도는 전용 스프라이트(요 5 × 피치 3)로 "끊어서" 전환.
const MP_VER = '0.10.14';
const MP_URL = `https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@${MP_VER}`;
const MODEL_URL = 'https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task';
const $ = id => document.getElementById(id);
const params = new URLSearchParams(location.search);
const canvas = $('c'), ctx = canvas.getContext('2d');
const video = $('video');
const off = document.createElement('canvas'), octx = off.getContext('2d');      // 원본 해상도 합성
const hc = document.createElement('canvas'), hctx = hc.getContext('2d');        // 머리 그룹 (롤 회전용)
import { mic, startMic, micTick } from './mic.js?v=20261021-fox62';
import { createTail, tailStep } from './tail.js?v=20261021-fox62';
const CHARS = { fox62: 'assets/fox62/', fox61: 'assets/fox61/', fox6: 'assets/fox6/', fox53: 'assets/fox53/', fox52: 'assets/fox52/', fox51: 'assets/fox51/', fox5: 'assets/fox5/', fox4: 'assets/fox4/', fox3: 'assets/fox3/', fox2: 'assets/fox2/', test: 'assets/test/' };
let ch = null; // {key, base, m, img, S}

// ---------- 캐릭터 로드 ----------
async function loadChar(key) {
  const base = CHARS[key] || CHARS.fox62;
  const m = await (await fetch(base + 'manifest.json')).json();
  const img = {};
  await Promise.all(m.layers.map(n => new Promise((res, rej) => {
    const i = new Image(); i.onload = res; i.onerror = () => rej(new Error('asset ' + n)); i.src = base + n + '.png'; img[n] = i;
  })));
  ch = { key, base, m, img, S: m.S, nYaw: m.yaw.length, nPitch: m.pitch.length };
  for (const c of [off, hc]) { c.width = c.height = ch.S; }
  octx.imageSmoothingEnabled = hctx.imageSmoothingEnabled = false;
  resize();
  window.__char = key;
}

// ---------- 설정 UI ----------
const cfg = {};
for (const id of ['tMouth', 'tBlink', 'tSmile', 'smooth', 'animFps', 'micSens']) {
  const el = $(id), out = el.nextElementSibling;
  const upd = () => { cfg[id] = parseFloat(el.value); out.textContent = el.value; };
  el.addEventListener('input', upd); upd();
}
cfg.choppy = $('choppy').checked; $('choppy').onchange = e => { cfg.choppy = e.target.checked; };
cfg.micExpr = $('micExpr').checked; $('micExpr').onchange = e => { cfg.micExpr = e.target.checked; };
$('micBtn').onclick = async () => {
  $('micBtn').disabled = true; showErr('');
  if (await startMic()) { $('micBtn').textContent = '🎤 마이크 켜짐'; $('meter').hidden = false; }
  else { showErr(mic.err); $('micBtn').disabled = false; }
};
cfg.mirror = $('mirror').checked; $('mirror').onchange = e => { cfg.mirror = e.target.checked; };
if (params.get('mirror') === '0') { $('mirror').checked = false; cfg.mirror = false; }
if (params.get('choppy') === '0') { $('choppy').checked = false; cfg.choppy = false; }
const setBg = c => { document.body.style.background = c; $('bg').value = c; };
$('bg').addEventListener('input', e => setBg(e.target.value));
$('green').onclick = () => setBg('#00ff00');
if (params.get('bg')) setBg('#' + params.get('bg').replace('#', ''));
$('preview').onchange = e => document.body.classList.toggle('preview', e.target.checked);
const setClean = on => document.body.classList.toggle('clean', on);
$('clean').onclick = () => setClean(true);
if (params.get('clean') === '1') setClean(true);
document.addEventListener('keydown', e => {
  if (e.key === 'Escape' || e.key === 'h') setClean(!document.body.classList.contains('clean') && e.key === 'h');
  const k = { '1': 'auto', '2': 'happy', '3': 'tired', '4': 'surprised', '5': 'smug' }[e.key]; if (k) setExpr(k);
});
let lastTap = 0;
$('stage').addEventListener('pointerup', () => { const t = performance.now(); if (t - lastTap < 350) setClean(false); lastTap = t; });
document.addEventListener('dblclick', () => setClean(false));
const status = s => { $('status').textContent = s; };
const showErr = s => { const e = $('err'); e.hidden = !s; e.textContent = s || ''; };
let exprOverride = 'auto';
function setExpr(k) { exprOverride = k; document.querySelectorAll('#expr button').forEach(b => b.classList.toggle('on', b.dataset.e === k)); }
document.querySelectorAll('#expr button').forEach(b => b.onclick = () => setExpr(b.dataset.e));
$('char').onchange = async e => { await loadChar(e.target.value); };

// ---------- 캔버스 크기 (정수 배율만) ----------
let scale = 4;
function resize() {
  if (!ch) return;
  const r = $('stage').getBoundingClientRect(), dpr = window.devicePixelRatio || 1;
  scale = Math.max(1, Math.floor(Math.min(r.width, r.height) * dpr / ch.S));
  canvas.width = canvas.height = ch.S * scale;
  canvas.style.width = canvas.style.height = (ch.S * scale / dpr) + 'px';
  ctx.imageSmoothingEnabled = false;
}
new ResizeObserver(resize).observe($('stage'));

// ---------- 스무딩 / 히스테리시스 ----------
const sm = { stretch: 0, asym: 0, puff: 0, squint: 0, jaw: 0, funnel: 0, smile: 0, blink: 0, brow: 0, wide: 0, yaw: 0, pitch: 0, roll: 0 };
function smooth(key, v, k = cfg.smooth) { sm[key] = sm[key] * k + v * (1 - k); return sm[key]; }
// 오름차순 경계값 ths, 현재 레벨 cur 기준 ±h 여유(데드존)를 둔 레벨
function level(v, cur, ths, h) {
  let l = cur;
  while (l < ths.length && v > ths[l] + h) l++;
  while (l > 0 && v < ths[l - 1] - h) l--;
  return l;
}
const YAW_TH = [-25, -10, 10, 25], YAW_H = 4;   // 도(deg)
const PIT_TH = [-10, 10], PIT_H = 3;
const ROLL_TH = [-9, 9], ROLL_H = 3, ROLL_DEG = 9;
const HOLD_MS = 100;  // 한 단계에 최소 머무는 시간
const pose = { yawL: 2, pitL: 1, rollL: 1, k: 0, p: 0, r: 0, shown: { k: 0, p: 0, r: 0 }, changedAt: { k: 0, p: 0, r: 0 }, lastTick: 0, tick: 0 };
const st = { eye: 0, mouth: 0, brow: 0, ears: 0, sparkle: false, expr: 'auto' };
let mouthLv = 0, eyeLv = 0;
const exc = { since: 0, calmSince: 0, hi: false };

// v6.2: 큰 입 — 벌림 5단계 + 모양(오/이/웃음/한쪽웃음/볼부풀림), 히스테리시스로 계단식 전환
const MV = { lv: 0, shape: 'n', since: 0 };
const MI = n => ch.m.mouth.indexOf(n);
const MSETS = { // 표정별 [닫힘, 작게, 중간, 크게, 아주 크게]
  auto: ['cat', 'o1', 'o2', 'o3', 'o4'], happy: ['smile_c', 'smile_m', 'smile_m', 'smile_b', 'smile_b'],
  tired: ['sigh', 'sigh', 'o2', 'yawn', 'yawn'], surprised: ['ro_s', 'ro_s', 'ro_b', 'ro_b', 'ro_b'], smug: ['smirk', 'grin', 'grin', 'grin', 'grin'],
};
function decideV2(b, jaw, fun, smi, ex, eye, browF) {
  const H = 0.04, t0 = cfg.tMouth;
  MV.lv = level(jaw, MV.lv, [t0 * 0.7, t0 * 1.5, t0 * 2.4, t0 * 3.4], H);
  const str = smooth('stretch', b.stretch || 0), asym = smooth('asym', b.smileAsym || 0), puff = smooth('puff', b.puff || 0), sq = smooth('squint', b.squint || 0);
  const hyst = (cur, name, v, th) => v > th + (cur === name ? -0.06 : 0.06);
  let shape = 'n';
  if (hyst(MV.shape, 'puff', puff, 0.4) && MV.lv <= 1) shape = 'puff';
  else if (hyst(MV.shape, 'o', fun, 0.35)) shape = 'o';
  else if (hyst(MV.shape, 'smile', smi, cfg.tSmile)) shape = 'smile';
  else if (hyst(MV.shape, 'asym', Math.abs(asym), 0.25)) shape = 'asym';
  else if (hyst(MV.shape, 'ee', str, 0.3) && MV.lv >= 1) shape = 'ee';
  MV.shape = shape;
  const lv = MV.lv; let name, blush = false;
  if (ex === 'auto') {
    if (shape === 'puff') { name = 'puff'; blush = true; }
    else if (shape === 'o') name = lv >= 2 ? 'ro_b' : 'ro_s';
    else if (shape === 'smile') { name = lv === 0 ? 'smile_c' : lv >= 3 ? 'smile_b' : 'smile_m'; blush = lv >= 3; }
    else if (shape === 'asym') name = lv === 0 ? 'smirk' : 'grin';
    else if (shape === 'ee') name = 'ee';
    else name = MSETS.auto[lv];
  } else name = (MSETS[ex] || MSETS.auto)[lv];
  // 눈을 입에 맞춰 미세 조정
  if (eye < 2) {
    if ((ex === 'happy' || shape === 'smile') && lv >= 3) eye = 3;                 // 크게 웃으면 ^^
    else if ((ex === 'surprised' || shape === 'o') && lv >= 3) eye = 5;             // 크게 놀라면 눈 크게
    else if (ex === 'auto' && sq > (eye === 1 ? 0.45 : 0.55)) eye = 1;              // 찡그림 → 가늘게
    else if (ex === 'auto' && b.brow > 0.55 && shape === 'n') { eye = 4; browF = 2; } // 걱정
  }
  if (ex === 'happy' && lv >= 3) blush = true;
  const mouth = Math.max(0, MI(name));
  window.__mv = { lv, shape, name, eye, blush };
  return { eye, mouth, browF, blush };
}
function decide(b, auto, t) {
  const jaw = smooth('jaw', b.jaw), fun = smooth('funnel', b.funnel), smi = smooth('smile', b.smile);
  const blink = smooth('blink', b.blink, Math.min(cfg.smooth, 0.3)); // 깜빡임은 빠르게
  const brow = smooth('brow', b.brow), wide = smooth('wide', b.wide || 0);
  const yaw = smooth('yaw', b.yaw), pitch = smooth('pitch', b.pitch), roll = smooth('roll', b.roll);
  const H = 0.04;
  // --- 입 (매 프레임, 반응 즉시)
  mouthLv = level(jaw, mouthLv, [cfg.tMouth, cfg.tMouth * 2.2], H);
  let mouth;
  if (mouthLv === 2) mouth = 2; else if (fun > 0.35 && mouthLv <= 1) mouth = 4; else if (mouthLv === 1) mouth = 1;
  else mouth = smi > cfg.tSmile + (st.mouth === 3 ? -H : H) ? 3 : 0;
  // --- 눈
  eyeLv = level(blink, eyeLv, [cfg.tBlink * 0.6, cfg.tBlink], H);
  if (auto) eyeLv = auto;
  let eye = [0, 1, 2][eyeLv], browF = brow > (st.brow ? 0.3 : 0.4) ? 1 : 0, ears = 0, sparkle = false;
  // --- 표정 (자동 판정 + 수동 고정)
  let ex = exprOverride;
  if (ex === 'auto') {
    if (jaw > 0.45 && (brow > 0.45 || wide > 0.4)) ex = 'surprised';
    else if (eyeLv === 0 && smi > cfg.tSmile + 0.25) ex = 'happy';
  }
  // --- 마이크 신남: 0.7초 이상 높으면 '웃음+반짝'으로, 충분히 차분해지면 해제 (히스테리시스)
  const e = mic.score;
  if (e > 0.6) { exc.calmSince = 0; if (!exc.since) exc.since = t; if (t - exc.since > 700) exc.hi = true; }
  else { exc.since = 0; if (e < 0.35) { if (!exc.calmSince) exc.calmSince = t; if (t - exc.calmSince > 1200) exc.hi = false; } else exc.calmSince = 0; }
  if (!mic.on) exc.hi = false;
  if (exc.hi && cfg.micExpr && exprOverride === 'auto' && ex === 'auto') ex = 'happy';
  if (ex === 'happy') { if (eyeLv === 0) eye = 3; sparkle = true; browF = 1; if (mouth === 0) mouth = 3; }
  if (ex === 'tired') { if (eyeLv < 2) eye = 4; browF = 2; ears = 1; }
  if (ex === 'surprised') { if (eyeLv < 2) eye = 5; browF = 1; mouth = mouth >= 1 ? 5 : 4; }
  if (ex === 'smug') { if (eyeLv < 2) eye = 6; browF = 3; if (mouth === 0 || mouth === 3) mouth = 6; }
  // 구버전 캐릭터: 없는 프레임은 대체
  const ne = ch.m.eyes.length, nm = ch.m.mouth.length, nb = ch.m.brows.length;
  if (eye >= ne) eye = { 4: 1, 5: 0, 6: 1 }[eye] ?? 0;
  if (mouth >= nm) mouth = { 5: 2, 6: 3 }[mouth] ?? 0;
  if (browF >= nb) browF = browF === 3 ? 1 : 0;
  let blush = false;
  if (ch.m.mouthV2) ({ eye, mouth, browF, blush } = decideV2(b, jaw, fun, smi, ex, eye, browF));
  Object.assign(st, { eye, mouth, brow: browF, ears, sparkle, expr: ex, blush: blush || (ex === 'happy') || exc.hi });
  // --- 머리 각도: 양자화 + 히스테리시스 (데드존)
  pose.yawL = level(yaw, pose.yawL, YAW_TH, YAW_H);
  pose.pitL = level(pitch, pose.pitL, PIT_TH, PIT_H);
  pose.rollL = level(roll, pose.rollL, ROLL_TH, ROLL_H);
  // MediaPipe(원본 카메라 기준): yaw>0 = 사용자가 "자기 왼쪽"으로 고개를 돌림, pitch>0 = 아래를 봄(실측), roll>0 = 원본 영상에서 반시계 기울기
  // 스프라이트 k>0 = 캐릭터가 "화면 오른쪽"을 봄. 거울 모드(셀카처럼)면 사용자 왼쪽 → 화면 왼쪽.
  const yawStep = pose.yawL - 2;                 // -2..2 (사용자 기준)
  pose.k = cfg.mirror ? -yawStep : yawStep;
  pose.p = pose.pitL - 1;                         // 실측: MediaPipe pitch(+) = 고개 숙임 → 스프라이트 p=+1(아래)
  const rollStep = pose.rollL - 1;
  pose.r = cfg.mirror ? rollStep : -rollStep;     // 화면 회전 방향(+ = 시계방향)
  // --- 끊김 느낌: 각도는 낮은 애니메이션 fps에서만 갱신 + 최소 유지 시간
  const tickMs = 1000 / cfg.animFps;
  const doTick = !cfg.choppy || t - pose.lastTick >= tickMs;
  if (doTick) {
    pose.lastTick = t; pose.tick++;
    for (const key of ['k', 'p', 'r']) {
      if (pose.shown[key] !== pose[key] && (!cfg.choppy || t - pose.changedAt[key] >= HOLD_MS)) { pose.shown[key] = pose[key]; pose.changedAt[key] = t; }
    }
  }
}

// ---------- 렌더링 ----------
function angleRow() {
  const k = Math.max(-2, Math.min(2, pose.shown.k)), p = Math.max(-1, Math.min(1, pose.shown.p));
  if (ch.nYaw === 1) return 0;
  return (p + 1) * ch.nYaw + (k + 2);
}
// 꼬리: 6가지 흔들기 패턴을 신남 정도에 따라 랜덤 선택 (js/tail.js). 신남은 6단계, 0.5초마다 한 단계씩만 변함.
const TAIL_STEPS = 5, tailSt = createTail();
function tailFrame(t, ex) {
  const n = (ch.m.tail | 0) || ((I_tailW() / ch.S) | 0) || 1;
  const dt = Math.min(200, t - (tailSt.last || t)); tailSt.last = t;
  const want = Math.round(Math.max(0, Math.min(1, ex)) * TAIL_STEPS);
  if (want !== tailSt.step && t - tailSt.stepAt > 500) { tailSt.step += Math.sign(want - tailSt.step); tailSt.stepAt = t; }
  const f = tailStep(tailSt, t, dt, tailSt.step / TAIL_STEPS, n, () => window.__forceTail);
  window.__tail = { n, step: tailSt.step, pattern: tailSt.cur, hist: [...tailSt.hist] };
  return f;
}
function I_tailW() { return ch.img.tail ? ch.img.tail.width : 0; }
// 통짜 프레임 캐릭터(fox4): 표정 × 피치 × 요 그림을 통째로 고름. 꼬리는 별도 레이어(애니메이션).
const FULL_EXPR = { auto: 0, happy: 2, tired: 3, surprised: 4, smug: 5 };
function fullCol() {
  let e = FULL_EXPR[st.expr] ?? 0;
  if (e === 0 && (st.mouth === 1 || st.mouth === 2 || st.mouth === 4 || st.mouth === 5)) e = 1; // 입 벌림 → 말하기 그림
  const blink = st.eye === 2 || eyeLv === 2;
  return e * 2 + (blink ? 1 : 0);
}
function drawFull(t, ex, bounce) {
  const S = ch.S, I = ch.img, row = angleRow();
  octx.clearRect(0, 0, S, S);
  const [rx, ry] = ch.m.rollPivot || [S / 2, S - 1];
  octx.save();
  if (pose.shown.r) { octx.translate(rx, ry); octx.rotate(pose.shown.r * ROLL_DEG * 0.55 * Math.PI / 180); octx.translate(-rx, -ry); }
  if (I.tail) octx.drawImage(I.tail, tailFrame(t, ex) * S, 0, S, S, 0, 0, S, S);
  octx.drawImage(I.frames, fullCol() * S, row * S, S, S, 0, Math.floor(t / 1200) % 2, S, S); // 숨쉬기 1px
  octx.restore();
  const animT = cfg.choppy ? pose.tick : Math.floor(t / 60);
  if (I.sparkle && ex > 0.85) { const o = Math.round(S / 16); octx.drawImage(I.sparkle, ((Math.floor(t * 8 / 1000) + 1) % 3) * S, 0, S, S, -o, o, S, S); }
  if (I.sparkle && st.sparkle && st.expr !== 'happy') octx.drawImage(I.sparkle, (Math.floor(animT / 2) % 3) * S, 0, S, S, 0, 0, S, S);
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.drawImage(off, 0, 0, S, S, 0, bounce * scale, S * scale, S * scale);
}
// fox5: 통짜 그림 + 입(벌림 3단계)/눈 감기/귀 레이어를 표정·각도별로 합성
const MOUTH_LV = [0, 1, 3, 0, 2, 3, 0]; // st.mouth(cat,slight,wide,smile,o,shock,smug) → 벌림 단계
function drawFull2(t) {
  const S = ch.S, I = ch.img, row = angleRow();
  const ex = mic.on ? mic.score : 0;
  const e = FULL_EXPR[st.expr] ?? 0;
  const lv = MOUTH_LV[st.mouth] || 0, blink = st.eye === 2 || eyeLv === 2;
  // 귀 들썩임 (v3와 같은 계단식), 높은 신남에서만 작게 통통
  const wig = ex > 0.25 ? Math.floor(t * (3 + 10 * ex) / 1000) % 2 : 0;
  const wigDy = wig ? -(ex > 0.7 ? 2 : 1) : 0, wigDx = 0;
  const bounce = ex > 0.75 ? -(Math.floor(t * 6 / 1000) % 2) : 0;
  const breath = Math.floor(t / 1200) % 2;
  window.__fx = { ex, wigDy, bounce, e, lv, blink };
  octx.clearRect(0, 0, S, S);
  const [rx, ry] = ch.m.rollPivot || [S / 2, S - 1];
  octx.save();
  if (pose.shown.r) { octx.translate(rx, ry); octx.rotate(pose.shown.r * ROLL_DEG * 0.55 * Math.PI / 180); octx.translate(-rx, -ry); }
  if (I.tail) octx.drawImage(I.tail, tailFrame(t, ex) * S, 0, S, S, 0, 0, S, S);
  const D = (im, col, dx = 0, dy = 0) => octx.drawImage(im, col * S, row * S, S, S, dx, breath + dy, S, S);
  D(I.base, e);
  if (lv > 0) D(I.mouth, e * 3 + lv - 1);
  if (blink) D(I.blink, e);
  if (st.expr !== 'tired') D(I.ears, e, wigDx, wigDy);
  octx.restore();
  const animT = cfg.choppy ? pose.tick : Math.floor(t / 60);
  if (I.sparkle && ex > 0.85) { const o = Math.round(S / 16); octx.drawImage(I.sparkle, ((Math.floor(t * 8 / 1000) + 1) % 3) * S, 0, S, S, -o, o, S, S); }
  if (I.sparkle && st.sparkle) octx.drawImage(I.sparkle, (Math.floor(animT / 2) % 3) * S, 0, S, S, 0, 0, S, S);
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.drawImage(off, 0, 0, S, S, 0, bounce * scale, S * scale, S * scale);
}
// fox52: v5 머리카락·몸 그림(얼굴 비움) + v3식 깔끔한 눈/입/눈썹 레이어
function drawFace(t) {
  const S = ch.S, I = ch.img, row = angleRow();
  const ex = mic.on ? mic.score : 0;
  const wig = ex > 0.25 ? Math.floor(t * (3 + 10 * ex) / 1000) % 2 : 0;
  const wigDy = wig ? -(ex > 0.7 ? 2 : 1) : 0;
  const bounce = ex > 0.75 ? -(Math.floor(t * 6 / 1000) % 2) : 0;
  const breath = Math.floor(t / 1200) % 2, tired = st.expr === 'tired';
  window.__fx = { ex, wigDy, bounce };
  octx.clearRect(0, 0, S, S);
  const [rx, ry] = ch.m.rollPivot || [S / 2, S - 1];
  octx.save();
  if (pose.shown.r) { octx.translate(rx, ry); octx.rotate(pose.shown.r * ROLL_DEG * 0.55 * Math.PI / 180); octx.translate(-rx, -ry); }
  if (I.tail) octx.drawImage(I.tail, tailFrame(t, ex) * S, 0, S, S, 0, 0, S, S);
  const D = (im, col, dy = 0) => octx.drawImage(im, col * S, row * S, S, S, 0, breath + dy, S, S);
  D(I.base, 0);
  D(I.eyes, st.eye); D(I.mouth, st.mouth); D(I.brows, st.brow);
  if (I.blush && st.blush) D(I.blush, 0);
  D(I.ears, tired && I.ears.width > S ? 1 : 0, tired ? 0 : wigDy);
  octx.restore();
  const animT = cfg.choppy ? pose.tick : Math.floor(t / 60);
  if (I.sparkle && ex > 0.85) { const o = Math.round(S / 16); octx.drawImage(I.sparkle, ((Math.floor(t * 8 / 1000) + 1) % 3) * S, 0, S, S, -o, o, S, S); }
  if (I.sparkle && st.sparkle) octx.drawImage(I.sparkle, (Math.floor(animT / 2) % 3) * S, 0, S, S, 0, 0, S, S);
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.drawImage(off, 0, 0, S, S, 0, bounce * scale, S * scale, S * scale);
}
function draw(t) {
  if (ch.m.mode === 'face') return drawFace(t);
  if (ch.m.mode === 'full2') return drawFull2(t);
  if (ch.m.mode === 'full') {
    const ex = mic.on ? mic.score : 0;
    const bounce = ex > 0.75 ? -(Math.floor(t * 6 / 1000) % 2) : 0;
    const wig = ex > 0.25 ? Math.floor(t * (3 + 10 * ex) / 1000) % 2 : 0; // 귀가 그림에 붙어 있어 귀 대신 통통 튀기로 표현
    window.__fx = { ex, wigDy: wig ? -1 : 0, bounce: bounce || (ex > 0.45 && wig ? -1 : 0), col: fullCol() };
    return drawFull(t, ex, window.__fx.bounce);
  }
  const S = ch.S, I = ch.img, row = angleRow();
  const animT = cfg.choppy ? pose.tick : Math.floor(t / 60);
  const breath = Math.floor(t / 1200) % 2;
  const L = (c, name, frame, r = row, dx = 0, dy = 0) => { const im = I[name]; if (!im) return; const rr = im.height > S ? r : 0; c.drawImage(im, frame * S, rr * S, S, S, dx, dy, S, S); };
  octx.clearRect(0, 0, S, S);
  const [px, py] = ch.m.neckPivot;
  const shoulder = Math.abs(pose.shown.k) === 2 ? Math.sign(pose.shown.k) : 0; // 크게 돌릴 때 어깨 1px
  // 신남 효과 (정수 픽셀, 프레임 단위 계단식)
  const ex = mic.on ? mic.score : 0;
  const wigFps = 3 + 10 * ex, wig = ex > 0.25 ? Math.floor(t * wigFps / 1000) % 2 : 0;
  const wigDy = wig ? -(ex > 0.7 ? 2 : 1) : 0, wigDx = (ex > 0.7 && wig) ? 1 : 0;
  const bounce = ex > 0.75 ? -(Math.floor(t * 6 / 1000) % 2) : 0;
  window.__fx = { ex, wigDy, bounce };
  const headGroup = names => {
    hctx.clearRect(0, 0, S, S);
    for (const [n, f, dx = 0, dy = 0] of names) L(hctx, n, f, row, dx, dy);
    octx.save();
    if (pose.shown.r) { octx.translate(px, py); octx.rotate(pose.shown.r * ROLL_DEG * Math.PI / 180); octx.translate(-px, -py); }
    octx.drawImage(hc, Math.round(shoulder * 0.5), breath);
    octx.restore();
  };
  if (I.tail) L(octx, 'tail', tailFrame(t, ex), 0);
  headGroup(I.ears ? (st.ears ? [['hair_back', 0]] : [['ears', 0, wigDx, wigDy], ['hair_back', 0]]) : [['hair_back', 0]]);
  L(octx, 'body', 0, 0, shoulder, breath ? 0 : 0);
  const front = [['head', 0], ['eyes', st.eye], ['mouth', st.mouth], ['hair_front', 0], ['brows', st.brow]];
  if (I.ears && st.ears) front.splice(0, 0, ['ears', 1]);
  headGroup(front);
  if (st.sparkle && I.sparkle) L(octx, 'sparkle', Math.floor(animT / 2) % 3, 0);
  if (ex > 0.85 && I.sparkle) { const o = Math.round(S / 16); L(octx, 'sparkle', (Math.floor(t * 8 / 1000) + 1) % 3, 0, -o, o); L(octx, 'sparkle', (Math.floor(t * 8 / 1000) + 2) % 3, 0, o, Math.round(o * 1.5)); }
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.drawImage(off, 0, 0, S, S, 0, bounce * scale, S * scale, S * scale);
}

// ---------- 자동 깜빡임 ----------
let nextBlink = 2000, blinkUntil = 0;
function autoBlink(t) {
  if (t > nextBlink) { blinkUntil = t + 140; nextBlink = t + 2500 + Math.random() * 3000; }
  return t < blinkUntil ? (t < blinkUntil - 90 || t > blinkUntil - 30 ? 1 : 2) : 0;
}

// ---------- 얼굴 추적 ----------
let landmarker = null, mode = 'idle', lastVideoTime = -1, faceSeen = 0;
const zero = { stretch: 0, smileAsym: 0, puff: 0, squint: 0, jaw: 0, funnel: 0, smile: 0, blink: 0, brow: 0, wide: 0, yaw: 0, pitch: 0, roll: 0 };
let latest = { ...zero };
async function loadModel() {
  status('모델 불러오는 중…');
  const { FaceLandmarker, FilesetResolver } = await import(`${MP_URL}/vision_bundle.mjs`);
  const fileset = await FilesetResolver.forVisionTasks(`${MP_URL}/wasm`);
  const opts = d => ({ baseOptions: { modelAssetPath: MODEL_URL, delegate: d }, runningMode: 'VIDEO', numFaces: 1,
    outputFaceBlendshapes: true, outputFacialTransformationMatrixes: true });
  try { landmarker = await FaceLandmarker.createFromOptions(fileset, opts('GPU')); window.__delegate = 'GPU'; }
  catch (e) { console.warn('GPU 실패, CPU로 전환', e); landmarker = await FaceLandmarker.createFromOptions(fileset, opts('CPU')); window.__delegate = 'CPU'; }
  window.__modelLoaded = true;
}
function readResult(r) {
  if (!r.faceBlendshapes?.length) return null;
  const m = {}; for (const c of r.faceBlendshapes[0].categories) m[c.categoryName] = c.score;
  const out = {
    jaw: m.jawOpen || 0, funnel: Math.max(m.mouthFunnel || 0, m.mouthPucker || 0),
    smile: ((m.mouthSmileLeft || 0) + (m.mouthSmileRight || 0)) / 2,
    blink: Math.max(m.eyeBlinkLeft || 0, m.eyeBlinkRight || 0) * 0.5 + ((m.eyeBlinkLeft || 0) + (m.eyeBlinkRight || 0)) / 4,
    brow: m.browInnerUp || 0, wide: ((m.eyeWideLeft || 0) + (m.eyeWideRight || 0)) / 2, yaw: 0, pitch: 0, roll: 0,
    stretch: ((m.mouthStretchLeft || 0) + (m.mouthStretchRight || 0)) / 2, smileAsym: (m.mouthSmileLeft || 0) - (m.mouthSmileRight || 0),
    puff: m.cheekPuff || 0, squint: ((m.eyeSquintLeft || 0) + (m.eyeSquintRight || 0)) / 2,
  };
  const mat = r.facialTransformationMatrixes?.[0]?.data;
  if (mat) { // column-major 4x4
    const D = 180 / Math.PI;
    out.pitch = Math.atan2(mat[6], mat[10]) * D;
    out.yaw = Math.asin(Math.max(-1, Math.min(1, -mat[2]))) * D;
    out.roll = Math.atan2(mat[1], mat[0]) * D;
  }
  window.__rawPose = { yaw: out.yaw, pitch: out.pitch, roll: out.roll };
  return out;
}
async function startCamera() {
  showErr('');
  if (!navigator.mediaDevices?.getUserMedia) { showErr('이 브라우저는 카메라를 지원하지 않거나 HTTPS가 아닙니다. HTTPS 주소로 접속해 주세요.'); return; }
  try {
    status('카메라 권한 요청 중…');
    const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'user', width: { ideal: 640 }, height: { ideal: 480 } }, audio: false });
    video.srcObject = stream; await video.play();
    if (!landmarker) await loadModel();
    mode = 'camera'; status(`추적 중 (${window.__delegate})`); $('start').textContent = '카메라 실행 중';
  } catch (e) {
    console.warn(e);
    const n = e && e.name;
    if (n === 'NotAllowedError' || n === 'SecurityError') showErr('카메라 권한이 거부되었습니다. 브라우저 설정(주소창의 자물쇠/aA 메뉴)에서 카메라를 허용한 뒤 새로고침해 주세요.');
    else if (n === 'NotFoundError' || n === 'OverconstrainedError') showErr('사용할 수 있는 카메라를 찾지 못했습니다.');
    else if (n === 'NotReadableError') showErr('다른 앱이 카메라를 사용 중입니다. 다른 앱을 종료하고 다시 시도해 주세요.');
    else showErr('시작 실패: ' + (e.message || e) + ' (네트워크 연결을 확인해 주세요)');
    status('오류');
  }
}
$('start').onclick = startCamera;
$('demo').onclick = () => { mode = mode === 'demo' ? 'idle' : 'demo'; status(mode === 'demo' ? '데모 모드' : '대기 중'); if (mode !== 'demo') setExpr('auto'); };
if (params.get('demo') === '1') { mode = 'demo'; status('데모 모드'); }

// ---------- 데모: 각도 + 표정 순환 ----------
// 각도는 가상의 "사용자 머리 각도"를 넣어 실제와 같은 양자화 경로를 거치게 함
const DEMO_POSE = [[0, 0, 0], [-18, 0, 0], [-35, 0, 0], [-35, 15, 0], [-18, -15, 0], [0, -15, 0], [0, 15, 0], [18, 15, 0], [35, 0, 0], [35, -15, 0], [18, 0, 0], [0, 0, 14], [0, 0, -14], [0, 0, 0]];
const DEMO_EXPR = [
  { name: '기본', e: 'auto' }, { name: '말하기', e: 'auto', talk: 1 }, { name: '웃음+반짝', e: 'happy', talk: 1 }, { name: '피곤(귀 처짐)', e: 'tired' },
  { name: '놀람', e: 'surprised', jaw: 0.6 }, { name: '의기양양', e: 'smug' }, { name: '눈 감기', e: 'auto', blink: 0.9 },
];
function demoValues(t) {
  const P = DEMO_POSE[Math.floor(t / 1100) % DEMO_POSE.length], d = DEMO_EXPR[Math.floor(t / 2600) % DEMO_EXPR.length];
  window.__demoExpr = d.name; window.__demoPose = P;
  if (exprOverride !== d.e) setExpr(d.e);
  const yaw = cfg.mirror ? -P[0] : P[0];   // 데모는 "화면 기준" 방향으로 보이도록 사용자 각도로 역변환
  const roll = cfg.mirror ? P[2] : -P[2];
  return { ...zero, blink: d.blink || 0, jaw: d.talk ? (Math.sin(t / 90) > 0 ? 0.3 : 0.05) : (d.jaw || 0), yaw, pitch: -P[1], roll };   // 데모 P[1]>0 = 위
}

// ---------- 루프 ----------
let frames = 0, fpsT = performance.now();
window.__frames = 0;
function loop(t) {
  let b = latest, auto = 0;
  if (mode === 'camera' && landmarker && video.readyState >= 2 && video.currentTime !== lastVideoTime) {
    lastVideoTime = video.currentTime;
    const r = readResult(landmarker.detectForVideo(video, t));
    if (r) { latest = r; faceSeen = t; }
  }
  if (mode === 'sim') { b = latest; }
  else if (mode === 'demo') { b = demoValues(t); if (!(b.blink > 0)) auto = autoBlink(t); }
  else if (mode !== 'camera' || t - faceSeen > 1000) { b = { ...zero }; auto = autoBlink(t); if (mode === 'camera') status('얼굴을 찾는 중…'); }
  else if (mode === 'camera') status(`추적 중 (${window.__delegate})`);
  micTick(t, cfg.micSens);
  decide(b, auto, t);
  draw(t);
  frames++; window.__frames++;
  if (mic.on) { $('meterBar').style.width = Math.round(mic.score * 100) + '%'; $('meterBar').classList.toggle('hi', exc.hi); }
  $('pose').textContent = `각도 요${pose.shown.k} 피치${pose.shown.p} 롤${pose.shown.r}`;
  if (t - fpsT > 1000) { $('fps').textContent = 'FPS: ' + Math.round(frames * 1000 / (t - fpsT)); frames = 0; fpsT = t; }
  requestAnimationFrame(loop);
}
await loadChar(params.get('char') && CHARS[params.get('char')] ? params.get('char') : 'fox62');
$('char').value = ch.key;
requestAnimationFrame(loop);
// 테스트용: 가짜 MediaPipe 결과를 실제 readResult 경로로 주입
function simResult(r) { mode = 'sim'; latest = readResult(r); }
window.__app = { mic, exc, st, pose, cfg, startCamera, loadModel, loadChar, setExpr, simResult };
