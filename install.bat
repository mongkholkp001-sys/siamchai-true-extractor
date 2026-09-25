@echo off
chcp 65001 >nul
title Siamchai and TrueCorp Installer
cls

echo ========================================================
echo   Siamchai and TrueCorp - Setup and Installation
echo ========================================================
echo.

:: 1. Auto-detect Python
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

if not defined PY_CMD goto :NO_PYTHON

echo [OK] ตรวจพบ Python:
"%PY_CMD%" --version
echo.

echo กำลังติดตั้งไลบรารีที่จำเป็น (FastAPI, Selenium, OpenPyXL, Pandas)...
echo --------------------------------------------------------
"%PY_CMD%" -m pip install --upgrade pip
"%PY_CMD%" -m pip install -r requirements.txt

if errorlevel 1 goto :INSTALL_FAIL

echo.
echo ========================================================
echo   [SUCCESS] ติดตั้งไลบรารีเรียบร้อยสมบูรณ์แล้ว!
echo   สามารถดับเบิ้ลคลิก "start_online.bat" เพื่อเปิดใช้งานได้ทันที
echo ========================================================
echo.
pause
exit /b 0

:INSTALL_FAIL
echo.
echo [ERROR] ติดตั้งไลบรารีไม่สำเร็จ กรุณาตรวจสอบการเชื่อมต่ออินเทอร์เน็ต
echo.
pause
exit /b 1

:NO_PYTHON
echo ========================================================
echo  [แจ้งเตือน] เครื่องนี้ยังไม่ได้ติดตั้งโปรแกรม Python
echo ========================================================
echo.
echo  ไฟล์ install.bat นี้เป็นตัวติดตั้งไลบรารีของระบบ
echo  แต่เครื่องคอมพิวเตอร์จำเป็นต้องมีโปรแกรม Python ก่อนครับ
echo.
echo  วิธีแก้ไข:
echo  1. ดาวน์โหลด Python 3.11 หรือ 3.12 จากเว็บ python.org
echo  2. ดับเบิ้ลคลิกติดตั้ง Python โดยอย่าลืมติ๊กถูก:
echo     [Add python.exe to PATH]
echo  3. เมื่อติดตั้ง Python เสร็จแล้ว ให้กดเปิด install.bat ใหม่อีกครั้ง
echo ========================================================
echo.
pause
exit /b 1
