@echo off
title Siamchai Online Hub
cd /d "%~dp0"
cls
echo ========================================================
echo   Siamchai and TrueCorp Unified Extractor - Online Mode
echo ========================================================
echo.

if exist "run_online.py" (
    py -u run_online.py
    if errorlevel 1 python -u run_online.py
    pause
    exit /b
)

echo [*] กำลังเริ่มเซิร์ฟเวอร์...
start "SiamchaiTrue-Backend" py run.py
timeout /t 3 /nobreak >nul

echo.
echo [*] กำลังสร้างลิงก์ Cloudflare Tunnel...
echo.
.\cloudflared.exe tunnel --url http://localhost:8000
pause
