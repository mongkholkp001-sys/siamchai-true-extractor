@echo off
title Siamchai and True Hub Updater
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0update.ps1"
if %errorlevel% neq 0 (
    echo.
    echo Press any key to exit...
    pause >nul
)
