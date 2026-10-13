@echo off
rem ============================================================
rem  Coral Guardian - Web version launcher (consensus tips OFF)
rem  ASCII only on purpose: .bat with UTF-8 Chinese breaks cmd.
rem ============================================================
setlocal
set PORT=%1
if "%PORT%"=="" set PORT=8000
rem turn off the two-model consensus tip (everything else unchanged)
set DISABLE_BLEACH_CONSENSUS=1
cd /d "%~dp0scripts"

echo ============================================================
echo   Coral Guardian  .  Web version   (consensus tip: OFF)
echo ============================================================
echo   Port      : %PORT%
echo   Computer  : http://127.0.0.1:%PORT%/
echo   Phone     : http://YOUR-LAN-IP:%PORT%/     (same Wi-Fi)
echo.
echo   Keep this window OPEN. Press Ctrl+C to stop the service.
echo ============================================================
echo.

start "" /min powershell -NoProfile -Command "Start-Sleep -Seconds 25; Start-Process 'http://127.0.0.1:%PORT%/'"

python serve_fusion.py --host 0.0.0.0 --port %PORT%

echo.
echo Service stopped. Press any key to close this window.
pause >nul
