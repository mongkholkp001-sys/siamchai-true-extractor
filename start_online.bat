@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
title Siamchai and TrueCorp Unified Extractor (Online Mode)
cls

echo ========================================================
echo     Siamchai and TrueCorp Unified Intelligence Hub
echo     โหมดออนไลน์ (Online Mode via Cloudflare Tunnel)
echo ========================================================
echo.

:: Auto-detect Python
set "PY_CMD="

python --version >nul 2>&1
if %errorlevel% equ 0 set "PY_CMD=python"

if not defined PY_CMD (
    py --version >nul 2>&1
    if !errorlevel! equ 0 set "PY_CMD=py"
)

if not defined PY_CMD (
    for %%V in (313 312 311 310) do (
        if exist "%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe" (
            set "PY_CMD=%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe"
        )
    )
)

if not defined PY_CMD (
    for %%V in (313 312 311 310) do (
        if exist "%ProgramFiles%\Python%%V\python.exe" (
            set "PY_CMD=%ProgramFiles%\Python%%V\python.exe"
        )
    )
)

if not defined PY_CMD (
    echo [ERROR] ไม่พบ Python ในเครื่องนี้ กรุณาติดตั้ง Python หรือรัน install.bat ก่อน
    pause
    exit /b 1
)

echo [1/2] กำลังเริ่ม Web Server ภายในเครื่อง...
start "SiamchaiTrue-Backend" "%PY_CMD%" run.py
timeout /t 3 /nobreak >nul

echo.
echo [2/2] กำลังสร้างลิงก์ออนไลน์ Cloudflare Tunnel...
echo.
echo ========================================================
echo เมื่อลิงก์ปรากฏด้านล่าง (https://xxxx.trycloudflare.com)
echo สามารถคัดลอกลิงก์ไปเปิดใช้งานบนมือถือหรือเครื่องอื่นได้ทันที!
echo ========================================================
echo.

.\cloudflared.exe tunnel --url http://localhost:8000
pause
