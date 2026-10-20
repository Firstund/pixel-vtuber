// 픽셀 VTuber — 프레임 교체 + 정수 픽셀 이동 리깅 (변형/회전 없음)
const MP_VER = '0.10.14';
const MP_URL = `https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@${MP_VER}`;
const MODEL_URL = 'https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task';
const S = 64;
const $ = id => document.getElementById(id);
const params = new URLSearchParams(location.search);
const canvas = $('c'), ctx = canvas.getContext('2d');
const video = $('video');
const EYE = { open: 0, half: 1, closed: 2, happy: 3 };
const MOUTH = { closed: 0, slight: 1, wide: 2, smile: 3, o: 4 };

// ---------- 에셋 ----------
const names = ['body', 'head', 'hair_back', 'hair_front', 'eyes', 'mouth', 'brows'];
const img = {};
await Promise.all(names.map(n => new Promise((res, rej) => {
  const i = new Image(); i.onload = res; i.onerror = () => rej(new Error('asset ' + n)); i.src = `assets/${n}.png`; img[n] = i;
})));

// ---------- 설정 UI ----------
const cfg = {};
for (const id of ['tMouth', 'tBlink', 'tSmile', 'smooth']) {
  const el = $(id), out = el.nextElementSibling;
  const upd = () => { cfg[id] = parseFloat(el.value); out.textContent = el.value; };
  el.addEventListener('input', upd); upd();
}
const setBg = c => { document.body.style.background = c; $('bg').value = c; };
$('bg').addEventListener('input', e => setBg(e.target.value));
$('green').onclick = () => setBg('#00ff00');
if (params.get('bg')) setBg('#' + params.get('bg').replace('#', ''));
$('preview').onchange = e => document.body.classList.toggle('preview', e.target.checked);
const setClean = on => document.body.classList.toggle('clean', on);
$('clean').onclick = () => setClean(true);
if (params.get('clean') === '1') setClean(true);
document.addEventListener('keydown', e => { if (e.key === 'Escape' || e.key === 'h') setClean(!document.body.classList.contains('clean') && e.key === 'h'); });
let lastTap = 0;
$('stage').addEventListener('pointerup', () => { const t = performance.now(); if (t - lastTap < 350) setClean(false); lastTap = t; });
document.addEventListener('dblclick', () => setClean(false));
const status = s => { $('status').textContent = s; };
const showErr = s => { const e = $('err'); e.hidden = !s; e.textContent = s || ''; };

// ---------- 캔버스 크기 (정수 배율만) ----------
let scale = 4;
function resize() {
  const st = $('stage').getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  scale = Math.max(1, Math.floor(Math.min(st.width, st.height) * dpr / S));
  canvas.width = canvas.height = S * scale;
  canvas.style.width = canvas.style.height = (S * scale / dpr) + 'px';
  ctx.imageSmoothingEnabled = false;
}
new ResizeObserver(resize).observe($('stage')); resize();

// ---------- 상태 / 스무딩 / 히스테리시스 ----------
const sm = { jaw: 0, funnel: 0, smile: 0, blink: 0, brow: 0, yaw: 0, pitch: 0, roll: 0 };
const st = { eye: EYE.open, mouth: MOUTH.closed, brow: 0, hx: 0, hy: 0, fx: 0, rollPx: 0 };
const H = 0.04; // 히스테리시스 폭
function smooth(key, v, k = cfg.smooth) { sm[key] = sm[key] * k + v * (1 - k); return sm[key]; }
// 히스테리시스 레벨: thresholds 오름차순, 현재 레벨 기준으로 위/아래 여유를 둠
function level(v, cur, ths, h = H) {
  let l = cur;
  while (l < ths.length && v > ths[l] + h) l++;
  while (l > 0 && v < ths[l - 1] - h) l--;
  return l;
}
// 각도 → 정수 픽셀 (히스테리시스)
function pxLevel(deg, cur, step, max) {
  const target = deg / step;
  if (Math.abs(target - cur) > 0.75) cur = Math.round(target);
  return Math.max(-max, Math.min(max, cur));
}
let mouthLv = 0, eyeLv = 0;
function decide(b, auto) {
  const jaw = smooth('jaw', b.jaw), fun = smooth('funnel', b.funnel), smi = smooth('smile', b.smile);
  const blink = smooth('blink', b.blink, Math.min(cfg.smooth, 0.3)); // 깜빡임은 빠르게
  const brow = smooth('brow', b.brow);
  const yaw = smooth('yaw', b.yaw), pitch = smooth('pitch', b.pitch), roll = smooth('roll', b.roll);
  // 입
  mouthLv = level(jaw, mouthLv, [cfg.tMouth, cfg.tMouth * 2.2]);
  if (mouthLv === 2) st.mouth = MOUTH.wide;
  else if (fun > 0.35 && mouthLv <= 1) st.mouth = MOUTH.o;
  else if (mouthLv === 1) st.mouth = MOUTH.slight;
  else st.mouth = smi > cfg.tSmile + (st.mouth === MOUTH.smile ? -H : H) ? MOUTH.smile : MOUTH.closed;
  // 눈
  eyeLv = level(blink, eyeLv, [cfg.tBlink * 0.6, cfg.tBlink]);
  if (auto) eyeLv = auto;
  if (eyeLv === 0 && smi > cfg.tSmile + 0.25) st.eye = EYE.happy;
  else st.eye = [EYE.open, EYE.half, EYE.closed][eyeLv];
  // 눈썹
  st.brow = brow > (st.brow ? 0.3 : 0.4) ? 1 : 0;
  // 머리: 정수 픽셀 오프셋 (거울 모드: 사용자 기준 좌우)
  st.hx = pxLevel(-yaw, st.hx, 10, 2);
  st.hy = pxLevel(pitch, st.hy, 12, 1);
  st.fx = Math.abs(yaw) > 22 ? -Math.sign(yaw) : 0; // 큰 회전: 이목구비 추가 1px
  st.rollPx = pxLevel(-roll, st.rollPx, 12, 1);
}

// ---------- 렌더링 ----------
function draw(t) {
  const breath = Math.floor(t / 1200) % 2; // 1px 호흡
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  const L = (name, frame, dx, dy) => ctx.drawImage(img[name], frame * S, 0, S, S, dx * scale, dy * scale, S * scale, S * scale);
  const hx = st.hx + st.rollPx, hy = st.hy + breath;
  L('hair_back', 0, hx - st.fx, hy);
  L('body', 0, 0, breath);
  L('head', 0, hx, hy);
  L('eyes', st.eye, hx + st.fx, hy);
  L('mouth', st.mouth, hx + st.fx, hy);
  L('hair_front', 0, hx + st.rollPx, hy);
  L('brows', st.brow, hx + st.fx, hy);
}

// ---------- 자동 깜빡임 (얼굴 없을 때/데모) ----------
let nextBlink = 2000, blinkUntil = 0;
function autoBlink(t) {
  if (t > nextBlink) { blinkUntil = t + 140; nextBlink = t + 2500 + Math.random() * 3000; }
  return t < blinkUntil ? (t < blinkUntil - 90 || t > blinkUntil - 30 ? 1 : 2) : 0;
}

// ---------- 얼굴 추적 ----------
let landmarker = null, mode = 'idle', lastVideoTime = -1, faceSeen = 0;
const zero = { jaw: 0, funnel: 0, smile: 0, blink: 0, brow: 0, yaw: 0, pitch: 0, roll: 0 };
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
    jaw: m.jawOpen || 0,
    funnel: Math.max(m.mouthFunnel || 0, m.mouthPucker || 0),
    smile: ((m.mouthSmileLeft || 0) + (m.mouthSmileRight || 0)) / 2,
    blink: Math.max(m.eyeBlinkLeft || 0, m.eyeBlinkRight || 0) * 0.5 + ((m.eyeBlinkLeft || 0) + (m.eyeBlinkRight || 0)) / 4,
    brow: m.browInnerUp || 0, yaw: 0, pitch: 0, roll: 0,
  };
  const mat = r.facialTransformationMatrixes?.[0]?.data;
  if (mat) { // column-major 4x4
    const D = 180 / Math.PI;
    out.pitch = Math.atan2(mat[6], mat[10]) * D;
    out.yaw = Math.asin(Math.max(-1, Math.min(1, -mat[2]))) * D;
    out.roll = Math.atan2(mat[1], mat[0]) * D;
  }
  return out;
}
async function startCamera() {
  showErr('');
  if (!navigator.mediaDevices?.getUserMedia) {
    showErr('이 브라우저는 카메라를 지원하지 않거나 HTTPS가 아닙니다. HTTPS 주소로 접속해 주세요.'); return;
  }
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
$('demo').onclick = () => { mode = mode === 'demo' ? 'idle' : 'demo'; status(mode === 'demo' ? '데모 모드' : '대기 중'); };
if (params.get('demo') === '1') { mode = 'demo'; status('데모 모드'); }

// 데모: 표정 순환 (2초마다)
const DEMO = [
  { name: '기본' }, { name: '말하기', talk: 1 }, { name: '입 크게', jaw: 0.7, brow: 0.7 }, { name: '웃음', smile: 0.9 },
  { name: 'O 입', funnel: 0.7, jaw: 0.05 }, { name: '미소', smile: 0.55 }, { name: '눈 감기', blink: 0.9 }, { name: '반눈', blink: 0.38 },
];
function demoValues(t) {
  const i = Math.floor(t / 2000) % DEMO.length, d = DEMO[i];
  window.__demoExpr = d.name;
  return { ...zero, ...d, jaw: d.talk ? (Math.sin(t / 90) > 0 ? 0.3 : 0.05) : (d.jaw || 0),
    yaw: Math.sin(t / 1500) * 28, pitch: Math.sin(t / 2300) * 10, roll: Math.sin(t / 1900) * 14 };
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
  if (mode === 'demo') { b = demoValues(t); if (!(b.blink > 0)) auto = autoBlink(t); }
  else if (mode !== 'camera' || t - faceSeen > 1000) { b = { ...zero }; auto = autoBlink(t); if (mode === 'camera') status('얼굴을 찾는 중…'); }
  else if (mode === 'camera') status(`추적 중 (${window.__delegate})`);
  decide(b, auto);
  draw(t);
  frames++; window.__frames++;
  if (t - fpsT > 1000) { $('fps').textContent = 'FPS: ' + Math.round(frames * 1000 / (t - fpsT)); frames = 0; fpsT = t; }
  requestAnimationFrame(loop);
}
requestAnimationFrame(loop);
window.__app = { st, startCamera, loadModel };
