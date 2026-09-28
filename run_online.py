"""
Customer Data Hub - Siamchai & True Unified Extractor
Online Runner with Auto Tunnel URL Extraction, Clipboard Copy & Auto Browser
"""

import sys
import os
import subprocess
import threading
import time
import re
import socket
import webbrowser

# Ensure utf-8 output on Windows
try:
    if sys.stdout.encoding != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from backend.app import app, get_lan_ip
import uvicorn

PORT = int(os.environ.get("PORT", 8000))
CLOUDFLARED_EXE = os.path.join(BASE_DIR, "cloudflared.exe")
LINK_FILE = os.path.join(BASE_DIR, "online_link.txt")

def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0

def start_server():
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="warning")

def launch_tunnel():
    if not os.path.exists(CLOUDFLARED_EXE):
        print(f"\n[!] ไม่พบไฟล์ {CLOUDFLARED_EXE}")
        print("    กรุณาตรวจสอบว่ามีไฟล์ cloudflared.exe อยู่ในโฟลเดอร์เดียวกันหรือไม่\n")
        return

    print("\n[*] กำลังเชื่อมต่อ Cloudflare Tunnel เพื่อสร้างลิงก์ออนไลน์ (ใช้เวลาประมาณ 3-5 วินาที)...")
    try:
        proc = subprocess.Popen(
            [CLOUDFLARED_EXE, "tunnel", "--url", f"http://localhost:{PORT}"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace"
        )
    except Exception as e:
        print(f"[!] เกิดข้อผิดพลาดในการเปิด cloudflared: {e}")
        return

    tunnel_url = None
    for line in proc.stderr:
        m = re.search(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com", line)
        if m:
            tunnel_url = m.group(0)
            break

    if tunnel_url:
        print("\n" + "=" * 72)
        print("  🎉 สร้างลิงก์ออนไลน์สำเร็จแล้ว! (ส่งลิงก์นี้ให้ทุกคนใช้งานได้เลย)")
        print("=" * 72)
        print(f"\n   👉 ลิงก์ออนไลน์: {tunnel_url}\n")
        print("=" * 72)
        print(f"  * บันทึกลิงก์ไว้ในไฟล์: {os.path.basename(LINK_FILE)}")
        print("  * กำลังเปิดลิงก์บนเบราว์เซอร์ให้อัตโนมัติ...")

        # Save to file for easy copy
        try:
            with open(LINK_FILE, "w", encoding="utf-8") as f:
                f.write(f"ลิงก์เข้าใช้งานระบบออนไลน์ (Siamchai & TrueCorp Unified Hub):\n")
                f.write(f"{tunnel_url}\n\n")
                f.write(f"ชื่อผู้ใช้: admin\nรหัสผ่าน: password123\n\n")
                f.write(f"สร้างเมื่อ: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        except Exception:
            pass

        # Copy to Windows clipboard
        try:
            clip_proc = subprocess.Popen(["clip"], stdin=subprocess.PIPE, text=True)
            clip_proc.communicate(input=tunnel_url.strip())
            print("  * [✓] คัดลอกลิงก์ลง Clipboard ให้แล้ว สามารถกดวาง (Ctrl+V) ส่งได้เลย!")
        except Exception:
            pass

        print("=" * 72 + "\n")

        # Open in browser
        try:
            webbrowser.open(tunnel_url)
        except Exception:
            pass
    else:
        print("[!] ไม่สามารถดึงลิงก์ Cloudflare ได้ กรุณาตรวจสอบการเชื่อมต่ออินเทอร์เน็ต")

    # Keep tunnel alive
    try:
        proc.wait()
    except KeyboardInterrupt:
        proc.terminate()

if __name__ == "__main__":
    lan_ip = get_lan_ip()
    print("=" * 72)
    print("      SIAMCHAI & TRUECORP UNIFIED EXTRACTOR - ONLINE MODE")
    print("=" * 72)
    print(f" [OK] เข้าใช้งานบนเครื่องนี้:    http://localhost:{PORT}")
    print(f" [OK] เข้าใช้งานผ่านมือถือ/LAN:  http://{lan_ip}:{PORT}")
    print("=" * 72)
    print(" * ชื่อผู้ใช้และรหัสผ่านเริ่มต้น: admin / password123")
    print("=" * 72)

    # Check if server is already running
    if is_port_in_use(PORT):
        print(f"\n[OK] ตรวจพบ Web Server กำลังทำงานอยู่บนพอร์ต {PORT} อยู่แล้ว")
    else:
        print(f"\n[*] กำลังเริ่ม Web Server บนพอร์ต {PORT}...")
        server_thread = threading.Thread(target=start_server, daemon=True)
        server_thread.start()
        time.sleep(1.5)

    launch_tunnel()
