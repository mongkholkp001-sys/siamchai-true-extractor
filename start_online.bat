@echo off
chcp 65001 >nul
title Siamchai & TrueCorp Unified Extractor (Online Mode)
cls

echo ========================================================
echo     Siamchai & TrueCorp Unified Intelligence Hub
echo     โหมดออนไลน์ (Online Mode via Cloudflare Tunnel)
echo ========================================================
echo.
echo [1/2] กำลังเริ่ม Web Server ภายในเครื่อง...
start "SiamchaiTrue-Backend" python run.py
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
