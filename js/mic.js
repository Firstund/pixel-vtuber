// 마이크 기반 신남(excitement) 감지: 음량(최근 ~10초 기준 자동 보정) + 음높이(본인 중앙값 대비) + 에너지 변동
export const mic = { on: false, score: 0, raw: 0, db: -100, f0: 0, med: 192, floor: -60, err: '' };
let ac, an, buf, hist = [], vhist = [], f0s = [], lastT = 0, lastF0T = 0; // f0 중앙값: 0.1초마다 1개, 최근 ~40초
const clamp = v => Math.max(0, Math.min(1, v));
const pct = (a, q) => { if (!a.length) return 0; const s = [...a].sort((x, y) => x - y); return s[Math.min(s.length - 1, Math.floor(q * s.length))]; };

export async function startMic() {
  if (mic.on) return true;
  try {
    if (!navigator.mediaDevices?.getUserMedia) throw new Error('이 브라우저는 마이크를 지원하지 않아요');
    const s = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: false, noiseSuppression: false, autoGainControl: false } });
    ac = new (window.AudioContext || window.webkitAudioContext)();
    if (ac.state === 'suspended') await ac.resume();
    an = ac.createAnalyser(); an.fftSize = 2048; buf = new Float32Array(an.fftSize);
    ac.createMediaStreamSource(s).connect(an);
    mic.on = true; mic.err = ''; return true;
  } catch (e) {
    mic.err = (e && e.name === 'NotAllowedError') ? '마이크 권한이 거부됐어요. 브라우저 설정에서 허용해 주세요.' : ('마이크를 켤 수 없어요: ' + (e.message || e));
    return false;
  }
}

function autocorrF0(x, sr) {
  const n = x.length, minL = Math.floor(sr / 500), maxL = Math.floor(sr / 70);
  let best = 0, bestL = 0, e0 = 0;
  for (let i = 0; i < n; i++) e0 += x[i] * x[i];
  if (e0 < 1e-6) return 0;
  for (let L = minL; L <= maxL; L++) {
    let c = 0; for (let i = 0; i + L < n; i++) c += x[i] * x[i + L];
    c /= e0; if (c > best) { best = c; bestL = L; }
  }
  return best > 0.45 ? sr / bestL : 0;
}

// 매 프레임 호출. sens: 0.5~2
export function micTick(t, sens = 1) {
  if (!mic.on) { mic.score = 0; return 0; }
  const dt = Math.min(1000, t - (lastT || t)); lastT = t;
  an.getFloatTimeDomainData(buf);
  let ss = 0; for (let i = 0; i < buf.length; i++) ss += buf[i] * buf[i];
  const db = 10 * Math.log10(ss / buf.length + 1e-10); mic.db = db;
  hist.push([t, db]); while (hist.length && t - hist[0][0] > 10000) hist.shift();
  const dbs = hist.map(h => h[1]);
  const floor = pct(dbs, 0.15); mic.floor = floor;
  const voiced = db > floor + 8;
  let f0 = 0;
  if (voiced) {
    f0 = autocorrF0(buf, ac.sampleRate);
    if (f0 && t - lastF0T > 100) { lastF0T = t; f0s.push(f0); if (f0s.length > 400) f0s.shift(); if (f0s.length > 20) mic.med = pct(f0s, 0.5); }
  }
  mic.f0 = f0;
  if (voiced) { vhist.push([t, db]); } while (vhist.length && t - vhist[0][0] > 10000) vhist.shift();
  const vdb = vhist.map(h => h[1]), vmed = vdb.length > 15 ? pct(vdb, 0.5) : db;
  mic.vmed = vmed;
  // 평소 말하는 음량(최근 10초 유성음 중앙값) 대비 얼마나 큰지
  const loud = clamp((db - vmed + 2) / 10);
  const pitch = f0 ? clamp(12 * Math.log2(f0 / mic.med) / 5) : 0;
  const rec = vhist.filter(h => t - h[0] < 1500).map(h => h[1]);
  const mean = rec.reduce((a, b) => a + b, 0) / (rec.length || 1);
  const sd = Math.sqrt(rec.reduce((a, b) => a + (b - mean) ** 2, 0) / (rec.length || 1));
  const vari = rec.length > 5 ? clamp((sd - 2) / 8) : 0;
  const raw = voiced ? clamp(sens * (0.5 * loud + 0.3 * pitch + 0.2 * vari)) : 0;
  mic.raw = raw;
  const k = raw > mic.score ? 1 - Math.exp(-dt / 120) : 1 - Math.exp(-dt / 900); // 빠른 상승, 느린 하강
  mic.score += (raw - mic.score) * k;
  return mic.score;
}
