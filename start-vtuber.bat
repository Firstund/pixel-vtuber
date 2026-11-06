@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 픽셀 VTuber / 음악 플레이어 로컬 중계
echo 카메라 영상과 마이크 소리는 전송하지 않습니다.
where py >nul 2>&1
if %errorlevel%==0 (
  py -3 tools\vtuber_relay.py
  if errorlevel 1 pause
  goto :eof
)
python tools\vtuber_relay.py
if errorlevel 1 (
  echo Python 3 이 필요합니다. https://www.python.org/ 에서 설치한 뒤 다시 실행하세요.
  pause
)
