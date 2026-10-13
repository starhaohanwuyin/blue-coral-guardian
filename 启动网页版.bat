@echo off
rem ============================================================
rem  Coral Guardian - Web version launcher (ASCII only on purpose:
rem  .bat files with UTF-8 Chinese get mis-parsed by cmd / GBK).
rem  Usage: double click this file, or run: <this-file> [port]
rem  (File name is Chinese; content is ASCII on purpose.)
rem ============================================================
setlocal
set PORT=%1
if "%PORT%"=="" set PORT=8000
cd /d "%~dp0scripts"

echo ============================================================
echo   Coral Guardian  .  Web version
echo ============================================================
echo   Port      : %PORT%
echo   Computer  : http://127.0.0.1:%PORT%/
echo   Phone     : http://YOUR-LAN-IP:%PORT%/     (same Wi-Fi)
echo.
echo   First start loads 4 models (40-90s); browser opens itself.
echo   Keep this window OPEN. Press Ctrl+C to stop the service.
echo ============================================================
echo.

rem open the browser after 25 seconds (service needs time to load models)
start "" /min powershell -NoProfile -Command "Start-Sleep -Seconds 25; Start-Process 'http://127.0.0.1:%PORT%/'"

python serve_fusion.py --host 0.0.0.0 --port %PORT%

echo.
echo Service stopped. Press any key to close this window.
pause >nul
