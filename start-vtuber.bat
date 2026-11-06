@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>&1
if not errorlevel 1 goto run_py
where python >nul 2>&1
if not errorlevel 1 goto run_python
goto missing

:run_py
py -3 "%~dp0tools\vtuber_relay.py"
if not errorlevel 1 exit /b 0
goto failed

:run_python
python "%~dp0tools\vtuber_relay.py"
if not errorlevel 1 exit /b 0
goto failed

:missing
echo Python 3 was not found.
echo Install Python 3 from https://www.python.org/downloads/
echo Turn on Add python.exe to PATH in the installer.
echo Then double-click start-vtuber.bat again.
echo.
echo Or open cmd in this folder and run:
echo   py -3 tools\vtuber_relay.py
echo   python tools\vtuber_relay.py
pause
exit /b 1

:failed
echo.
echo The relay did not stay running.
echo Open cmd in this folder and run:
echo   py -3 tools\vtuber_relay.py
echo   python tools\vtuber_relay.py
pause
exit /b 1
