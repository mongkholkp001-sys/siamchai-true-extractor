@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
title Siamchai and TrueCorp Unified Extractor (Online Mode)
cls

:: Auto-detect Python
set "PY_CMD="

python --version >nul 2>&1
if not errorlevel 1 set "PY_CMD=python"

if not defined PY_CMD (
    py --version >nul 2>&1
    if not errorlevel 1 set "PY_CMD=py"
)

if not defined PY_CMD (
    for %%V in (313 312 311 310 39) do (
        if exist "%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe" (
            set "PY_CMD=%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe"
        )
    )
)

if not defined PY_CMD (
    for %%V in (313 312 311 310 39) do (
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

:: Run the unified online runner
"%PY_CMD%" run_online.py

pause
