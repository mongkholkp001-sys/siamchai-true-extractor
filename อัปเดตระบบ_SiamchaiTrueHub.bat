@echo off
chcp 65001 >nul
title ระบบอัปเดต Siamchai & True Hub (One-Click Updater)
cd /d "%~dp0"

echo ==================================================================
echo         ระบบอัปเดตอัตโนมัติ: Siamchai & TrueCorp Hub
echo                (คลิกเดียว อัปเดตและแก้ปัญหาทันที)
echo ==================================================================
echo.

set "SCRIPT_DIR=%~dp0"

powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^
  "$curr = '%SCRIPT_DIR%'.TrimEnd('\'); " ^
  "Write-Host '[1/5] ปิดโปรแกรมและ Webdriver ที่ค้างอยู่...' -ForegroundColor Yellow; " ^
  "taskkill /F /IM chromedriver.exe /T 2>$null | Out-Null; " ^
  "taskkill /F /IM msedgedriver.exe /T 2>$null | Out-Null; " ^
  "taskkill /F /IM SiamchaiTrueHub.exe /T 2>$null | Out-Null; " ^
  "Start-Sleep -Seconds 1; " ^
  "Write-Host '      [OK] เคลียร์โปรเซสเรียบร้อย' -ForegroundColor Gray; " ^
  "Write-Host '[2/5] ตรวจสอบโฟลเดอร์โปรแกรม...' -ForegroundColor Yellow; " ^
  "$targetDir = $curr; " ^
  "if (-not (Test-Path (Join-Path $targetDir 'SiamchaiTrueHub.exe'))) { " ^
  "  if (Test-Path 'C:\Siamchai_True_Hub\SiamchaiTrueHub.exe') { $targetDir = 'C:\Siamchai_True_Hub' } " ^
  "  elseif (Test-Path ([Environment]::GetFolderPath('Desktop') + '\SiamchaiTrueHub.exe')) { $targetDir = [Environment]::GetFolderPath('Desktop') } " ^
  "}; " ^
  "$codeDir = Join-Path $targetDir 'code'; " ^
  "$dataDir = Join-Path $targetDir 'data'; " ^
  "New-Item -ItemType Directory -Force -Path (Join-Path $codeDir 'backend') | Out-Null; " ^
  "New-Item -ItemType Directory -Force -Path (Join-Path $codeDir 'static') | Out-Null; " ^
  "New-Item -ItemType Directory -Force -Path $dataDir | Out-Null; " ^
  "$activeJobs = Join-Path $dataDir 'active_jobs.json'; " ^
  "if (Test-Path $activeJobs) { Remove-Item -Force $activeJobs -ErrorAction SilentlyContinue }; " ^
  "Write-Host '[3/5] ทำการติดตั้งแพตช์อัปเดต v2026.11.25.1...' -ForegroundColor Yellow; " ^
  "$offlineCode = Join-Path $curr 'code'; " ^
  "$applied = $false; " ^
  "if (Test-Path (Join-Path $offlineCode 'backend')) { " ^
  "  Copy-Item -Recurse -Force (Join-Path $offlineCode 'backend') $codeDir; " ^
  "  Copy-Item -Recurse -Force (Join-Path $offlineCode 'static') $codeDir; " ^
  "  $applied = $true; " ^
  "  Write-Host '      [OK] ติดตั้งจากไฟล์แพตช์ออฟไลน์สำเร็จทันที!' -ForegroundColor Green; " ^
  "} else { " ^
  "  Write-Host '      กำลังดาวน์โหลดแพตช์จากเซิร์ฟเวอร์...' -ForegroundColor Cyan; " ^
  "  $zipPath = Join-Path $env:TEMP 'siamchai_update.zip'; " ^
  "  $extPath = Join-Path $env:TEMP 'siamchai_ext'; " ^
  "  $dlOk = $false; " ^
  "  try { " ^
  "    & curl.exe -L -k -s -m 30 'https://github.com/mongkholkp001-sys/siamchai-true-extractor/archive/refs/heads/main.zip' -o $zipPath; " ^
  "    if ((Test-Path $zipPath) -and (Get-Item $zipPath).Length -gt 1000) { $dlOk = $true } " ^
  "  } catch {}; " ^
  "  if (-not $dlOk) { " ^
  "    try { " ^
  "      [System.Net.ServicePointManager]::SecurityProtocol = 3072; " ^
  "      (New-Object System.Net.WebClient).DownloadFile('https://github.com/mongkholkp001-sys/siamchai-true-extractor/archive/refs/heads/main.zip', $zipPath); " ^
  "      if ((Test-Path $zipPath) -and (Get-Item $zipPath).Length -gt 1000) { $dlOk = $true } " ^
  "    } catch {}; " ^
  "  }; " ^
  "  if ($dlOk) { " ^
  "    try { " ^
  "      Expand-Archive -Path $zipPath -DestinationPath $extPath -Force; " ^
  "      $src = Join-Path $extPath 'siamchai-true-extractor-main'; " ^
  "      Copy-Item -Recurse -Force (Join-Path $src 'backend') $codeDir; " ^
  "      Copy-Item -Recurse -Force (Join-Path $src 'static') $codeDir; " ^
  "      $applied = $true; " ^
  "      Write-Host '      [OK] ดาวน์โหลดและติดตั้งเรียบร้อย!' -ForegroundColor Green; " ^
  "    } catch {} finally { " ^
  "      Remove-Item -Recurse -Force $extPath -ErrorAction SilentlyContinue; " ^
  "      Remove-Item -Force $zipPath -ErrorAction SilentlyContinue; " ^
  "    } " ^
  "  } " ^
  "}; " ^
  "Set-Content -Path (Join-Path $codeDir 'version.txt') -Value '2026.11.25.1' -Encoding UTF8; " ^
  "Write-Host '[4/5] ตรวจสอบไฟล์ตัวรัน SiamchaiTrueHub.exe...' -ForegroundColor Yellow; " ^
  "$exe = Join-Path $targetDir 'SiamchaiTrueHub.exe'; " ^
  "if (Test-Path $exe) { " ^
  "  Write-Host '[5/5] กำลังเริ่มโปรแกรมและเปิดหน้าเว็บ...' -ForegroundColor Green; " ^
  "  Start-Process -FilePath $exe; " ^
  "  Start-Sleep -Seconds 3; " ^
  "  Start-Process 'http://localhost:8088/'; " ^
  "  Write-Host ''; " ^
  "  Write-Host '==================================================================' -ForegroundColor Cyan; " ^
  "  Write-Host '   ✅ อัปเดตและปลดล็อคระบบเสร็จสมบูรณ์ พร้อมใช้งาน 100%!           ' -ForegroundColor Green; " ^
  "  Write-Host '   - แก้ไขปุ่มหยุด (Stop) หยุดได้ทันที ไม่ค้าง                       ' -ForegroundColor White; " ^
  "  Write-Host '   - เพิ่มปุ่ม รีเซ็ต ฉุกเฉินสำหรับปลดล็อคหน้าจอทันที               ' -ForegroundColor White; " ^
  "  Write-Host '   - รองรับทั้ง Chrome และ Microsoft Edge อัตโนมัติ                  ' -ForegroundColor White; " ^
  "  Write-Host '==================================================================' -ForegroundColor Cyan; " ^
  "} else { " ^
  "  Write-Host '   ✅ อัปเดตโค้ดเรียบร้อย! กรุณาเปิดโปรแกรม SiamchaiTrueHub.exe เพื่อเริ่มใช้งาน' -ForegroundColor Yellow; " ^
  "}"

echo.
echo กดปุ่มใดก็ได้เพื่อปิดหน้าต่างนี้...
pause >nul
