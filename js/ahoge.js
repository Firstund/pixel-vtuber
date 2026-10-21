// v7 아호게 애니메이션 (귀 대신). 프레임: 0 기본, 1 왼쪽 흔들, 2 오른쪽 흔들, 3 통통(위로), 4 눌림, 5 처짐, 6 많이 처짐
const R = (a, b) => a + Math.random() * (b - a);
function seqFor(mood, x) {
  if (mood === 'tired') return [[5, R(500, 900)], [6, R(900, 1600)]];
  if (mood === 'surprised') return [[3, R(500, 800)], [0, 120]];
  if (mood === 'smug') return [[2, R(600, 1000)], [0, 200], [2, 300]];
  if (mood === 'happy' || x > 0.5) { const k = 3 + (Math.random() * 3 | 0), d = 150 - 60 * Math.min(1, x); const s = []; for (let i = 0; i < k; i++) s.push([3, d], [4, d]); s.push([0, 150]); return s; }
  return [[0, R(700, 1600)], [1, R(220, 320)], [0, R(150, 250)], [2, R(220, 320)]];
}
export function createAhoge() { return { seq: [], i: 0, t: 0, mood: '', f: 0 }; }
export function ahogeStep(st, dt, x, mood) {
  if (mood !== st.mood) { st.mood = mood; st.seq = []; }
  if (st.i >= st.seq.length) { st.seq = seqFor(mood, x); st.i = 0; st.t = 0; }
  st.t += dt;
  while (st.i < st.seq.length && st.t >= st.seq[st.i][1]) { st.t -= st.seq[st.i][1]; st.i++; }
  st.f = st.i < st.seq.length ? st.seq[st.i][0] : 0;
  return st.f;
}
