@echo off
REM ============================================================
REM  Stop the Blue Coral Guardian demo service (serve_fusion.py)
REM  Usage: double-click this file. It frees port 8000.
REM
REM  Why: the service loads 4 models on the GPU. When you are NOT
REM  demoing, shut it down so nothing can consume your compute.
REM  (Team policy: turn it off when not in use.)
REM
REM  NOTE: keep this file pure ASCII - Chinese characters break cmd
REM  under the GBK code page.
REM ============================================================
setlocal enabledelayedexpansion
echo.
echo === Blue Coral Guardian - stopping demo service ===
echo.

set FOUND=0
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8000" ^| findstr "LISTENING"') do (
  if not "%%p"=="0" (
    echo   killing PID %%p ...
    taskkill /PID %%p /F >nul 2>&1
    if !errorlevel!==0 (echo     OK) else (echo     failed - try running as Administrator)
    set FOUND=1
  )
)

if "!FOUND!"=="0" echo   nothing was listening on port 8000.

REM Releasing the port takes a moment - wait up to ~6s before judging,
REM otherwise we would wrongly report "still in use" right after taskkill.
set WAIT=0
:check
netstat -ano | findstr ":8000" | findstr "LISTENING" >nul 2>&1
if !errorlevel!==0 (
  set /a WAIT+=1
  if !WAIT! lss 6 (
    ping -n 2 127.0.0.1 >nul
    goto check
  )
)

echo.
netstat -ano | findstr ":8000" | findstr "LISTENING" >nul 2>&1
if !errorlevel!==0 (
  echo   WARNING: port 8000 is STILL in use. Close the service window manually.
) else (
  echo   OK: port 8000 is free. Service stopped - GPU no longer held by the demo.
)
echo.
pause
