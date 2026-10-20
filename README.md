# 픽셀 VTuber — 퇴근여우
정적 파일: index.html, style.css, js/app.js, assets/<캐릭터>/ (manifest.json + PNG 시트)
- `assets/fox2/` 퇴근여우 v2 (96px). 머리 레이어는 각도 시트: 행 = (pitch+1)*5 + (yaw+2), yaw −2…+2(+ = 화면 오른쪽을 봄), pitch −1 위 / 0 / +1 아래
  - eyes: 기본·반눈·감음·웃음·피곤·놀람·의기양양 / mouth: :3·살짝·크게·미소·O·경악·의기양양 / brows: 기본·올림·걱정·한쪽올림 / ears: 서있음·처짐 / tail 4 / sparkle 3
- `assets/test/` 구버전 64px 테스트 캐릭터
- 생성 스크립트: tools/ (gen_v2.py, gen_angles.py, preview_angles.py, gen_sprites_test.py)

머리 회전: 각도를 단계로 양자화(데드존 히스테리시스) → "끊김 느낌" 켜면 애니메이션 fps(6–30)로만 갱신 + 단계당 최소 100ms 유지. 입/눈 깜빡임은 매 프레임 반응.
롤(기울기)은 ±9° 3단계, 원본 해상도에서 최근접 보간으로 회전 후 정수 배율 확대.

로컬 실행: `python3 -m http.server 8765` → http://localhost:8765 (카메라는 localhost 또는 HTTPS에서만 동작)
URL 옵션: ?demo=1 (카메라 없이 각도·표정 순환), ?char=test, ?mirror=0, ?choppy=0, ?clean=1, ?bg=00ff00
단축키: 1–5 표정, h 클린 뷰, Esc/더블탭 해제
