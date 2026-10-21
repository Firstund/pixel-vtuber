// 귀 움직임 패턴 엔진 (꼬리와 같은 방식). 프레임: 0 기본, 1/2 바깥 기울기(작게/크게), 3/4 안쪽, 5 살짝 쫑긋, 6 쫑긋(위로), 7 휙(빠른 경련), 8 뒤로 접기, 9 미세 떨림
const R = (a, b) => a + Math.random() * (b - a);
const rep = (n, f) => { const s = []; for (let i = 0; i < n; i++) s.push(...f(i)); return s; };
// 각 패턴: { L: [[프레임, ms], ...], R: [...] } — 좌우 따로, 타이밍 살짝 어긋나게
export const EAR_PATTERNS = {
  hold:    { name: '가만히', calm: 6, exc: 0.6, make: () => { const h = R(900, 2200); return { L: [[0, h]], R: [[0, h]] }; } },
  twitch:  { name: '한쪽 귀 움찔', calm: 2, exc: 2, make: () => { const s = [[7, 90], [0, 140]]; const o = [[0, 230]]; return Math.random() < 0.5 ? { L: s, R: o } : { L: o, R: s }; } },
  flick2:  { name: '한쪽 두 번 휙휙', calm: 0.4, exc: 2.5, make: () => { const s = [[7, 80], [0, 110], [7, 80], [0, 200]]; const o = [[0, 470]]; return Math.random() < 0.5 ? { L: s, R: o } : { L: o, R: s }; } },
  perk:    { name: '양쪽 쫑긋', calm: 0.8, exc: 2.5, make: () => { const h = R(450, 900), d = R(30, 90); return { L: [[5, 120], [6, h], [5, 140], [0, 200]], R: [[0, d], [5, 120], [6, h - d], [5, 140], [0, 200]] }; } },
  alt:     { name: '번갈아 까딱', calm: 0.3, exc: 2.5, make: () => { const k = 3 + (Math.random() * 3 | 0), d = R(150, 220); return { L: [...rep(k, () => [[1, d], [3, d]]), [0, 200]], R: [...rep(k, () => [[3, d], [1, d]]), [0, 200]] }; } },
  tremble: { name: '파르르', calm: 0.3, exc: 1.5, make: () => { const k = 4 + (Math.random() * 3 | 0); return { L: [...rep(k, () => [[9, 90], [0, 90]]), [0, 150]], R: [[0, 60], ...rep(k, () => [[9, 90], [0, 90]]), [0, 90]] }; } },
  outward: { name: '바깥으로 기울였다 돌아오기', calm: 1.5, exc: 1, make: () => { const h = R(500, 1100); return { L: [[1, 180], [2, h], [1, 180], [0, 200]], R: [[0, 70], [1, 180], [2, h], [1, 180], [0, 130]] }; } },
  fold:    { name: '살짝 뒤로 접기', calm: 1.2, exc: 0.4, make: () => { const h = R(500, 1000); return { L: [[8, h], [0, 250]], R: [[0, 50], [8, h], [0, 200]] }; } },
};
const KEYS = Object.keys(EAR_PATTERNS);
export function createEars() { return { hist: [], cur: null, L: [], R: [], li: 0, ri: 0, lt: 0, rt: 0, fL: 0, fR: 0, pause: 0 }; }
function pick(st, x, force) {
  let k = force;
  if (!k) {
    const banned = st.hist.length >= 2 && st.hist[0] === st.hist[1] ? st.hist[0] : null; // 같은 패턴 3연속 금지
    const w = KEYS.map(k => k === banned ? 0 : EAR_PATTERNS[k].calm * (1 - x) + EAR_PATTERNS[k].exc * x);
    let r = Math.random() * w.reduce((a, b) => a + b, 0); k = KEYS[0];
    for (let i = 0; i < KEYS.length; i++) { r -= w[i]; if (r <= 0) { k = KEYS[i]; break; } }
  }
  st.hist.unshift(k); st.hist.length = Math.min(st.hist.length, 2);
  const p = EAR_PATTERNS[k].make(); st.cur = k; st.L = p.L; st.R = p.R; st.li = st.ri = 0; st.lt = st.rt = 0;
}
// x: 신남 0..1 (단계 양자화된 값). 반환 [왼귀 프레임, 오른귀 프레임]
export function earStep(st, dt, x, force) {
  const sc = 1 - 0.4 * x, MIN = 70; // 신날수록 빠르게, 너무 빠른 깜빡임 방지
  const adv = (seq, i, tk) => {
    let t = st[tk] + dt;
    while (i < seq.length && t >= Math.max(MIN, seq[i][1] * (seq[i][0] === 0 && seq[i][1] > 600 ? 1 : sc))) { t -= Math.max(MIN, seq[i][1] * sc); i++; }
    st[tk] = t; return i;
  };
  if (st.pause > 0) { st.pause -= dt; return [0, 0]; }
  if (!st.cur || (st.li >= st.L.length && st.ri >= st.R.length)) { pick(st, x, force && force()); st.pause = (1 - 0.8 * x) * R(100, 600); return [0, 0]; }
  st.li = adv(st.L, st.li, 'lt'); st.ri = adv(st.R, st.ri, 'rt');
  st.fL = st.li < st.L.length ? st.L[st.li][0] : 0; st.fR = st.ri < st.R.length ? st.R[st.ri][0] : 0;
  return [st.fL, st.fR];
}
