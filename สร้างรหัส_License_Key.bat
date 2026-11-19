@echo off
chcp 65001 >nul
title สร้างรหัส License Key - Customer Data Hub
cd /d "%~dp0"

:: Auto-detect Python
set "PY_CMD=python"
python --version >nul 2>&1
if %errorlevel% neq 0 (
    py --version >nul 2>&1
    if %errorlevel% equ 0 (
        set "PY_CMD=py"
    )
)

"%PY_CMD%" generate_license.py
pause
