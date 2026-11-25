"""
Customer Data Hub - Siamchai & True Unified Extractor
Main Server Entry Point
"""

import sys
import os
import webbrowser
import threading
import time
import uvicorn

# Ensure utf-8 output on Windows
try:
    if sys.stdout.encoding != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

def sync_code_from_cloud():
    """Checks central VPS for updated code bundle on startup and auto-updates in 0.5s."""
    if os.name != "nt":
        return
    try:
        import urllib.request
        import json
        import zipfile
        import io

        cloud_host = "http://119.10.137.52:8000"
        v_url = f"{cloud_host}/api/client/version"
        req = urllib.request.Request(v_url, headers={"User-Agent": "HubClient/2.0"})
        with urllib.request.urlopen(req, timeout=2.5) as r:
            if r.status != 200:
                return
            data = json.loads(r.read().decode())
            server_ver = data.get("version")

        if not server_ver:
            return

        code_dir = r"C:\Siamchai_True_Hub\code"
        v_file = os.path.join(code_dir, "version.txt")
        local_ver = None
        if os.path.exists(v_file):
            try:
                with open(v_file, "r", encoding="utf-8") as f:
                    local_ver = f.read().strip()
            except Exception:
                pass

        if server_ver != local_ver:
            print(f"[*] ตรวจพบการอัปเดตระบบอัตโนมัติจากคลาวด์ (v{server_ver})...")
            dl_url = f"{cloud_host}/api/client/download-code"
            req_dl = urllib.request.Request(dl_url, headers={"User-Agent": "HubClient/2.0"})
            with urllib.request.urlopen(req_dl, timeout=8) as dl_resp:
                if dl_resp.status == 200:
                    zdata = io.BytesIO(dl_resp.read())
                    os.makedirs(code_dir, exist_ok=True)
                    with zipfile.ZipFile(zdata) as z:
                        z.extractall(code_dir)
                    with open(v_file, "w", encoding="utf-8") as f:
                        f.write(server_ver)
                    print(f"[✓] อัปเดตระบบล่าสุดเรียบร้อยแล้ว (v{server_ver})")
    except Exception:
        pass

# 1. Run sync BEFORE importing backend
sync_code_from_cloud()

# 2. Priority path: local dynamic code folder first
exe_dir = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, "frozen", False) else __file__))
for candidate_dir in [os.path.join(exe_dir, "code"), r"C:\Siamchai_True_Hub\code"]:
    if os.path.exists(os.path.join(candidate_dir, "backend")):
        sys.path.insert(0, candidate_dir)
        break

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from backend.app import app, get_lan_ip

PORT = int(os.environ.get("PORT", 8088))

def open_browser():
    time.sleep(1.8)
    url = f"http://localhost:{PORT}"
    print(f"\n[+] กำลังเปิดเบราว์เซอร์อัตโนมัติ: {url}\n")
    try:
        webbrowser.open(url)
    except Exception:
        pass

if __name__ == "__main__":
    lan_ip = get_lan_ip()
    print("=" * 65)
    print("      SIAMCHAI & TRUECORP UNIFIED EXTRACTOR v2.0")
    print("=" * 65)
    print(f" [OK] เข้าใช้งานบนเครื่องนี้:    http://localhost:{PORT}")
    print(f" [OK] เข้าใช้งานผ่านมือถือ/LAN:  http://{lan_ip}:{PORT}")
    print("=" * 65)
    print(" * ชื่อผู้ใช้และรหัสผ่านเริ่มต้น: admin / password123")
    print(" * สามารถเปลี่ยนรหัสผ่านและบัญชีสยามชัย/ทรู ได้ที่เมนูตั้งค่า")
    print("=" * 65)

    if os.name == "nt" and not os.environ.get("RENDER"):
        threading.Thread(target=open_browser, daemon=True).start()
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info")
