@echo off
rem ============================================================
rem  Blue Coral Guardian - One-click demo launcher
rem  (ASCII only on purpose: UTF-8 Chinese in .bat breaks cmd)
rem  1) check model weights  2) start AI service  3) open browser
rem ============================================================
setlocal
set PORT=%1
if "%PORT%"=="" set PORT=8000
cd /d "%~dp0ai-service"

echo ============================================================
echo   Blue Coral Guardian  .  Demo Launcher
echo ============================================================
echo.

rem ---- 1) model weights present? ----
if not exist "weights\bleaching_all\best.pt" goto need_weights
if not exist "weights\species_ip\best.pt" goto need_weights
if not exist "weights\segformer_coralscapes\model.safetensors" goto need_weights
goto weights_ok

:need_weights
echo [1/3] Model weights NOT found.
echo       Downloading about 470 MB from GitHub Release ...
echo       (needs internet; if it fails, download manually from
echo        https://github.com/starhaohanwuyin/blue-coral-guardian/releases/tag/v1.0-models )
echo.
python tools\download_weights.py
if errorlevel 1 (
  echo.
  echo   Download failed. Please get the weights manually, then run this file again.
  pause
  exit /b 1
)

:weights_ok
echo [1/3] Model weights OK.
echo.
echo [2/3] Starting AI service on port %PORT% ...
echo       First start loads 4 models: wait 40-90 seconds.
echo       KEEP THIS WINDOW OPEN. Press Ctrl+C to stop.
echo.

rem ---- 3) open browser after the models are loaded ----
start "" /min powershell -NoProfile -Command "Start-Sleep -Seconds 30; Start-Process 'http://127.0.0.1:%PORT%/'"

cd scripts
python serve_fusion.py --host 0.0.0.0 --port %PORT%

echo.
echo Service stopped. Press any key to close.
pause >nul
