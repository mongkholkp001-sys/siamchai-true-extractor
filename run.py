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

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from backend.app import app, get_lan_ip

PORT = 8000

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

    threading.Thread(target=open_browser, daemon=True).start()
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info")
