// 꼬리 흔들기 패턴 엔진. 위상 ph(연속값, 1 = 한 바퀴; 정수 = 가운데). 프레임 = floor(frac(ph)*N).
// 각 패턴은 위상 0(가운데)에서 시작해 정수 위상에서 끝남. 세그먼트: [목표 위상(상대), 길이 ms, 끝에서 멈춤 ms]
const R = (a, b) => a + Math.random() * (b - a);
export const PATTERNS = {
  sway:    { name: '느긋한 큰 흔들기', calm: 4, exc: 1, make: () => [[0.25, 900], [0.75, 1800, R(0, 300)], [1, 900]] },
  flutter: { name: '가운데 살랑살랑', calm: 3, exc: 1, make: () => { const s = []; const k = 4 + (Math.random() * 3 | 0); for (let i = 0; i < k; i++) s.push([i % 2 ? -0.05 : 0.06, R(320, 420)]); s.push([0, 300]); return s; } },
  flick2:  { name: '휙휙 두 번', calm: 0.5, exc: 3, make: () => [[1, 700], [1, 0, 150], [2, 700]] },
  curl:    { name: '한쪽으로 말고 버티다 풀기', calm: 2, exc: 1, make: () => [[0.25, 700, R(900, 1600)], [0.75, 600], [1, 500]] },
  swish:   { name: '크게 휙 + 멈춤', calm: 2, exc: 2, make: () => [[0.75, 1000, R(500, 900)], [1, 600]] },
  wiggle:  { name: '끝만 빠르게 파닥', calm: 0.3, exc: 3, make: () => { const s = [[0.5, 600]]; const k = 6 + (Math.random() * 3 | 0); for (let i = 0; i < k; i++) s.push([i % 2 ? 0.5 : 0.56, 170]); s.push([1, 600]); return s; } },
};
const KEYS = Object.keys(PATTERNS);
const smooth = u => u * u * (3 - 2 * u); // 세그먼트 양끝 느리고 가운데 빠름
export function createTail() {
  return { ph: 0, base: 0, segs: [], si: 0, segT: 0, from: 0, holdUntil: 0, idleUntil: 0, hist: [], cur: null, step: 0, stepAt: 0, last: 0 };
}
export function pickPattern(st, x, force) {
  let k = force;
  if (!k) {
    const banned = st.hist.length >= 2 && st.hist[0] === st.hist[1] ? st.hist[0] : null; // 같은 패턴 3연속 금지
    const w = KEYS.map(k => k === banned ? 0 : PATTERNS[k].calm * (1 - x) + PATTERNS[k].exc * x);
    let r = Math.random() * w.reduce((a, b) => a + b, 0); k = KEYS[0];
    for (let i = 0; i < KEYS.length; i++) { r -= w[i]; if (r <= 0) { k = KEYS[i]; break; } }
  }
  st.hist.unshift(k); st.hist.length = Math.min(st.hist.length, 2);
  st.cur = k; st.base = Math.round(st.ph); st.segs = PATTERNS[k].make(); st.si = 0; st.segT = 0; st.from = st.ph - st.base;
  return k;
}
// x: 0..1 (신남, 단계 양자화 후). 반환: 프레임 번호
export function tailStep(st, t, dt, x, n, force) {
  if (t < st.holdUntil || t < st.idleUntil) return Math.floor(((st.ph % 1) + 1) % 1 * n) % n;
  if (st.si >= st.segs.length) {
    if (!st.cur || st.idleDone) { pickPattern(st, x, force && force()); st.idleDone = false; }
    else { st.idleDone = true; st.idleUntil = t + (1 - 0.75 * x) * R(300, 1500); return Math.floor(((st.ph % 1) + 1) % 1 * n) % n; }
  }
  const sc = 1 - 0.45 * x; // 신날수록 빠르게 (최소 세그먼트 120ms 제한)
  const [to, d0, hold = 0] = st.segs[st.si];
  const d = Math.max(120, d0 * sc);
  st.segT += dt;
  const u = Math.min(1, st.segT / d);
  st.ph = st.base + st.from + (to - st.from) * smooth(u);
  if (u >= 1) { st.from = to; st.si++; st.segT = 0; if (hold) st.holdUntil = t + hold * (1 - 0.5 * x); }
  return Math.floor(((st.ph % 1) + 1) % 1 * n) % n;
}
