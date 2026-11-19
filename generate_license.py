#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Customer Data Hub - License Key Generator
สำหรับผู้ดูแลระบบ (Admin: mongkholkp001@gmail.com)
ใช้สำหรับสร้างรหัสเปิดใช้งาน (License Key) ให้ลูกค้า พร้อมกำหนดวันหมดอายุ และล็อกรหัสเครื่อง (สูงสุด 3 เครื่อง)
"""

import os
import sys
import json
import subprocess
from datetime import datetime, date, timedelta

# Ensure parent directory is on sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.license_manager import generate_license_key, get_machine_id, verify_license_string, CONTACT_EMAIL

def copy_to_clipboard(text: str):
    try:
        if sys.platform == "win32":
            subprocess.run(["powershell", "-Command", f"Set-Clipboard -Value @'\n{text}\n'@"], check=True, capture_output=True)
            return True
    except Exception:
        pass
    return False

def interactive_mode():
    print("=" * 65)
    print("  🔑 Customer Data Hub - ระบบสร้างรหัสเปิดใช้งาน (License Generator)")
    print(f"  ผู้ดูแลระบบ: {CONTACT_EMAIL}")
    print("=" * 65)
    
    current_mch = get_machine_id()
    print(f"💻 รหัสเครื่องนี้ (Current Machine): {current_mch}")
    print("-" * 65)

    # 1. Customer Name
    customer = ""
    while not customer:
        customer = input("1. ระบุชื่อลูกค้า / บริษัท (เช่น MaxGroup, ร้านค้า ก): ").strip()
        if not customer:
            print("   ⚠️ กรุณาระบุชื่อลูกค้า")

    # 2. Expiration Date
    print("\n2. เลือกระยะเวลาการใช้งาน:")
    print("   [1] 30 วัน (1 เดือน)")
    print("   [2] 90 วัน (3 เดือน)")
    print("   [3] 180 วัน (6 เดือน)")
    print("   [4] 365 วัน (1 ปี)")
    print("   [5] กำหนดวันหมดอายุเอง (รูปแบบ YYYY-MM-DD)")
    
    choice = input("   เลือก (กด Enter เพื่อเลือก 30 วัน): ").strip()
    today = date.today()
    
    if choice == "2":
        exp_date = today + timedelta(days=90)
    elif choice == "3":
        exp_date = today + timedelta(days=180)
    elif choice == "4":
        exp_date = today + timedelta(days=365)
    elif choice == "5":
        while True:
            custom_str = input("   ระบุวันหมดอายุ (YYYY-MM-DD เช่น 2026-12-31): ").strip()
            try:
                exp_date = datetime.strptime(custom_str, "%Y-%m-%d").date()
                if exp_date <= today:
                    print("   ⚠️ วันหมดอายุต้องเป็นวันในอนาคต")
                    continue
                break
            except ValueError:
                print("   ⚠️ รูปแบบวันที่ไม่ถูกต้อง กรุณากรอกแบบ YYYY-MM-DD")
    else: # default 30 days
        exp_date = today + timedelta(days=30)
    
    exp_date_str = exp_date.strftime("%Y-%m-%d")
    days_left = (exp_date - today).days

    # 3. Machine IDs (Up to 3 machines)
    print("\n3. ระบุรหัสเครื่องของลูกค้า (Machine ID) ที่อนุญาตให้ใช้งาน:")
    print("   (รหัสเครื่องจะมีรูปแบบ เช่น CDH-XXXX-XXXX-XXXX-XXXX)")
    print("   * สามารถใส่ได้สูงสุด 3 เครื่อง (หากลูกค้ายื่นมาเครื่องเดียวก่อน ให้กรอกเครื่องที่ 1 แล้วกด Enter ข้ามเครื่องที่ 2-3)*")
    
    machines = []
    for i in range(1, 4):
        prompt = f"   รหัสเครื่องที่ {i} (หรือกด Enter เพื่อข้าม): "
        m_id = input(prompt).strip().upper()
        if m_id:
            machines.append(m_id)
            print(f"     ✅ บันทึกเครื่องที่ {i}: {m_id}")
    
    if not machines:
        print("\n   ⚠️ คุณไม่ได้ระบุรหัสเครื่องใดๆ!")
        confirm = input(f"   ต้องการใช้รหัสเครื่องนี้ ({current_mch}) แทนหรือไม่? (y/n): ").strip().lower()
        if confirm in ["y", "yes", ""]:
            machines.append(current_mch)
        else:
            print("   ❌ ยกเลิกการสร้างรหัสเนื่องจากไม่มีรหัสเครื่อง")
            return

    # 4. Generate Key
    license_key = generate_license_key(
        customer=customer,
        expire_date=exp_date_str,
        machines=machines,
        max_machines=3
    )

    # 5. Verify & Print
    verify_result = verify_license_string(license_key, current_machine_id=machines[0])
    
    print("\n" + "=" * 65)
    print("🎉 สร้างรหัสเปิดใช้งาน (License Key) สำเร็จเรียบร้อยแล้ว!")
    print("=" * 65)
    print(f"👤 ชื่อลูกค้า:      {customer}")
    print(f"📅 ใช้งานได้ถึง:    {exp_date_str} (อีก {days_left} วัน)")
    print(f"💻 จำนวนเครื่อง:     {len(machines)} / 3 เครื่อง")
    for idx, m in enumerate(machines, 1):
        print(f"   เครื่องที่ {idx}:     {m}")
    print("-" * 65)
    print("🔑 รหัส License Key (ส่งข้อความนี้ให้ลูกค้า):")
    print("-" * 65)
    print(license_key)
    print("-" * 65)

    # Save to history file
    try:
        from backend.storage import DATA_DIR
        os.makedirs(DATA_DIR, exist_ok=True)
        history_file = os.path.join(DATA_DIR, "issued_licenses.json")
        history = []
        if os.path.exists(history_file):
            try:
                with open(history_file, "r", encoding="utf-8") as f:
                    history = json.load(f)
            except Exception:
                history = []
        history.append({
            "customer": customer,
            "expire_date": exp_date_str,
            "machines": machines,
            "max_machines": 3,
            "license_key": license_key,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        with open(history_file, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2, ensure_ascii=False)
    except Exception:
        pass

    # Save to separate file for easy sending
    safe_name = "".join(c for c in customer if c.isalnum() or c in (' ', '_', '-')).strip()
    out_filename = f"license_{safe_name}.txt"
    try:
        with open(out_filename, "w", encoding="utf-8") as f:
            f.write(f"Customer Data Hub - License Key\n")
            f.write(f"ลูกค้า: {customer}\n")
            f.write(f"หมดอายุ: {exp_date_str}\n")
            f.write(f"เครื่องที่อนุมัติ ({len(machines)}/3):\n")
            for m in machines:
                f.write(f"- {m}\n")
            f.write(f"\nLicense Key:\n{license_key}\n")
        print(f"💾 บันทึกไฟล์รหัสสำรองไว้ที่: {out_filename}")
    except Exception:
        pass

    if copy_to_clipboard(license_key):
        print("📋 คัดลอกรหัส License Key ลง Clipboard เรียบร้อยแล้ว (สามารถกด Ctrl + V ส่งให้ลูกค้าได้ทันที)")

    print("=" * 65)

if __name__ == "__main__":
    interactive_mode()
