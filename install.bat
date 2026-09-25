@echo off
chcp 65001 >nul
title ติดตั้งไลบรารีสำหรับระบบ Siamchai & TrueCorp
cls

echo ========================================================
echo    ติดตั้งโปรแกรมและไลบรารีที่จำเป็น (Setup & Install)
echo ========================================================
echo.
echo [1/2] ตรวจสอบ Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [X] ไม่พบ Python ในเครื่องนี้!
    echo กรุณาติดตั้ง Python จาก https://www.python.org/downloads/
    echo ** ข้อสำคัญ: ตอนติดตั้งอย่าลืมติ๊กถูก "Add Python to PATH" **
    echo.
    pause
    exit /b
)

echo [OK] ตรวจพบ Python เรียบร้อยแล้ว
echo.
echo [2/2] กำลังติดตั้งไลบรารีที่จำเป็นทั้งหมด (FastAPI, Selenium, OpenPyXL, Pandas)...
python -m pip install --upgrade pip
pip install -r requirements.txt

echo.
echo ========================================================
echo    [สำเร็จ] ติดตั้งไลบรารีเรียบร้อยแล้ว!
echo    สามารถดับเบิ้ลคลิก "start_online.bat" เพื่อเปิดใช้งานได้ทันที
echo ========================================================
echo.
pause
