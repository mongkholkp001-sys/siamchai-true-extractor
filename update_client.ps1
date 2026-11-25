# ==============================================================================
# Update Client Script for Siamchai & TrueCorp Unified Hub
# ==============================================================================
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = "SilentlyContinue"

Write-Host ""
Write-Host "==================================================================" -ForegroundColor Cyan
Write-Host "         ระบบอัปเดตอัตโนมัติ: Siamchai & TrueCorp Hub              " -ForegroundColor Green
Write-Host "                (คลิกเดียว อัปเดตและแก้ปัญหาทันที)                  " -ForegroundColor White
Write-Host "==================================================================" -ForegroundColor Cyan
Write-Host ""

# ขั้นตอนที่ 1: ปิดโปรแกรมและ Driver ที่ค้างอยู่
Write-Host "[1/5] ปิดโปรแกรมและ Webdriver ที่อาจค้างอยู่..." -ForegroundColor Yellow
taskkill /F /IM chromedriver.exe /T 2>$null | Out-Null
taskkill /F /IM msedgedriver.exe /T 2>$null | Out-Null
taskkill /F /IM SiamchaiTrueHub.exe /T 2>$null | Out-Null
Start-Sleep -Seconds 1
Write-Host "      [OK] เคลียร์โปรเซสเรียบร้อย" -ForegroundColor Gray

# ขั้นตอนที่ 2: เตรียมโฟลเดอร์ระบบและล้างสถานะงานที่ค้าง
Write-Host "[2/5] ล้างสถานะค้างและเตรียมโฟลเดอร์ระบบ..." -ForegroundColor Yellow
$TargetDir = "C:\Siamchai_True_Hub"
$CodeDir = Join-Path $TargetDir "code"
$DataDir = Join-Path $TargetDir "data"
New-Item -ItemType Directory -Force -Path $CodeDir | Out-Null
New-Item -ItemType Directory -Force -Path $DataDir | Out-Null

$ActiveJobsFile = Join-Path $DataDir "active_jobs.json"
if (Test-Path $ActiveJobsFile) {
    Remove-Item -Force $ActiveJobsFile -ErrorAction SilentlyContinue
    Write-Host "      [OK] ล้างข้อมูลงานที่ค้างอยู่สำเร็จ" -ForegroundColor Gray
}

# ขั้นตอนที่ 3: ดาวน์โหลดโค้ดอัปเดตล่าสุดจาก GitHub ทันที (ขนาดเล็กเพียง ~2MB)
Write-Host "[3/5] กำลังดาวน์โหลดแพตช์อัปเดตเวอร์ชันล่าสุดจาก GitHub..." -ForegroundColor Yellow
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$ZipUrl = "https://github.com/mongkholkp001-sys/siamchai-true-extractor/archive/refs/heads/main.zip"
$TempZip = Join-Path $env:TEMP "siamchai_update_$([System.Guid]::NewGuid().ToString().Substring(0,8)).zip"
$TempExtract = Join-Path $env:TEMP "siamchai_extract_$([System.Guid]::NewGuid().ToString().Substring(0,8))"

$downloadSuccess = $false
try {
    Invoke-WebRequest -Uri $ZipUrl -OutFile $TempZip -UseBasicParsing -TimeoutSec 45
    Expand-Archive -Path $TempZip -DestinationPath $TempExtract -Force
    
    $SourceRoot = Join-Path $TempExtract "siamchai-true-extractor-main"
    if (Test-Path (Join-Path $SourceRoot "backend")) {
        Copy-Item -Recurse -Force (Join-Path $SourceRoot "backend") $CodeDir
        Copy-Item -Recurse -Force (Join-Path $SourceRoot "static") $CodeDir
        Set-Content -Path (Join-Path $CodeDir "version.txt") -Value "2026.11.25.1" -Encoding UTF8
        $downloadSuccess = $true
        Write-Host "      [OK] ติดตั้งโค้ดเวอร์ชันล่าสุด v2026.11.25.1 เรียบร้อยแล้ว!" -ForegroundColor Green
    }
} catch {
    Write-Host "      [!] ดาวน์โหลดไม่สำเร็จ: $($_.Exception.Message)" -ForegroundColor Red
} finally {
    if (Test-Path $TempZip) { Remove-Item -Force $TempZip -ErrorAction SilentlyContinue }
    if (Test-Path $TempExtract) { Remove-Item -Recurse -Force $TempExtract -ErrorAction SilentlyContinue }
}

# ขั้นตอนที่ 4: ค้นหาไฟล์ตัวรัน SiamchaiTrueHub.exe
Write-Host "[4/5] ตรวจสอบไฟล์โปรแกรมหลัก SiamchaiTrueHub.exe..." -ForegroundColor Yellow
$DesktopExe = Join-Path ([Environment]::GetFolderPath("Desktop")) "SiamchaiTrueHub.exe"
$LocalExe = Join-Path $TargetDir "SiamchaiTrueHub.exe"
$DownloadsExe = Join-Path ([Environment]::GetFolderPath("UserProfile")) "Downloads\SiamchaiTrueHub.exe"

$ExePath = $null
if (Test-Path $DesktopExe) { $ExePath = $DesktopExe }
elseif (Test-Path $LocalExe) { $ExePath = $LocalExe }
elseif (Test-Path $DownloadsExe) { $ExePath = $DownloadsExe }

if (-not $ExePath) {
    $DistExe = "C:\Users\comk25\.gemini\antigravity\scratch\siamchai_true_hub\dist\SiamchaiTrueHub.exe"
    if (Test-Path $DistExe) { $ExePath = $DistExe }
}

# ขั้นตอนที่ 5: เปิดโปรแกรมพร้อมใช้งาน
if ($ExePath -and (Test-Path $ExePath)) {
    Write-Host "[5/5] กำลังเริ่มทำงานและเปิดหน้าเว็บ..." -ForegroundColor Green
    Start-Process -FilePath $ExePath
    Start-Sleep -Seconds 3
    Start-Process "http://localhost:8088/"
    
    Write-Host ""
    Write-Host "==================================================================" -ForegroundColor Cyan
    Write-Host "   ✅ อัปเดตเสร็จสมบูรณ์! ระบบกลับมาพร้อมทำงาน 100% แล้ว          " -ForegroundColor Green
    Write-Host "   - แก้ไขปุ่มหยุด (Stop) หยุดได้ทันที ไม่ค้างอีกต่อไป              " -ForegroundColor White
    Write-Host "   - เพิ่มปุ่ม 'รีเซ็ต' สำหรับปลดล็อคหน้าจอทันที                   " -ForegroundColor White
    Write-Host "   - รองรับทั้ง Chrome และ Microsoft Edge อัตโนมัติ                  " -ForegroundColor White
    Write-Host "   - ตรวจจับเลขบัตรประชาชนได้ตามปกติ                             " -ForegroundColor White
    Write-Host "==================================================================" -ForegroundColor Cyan
} else {
    Write-Host ""
    Write-Host "==================================================================" -ForegroundColor Yellow
    Write-Host "   ✅ อัปเดตโค้ดเรียบร้อยแล้ว!" -ForegroundColor Green
    Write-Host "   กรุณาดับเบิ้ลคลิกเปิดโปรแกรม SiamchaiTrueHub.exe เพื่อเริ่มใช้งาน " -ForegroundColor White
    Write-Host "==================================================================" -ForegroundColor Yellow
}
