@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
title Siamchai and TrueCorp Installer
cls

echo ========================================================
echo    Siamchai and TrueCorp - Setup and Installation
echo ========================================================
echo.

:: 1. Auto-detect Python
set "PY_CMD="

python --version >nul 2>&1
if %errorlevel% equ 0 (
    set "PY_CMD=python"
)

if not defined PY_CMD (
    py --version >nul 2>&1
    if !errorlevel! equ 0 (
        set "PY_CMD=py"
    )
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
    echo [ERROR] ไม่พบ Python ในเครื่องนี้
    echo --------------------------------------------------------
    echo 1. หากยังไม่ได้ติดตั้ง Python:
    echo    กรุณาดาวน์โหลด Python 3.11 หรือ 3.12 จาก:
    echo    https://www.python.org/downloads/
    echo.
    echo 2. หากติดตั้งไปแล้ว:
    echo    - ตอนติดตั้งอย่าลืมติ๊กถูก [Add python.exe to PATH]
    echo    - หรือลองปิดและเปิดหน้าต่างนี้ใหม่อีกครั้ง
    echo --------------------------------------------------------
    echo.
    pause
    exit /b 1
)

echo [OK] ตรวจพบ Python:
"%PY_CMD%" --version
echo.

echo [2/2] กำลังติดตั้งไลบรารีที่จำเป็น (FastAPI, Selenium, OpenPyXL, Pandas)...
echo --------------------------------------------------------
"%PY_CMD%" -m pip install --upgrade pip
"%PY_CMD%" -m pip install -r requirements.txt

if %errorlevel% equ 0 (
    echo.
    echo ========================================================
    echo    [SUCCESS] ติดตั้งไลบรารีเรียบร้อยสมบูรณ์แล้ว!
    echo    สามารถดับเบิ้ลคลิก "start_online.bat" เพื่อเปิดใช้งานได้ทันที
    echo ========================================================
) else (
    echo.
    echo [ERROR] การติดตั้งไลบรารีไม่สมบูรณ์ กรุณาตรวจสอบการเชื่อมต่ออินเทอร์เน็ต
)

echo.
pause
