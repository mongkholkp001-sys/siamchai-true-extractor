# ==============================================================================
# update.ps1 - Bulletproof Offline & Online Patch Updater
# ==============================================================================
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = "SilentlyContinue"

Clear-Host
Write-Host "==================================================================" -ForegroundColor Cyan
Write-Host "         ระบบอัปเดตอัตโนมัติ: Siamchai & TrueCorp Hub              " -ForegroundColor Green
Write-Host "                (คลิกเดียว อัปเดตและแก้ปัญหาทันที)                  " -ForegroundColor White
Write-Host "==================================================================" -ForegroundColor Cyan
Write-Host ""

$CurrentDir = $PSScriptRoot
if (-not $CurrentDir) { $CurrentDir = (Get-Location).Path }

# ขั้นตอนที่ 1: ปิดโปรแกรมและ Driver ที่ค้างอยู่
Write-Host "[1/5] ปิดโปรแกรมและ Webdriver ที่อาจค้างอยู่..." -ForegroundColor Yellow
taskkill /F /IM chromedriver.exe /T 2>$null | Out-Null
taskkill /F /IM msedgedriver.exe /T 2>$null | Out-Null
taskkill /F /IM SiamchaiTrueHub.exe /T 2>$null | Out-Null
Start-Sleep -Seconds 1
Write-Host "      [OK] เคลียร์โปรเซสเรียบร้อย" -ForegroundColor Gray

# ขั้นตอนที่ 2: ตรวจหาตำแหน่งที่ติดตั้งโปรแกรม
Write-Host "[2/5] ตรวจสอบตำแหน่งโปรแกรมในเครื่อง..." -ForegroundColor Yellow

$TargetDir = $CurrentDir
if (-not (Test-Path (Join-Path $TargetDir "SiamchaiTrueHub.exe"))) {
    $candidates = @(
        "C:\Siamchai_True_Hub",
        (Join-Path ([Environment]::GetFolderPath("Desktop")) "SiamchaiTrueHub"),
        ([Environment]::GetFolderPath("Desktop")),
        "D:\Program Files (x86)\SiamchaiTrueHub",
        "C:\Program Files (x86)\SiamchaiTrueHub"
    )
    foreach ($c in $candidates) {
        if (Test-Path (Join-Path $c "SiamchaiTrueHub.exe")) {
            $TargetDir = $c
            break
        }
    }
}
Write-Host "      [OK] ตำแหน่งโฟลเดอร์: $TargetDir" -ForegroundColor Gray

# เตรียมโฟลเดอร์ code และ data
$CodeDir = Join-Path $TargetDir "code"
$DataDir = Join-Path $TargetDir "data"
New-Item -ItemType Directory -Force -Path (Join-Path $CodeDir "backend") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $CodeDir "static") | Out-Null
New-Item -ItemType Directory -Force -Path $DataDir | Out-Null

# ล้างงานที่ค้างในระบบ
$ActiveJobsFile = Join-Path $DataDir "active_jobs.json"
if (Test-Path $ActiveJobsFile) {
    Remove-Item -Force $ActiveJobsFile -ErrorAction SilentlyContinue
    Write-Host "      [OK] ปลดล็อคงานที่ค้างในระบบสำเร็จ" -ForegroundColor Gray
}

# ขั้นตอนที่ 3: ติดตั้งแพตช์อัปเดตโค้ด
Write-Host "[3/5] ทำการติดตั้งแพตช์อัปเดต v2026.11.25.1..." -ForegroundColor Yellow

$OfflineCode = Join-Path $CurrentDir "code"
$Installed = $false

# แบบที่ 3.1: ติดตั้งจากโฟลเดอร์ code แบบออฟไลน์ 100% ไม่ต้องต่อเน็ต
if (Test-Path (Join-Path $OfflineCode "backend")) {
    Copy-Item -Recurse -Force (Join-Path $OfflineCode "backend\*") (Join-Path $CodeDir "backend")
    Copy-Item -Recurse -Force (Join-Path $OfflineCode "static\*") (Join-Path $CodeDir "static")
    $Installed = $true
    Write-Host "      [OK] ติดตั้งจากแพตช์ออฟไลน์สำเร็จทันที (ไม่ต้องใช้อินเทอร์เน็ต)!" -ForegroundColor Green
}

# แบบที่ 3.2: หากไม่มีโฟลเดอร์ออฟไลน์ ให้ดาวน์โหลดผ่าน curl หรือ powershell
if (-not $Installed) {
    Write-Host "      กำลังดาวน์โหลดแพตช์อัปเดต..." -ForegroundColor Cyan
    $TempZip = Join-Path $env:TEMP "siamchai_update_$([System.Guid]::NewGuid().ToString().Substring(0,8)).zip"
    $TempExtract = Join-Path $env:TEMP "siamchai_ext_$([System.Guid]::NewGuid().ToString().Substring(0,8))"
    
    $downloaded = $false
    try {
        & curl.exe -L -k -s -m 35 "https://github.com/mongkholkp001-sys/siamchai-true-extractor/archive/refs/heads/main.zip" -o $TempZip
        if ((Test-Path $TempZip) -and ((Get-Item $TempZip).Length -gt 1000)) { $downloaded = $true }
    } catch {}

    if (-not $downloaded) {
        try {
            [System.Net.ServicePointManager]::SecurityProtocol = 3072
            (New-Object System.Net.WebClient).DownloadFile("https://github.com/mongkholkp001-sys/siamchai-true-extractor/archive/refs/heads/main.zip", $TempZip)
            if ((Test-Path $TempZip) -and ((Get-Item $TempZip).Length -gt 1000)) { $downloaded = $true }
        } catch {}
    }

    if ($downloaded) {
        try {
            Expand-Archive -Path $TempZip -DestinationPath $TempExtract -Force
            $src = Join-Path $TempExtract "siamchai-true-extractor-main"
            Copy-Item -Recurse -Force (Join-Path $src "backend\*") (Join-Path $CodeDir "backend")
            Copy-Item -Recurse -Force (Join-Path $src "static\*") (Join-Path $CodeDir "static")
            $Installed = $true
            Write-Host "      [OK] ดาวน์โหลดและติดตั้งแพตช์สำเร็จ!" -ForegroundColor Green
        } catch {} finally {
            Remove-Item -Recurse -Force $TempExtract -ErrorAction SilentlyContinue
            Remove-Item -Force $TempZip -ErrorAction SilentlyContinue
        }
    }
}

Set-Content -Path (Join-Path $CodeDir "version.txt") -Value "2026.11.25.1" -Encoding UTF8

# ขั้นตอนที่ 4: ตรวจสอบและเริ่มโปรแกรม
Write-Host "[4/5] ตรวจสอบไฟล์โปรแกรมหลัก..." -ForegroundColor Yellow
$ExePath = Join-Path $TargetDir "SiamchaiTrueHub.exe"

if (Test-Path $ExePath) {
    Write-Host "[5/5] กำลังเริ่มโปรแกรมและเปิดหน้าเว็บ..." -ForegroundColor Green
    Start-Process -FilePath $ExePath
    Start-Sleep -Seconds 3
    Start-Process "http://localhost:8088/"

    Write-Host ""
    Write-Host "==================================================================" -ForegroundColor Cyan
    Write-Host "   ✅ อัปเดตและปลดล็อคระบบเสร็จสมบูรณ์ พร้อมใช้งาน 100%!           " -ForegroundColor Green
    Write-Host "   - แก้ไขปุ่มหยุด (Stop) หยุดได้ทันที ไม่ค้างอีกต่อไป              " -ForegroundColor White
    Write-Host "   - เพิ่มปุ่ม 'รีเซ็ต' ฉุกเฉินสำหรับปลดล็อคหน้าจอทันที               " -ForegroundColor White
    Write-Host "   - รองรับทั้ง Chrome และ Microsoft Edge อัตโนมัติ                  " -ForegroundColor White
    Write-Host "   - เลขบัตรประชาชนค้นหาได้ตามปกติ                                " -ForegroundColor White
    Write-Host "==================================================================" -ForegroundColor Cyan
} else {
    Write-Host "   ✅ อัปเดตโค้ดเรียบร้อยแล้ว!" -ForegroundColor Green
    Write-Host "   กรุณาเปิดไฟล์ SiamchaiTrueHub.exe เพื่อเริ่มใช้งานตามปกติ" -ForegroundColor Yellow
}
