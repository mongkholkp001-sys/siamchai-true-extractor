import os
import sys
import json
import time
import base64
import hmac
import hashlib
import platform
from datetime import datetime, date
from typing import Dict, Any, List, Optional

# Contact info for license requests
CONTACT_EMAIL = "mongkholkp001@gmail.com"

# Master signing secret - KEEP CONFIDENTIAL
MASTER_SIGNING_SECRET = "CDH_MASTER_SECRET_KEY_MONGKHOL_2026_SECURE_AUTH"

def get_machine_id() -> str:
    """
    Generates a persistent, unique, and human-friendly Machine ID for the current computer.
    Uses Windows MachineGuid if available, falling back to system hardware identifiers.
    Format: CDH-XXXX-XXXX-XXXX-XXXX
    """
    raw_id = ""
    
    # 1. Try Windows Registry MachineGuid (Most stable & unique on Windows)
    if platform.system() == "Windows":
        try:
            import winreg
            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE, 
                r"SOFTWARE\Microsoft\Cryptography", 
                0, 
                winreg.KEY_READ | winreg.KEY_WOW64_64KEY
            ) as key:
                guid, _ = winreg.QueryValueEx(key, "MachineGuid")
                if guid:
                    raw_id = str(guid).strip()
        except Exception:
            pass

    # 2. Fallback to Linux /etc/machine-id
    if not raw_id and os.path.exists("/etc/machine-id"):
        try:
            with open("/etc/machine-id", "r") as f:
                raw_id = f.read().strip()
        except Exception:
            pass

    # 3. Fallback to UUID node + platform
    if not raw_id:
        import uuid
        raw_id = f"{uuid.getnode()}-{platform.node()}-{platform.processor()}"

    # Hash with fixed salt and format as CDH-XXXX-XXXX-XXXX-XXXX
    digest = hashlib.sha256(f"CDH-HWID-{raw_id}".encode("utf-8")).hexdigest().upper()
    part1 = digest[0:4]
    part2 = digest[4:8]
    part3 = digest[8:12]
    part4 = digest[12:16]
    return f"CDH-{part1}-{part2}-{part3}-{part4}"


def generate_license_key(
    customer: str, 
    expire_date: str, 
    machines: List[str], 
    max_machines: int = 3
) -> str:
    """
    Generates a cryptographically signed license key string.
    customer: Name or company
    expire_date: YYYY-MM-DD
    machines: List of allowed Machine IDs (e.g. ['CDH-A1B2-C3D4-E5F6-0001'])
    max_machines: Max allowed machines (default 3)
    """
    clean_machines = [m.strip().upper() for m in machines if m.strip()]
    if len(clean_machines) > max_machines:
        clean_machines = clean_machines[:max_machines]

    payload = {
        "customer": customer.strip(),
        "expire_date": expire_date.strip(),
        "max_machines": int(max_machines),
        "machines": clean_machines,
        "issued_at": datetime.now().strftime("%Y-%m-%d")
    }

    payload_json = json.dumps(payload, separators=(',', ':'), sort_keys=True)
    payload_b64 = base64.urlsafe_b64encode(payload_json.encode("utf-8")).decode("ascii")
    
    # Generate HMAC-SHA256 signature
    sig = hmac.new(
        MASTER_SIGNING_SECRET.encode("utf-8"), 
        payload_b64.encode("utf-8"), 
        hashlib.sha256
    ).hexdigest()

    # Full license key format: CDHLIC.<payload_b64>.<sig>
    return f"CDHLIC.{payload_b64}.{sig}"


def verify_license_string(license_str: str, current_machine_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Verifies a license string against signature, expiration date, and current machine ID.
    """
    if not current_machine_id:
        current_machine_id = get_machine_id()
    current_machine_id = current_machine_id.strip().upper()

    if not license_str or not isinstance(license_str, str):
        return {
            "valid": False,
            "status": "NO_LICENSE",
            "message": "ยังไม่มีรหัสเปิดใช้งานระบบ",
            "current_machine": current_machine_id,
            "contact_email": CONTACT_EMAIL
        }

    clean_str = license_str.strip()
    if not clean_str.startswith("CDHLIC."):
        return {
            "valid": False,
            "status": "INVALID_FORMAT",
            "message": "รูปแบบรหัสเปิดใช้งานไม่ถูกต้อง",
            "current_machine": current_machine_id,
            "contact_email": CONTACT_EMAIL
        }

    parts = clean_str.split(".")
    if len(parts) != 3:
        return {
            "valid": False,
            "status": "INVALID_FORMAT",
            "message": "ส่วนประกอบของรหัสเปิดใช้งานไม่สมบูรณ์",
            "current_machine": current_machine_id,
            "contact_email": CONTACT_EMAIL
        }

    _, payload_b64, sig = parts

    # 1. Verify Signature
    expected_sig = hmac.new(
        MASTER_SIGNING_SECRET.encode("utf-8"), 
        payload_b64.encode("utf-8"), 
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(sig.lower(), expected_sig.lower()):
        return {
            "valid": False,
            "status": "INVALID_SIGNATURE",
            "message": "รหัสเปิดใช้งานไม่ถูกต้องหรือถูกแก้ไขโดยไม่ได้รับอนุญาต",
            "current_machine": current_machine_id,
            "contact_email": CONTACT_EMAIL
        }

    # 2. Decode payload
    try:
        payload_str = base64.urlsafe_b64decode(payload_b64.encode("ascii")).decode("utf-8")
        payload = json.loads(payload_str)
    except Exception as e:
        return {
            "valid": False,
            "status": "DECODE_ERROR",
            "message": f"ไม่สามารถอ่านข้อมูลใบอนุญาตได้: {e}",
            "current_machine": current_machine_id,
            "contact_email": CONTACT_EMAIL
        }

    customer = payload.get("customer", "Unknown")
    expire_str = payload.get("expire_date", "")
    max_machines = int(payload.get("max_machines", 3))
    allowed_machines = [m.strip().upper() for m in payload.get("machines", [])]
    issued_at = payload.get("issued_at", "")

    # 3. Check Expiration Date
    days_left = 0
    try:
        exp_date = datetime.strptime(expire_str, "%Y-%m-%d").date()
        today = date.today()
        days_left = (exp_date - today).days
        if days_left < 0:
            return {
                "valid": False,
                "status": "EXPIRED",
                "message": f"ใบอนุญาตหมดอายุแล้ว (หมดอายุเมื่อ: {expire_str})",
                "customer": customer,
                "expire_date": expire_str,
                "days_left": days_left,
                "current_machine": current_machine_id,
                "contact_email": CONTACT_EMAIL
            }
    except Exception:
        return {
            "valid": False,
            "status": "INVALID_EXPIRY",
            "message": "รูปแบบวันหมดอายุในใบอนุญาตไม่ถูกต้อง",
            "current_machine": current_machine_id,
            "contact_email": CONTACT_EMAIL
        }

    # 4. Check Machine Hardware ID Authorization
    if current_machine_id not in allowed_machines:
        if len(allowed_machines) >= max_machines:
            return {
                "valid": False,
                "status": "MACHINE_LIMIT_REACHED",
                "message": f"สิทธิ์นี้ลงทะเบียนใช้งานครบกำหนด {max_machines} เครื่องแล้ว ไม่สามารถใช้กับเครื่องนี้ได้",
                "customer": customer,
                "expire_date": expire_str,
                "max_machines": max_machines,
                "registered_count": len(allowed_machines),
                "current_machine": current_machine_id,
                "contact_email": CONTACT_EMAIL
            }
        else:
            return {
                "valid": False,
                "status": "UNAUTHORIZED_MACHINE",
                "message": f"เครื่องนี้ยังไม่ได้รับการอนุมัติ (ใช้ไปแล้ว {len(allowed_machines)}/{max_machines} เครื่อง)",
                "customer": customer,
                "expire_date": expire_str,
                "max_machines": max_machines,
                "registered_count": len(allowed_machines),
                "current_machine": current_machine_id,
                "contact_email": CONTACT_EMAIL
            }

    # Machine index (1-based)
    machine_index = allowed_machines.index(current_machine_id) + 1

    return {
        "valid": True,
        "status": "ACTIVE",
        "message": "ใบอนุญาตใช้งานถูกต้อง",
        "customer": customer,
        "expire_date": expire_str,
        "days_left": days_left,
        "max_machines": max_machines,
        "machine_slot": machine_index,
        "total_active_machines": len(allowed_machines),
        "current_machine": current_machine_id,
        "issued_at": issued_at,
        "contact_email": CONTACT_EMAIL
    }


def get_license_file_path() -> str:
    from backend.storage import DATA_DIR
    return os.path.join(DATA_DIR, "license.key")


def get_current_license_status() -> Dict[str, Any]:
    """Reads license file from disk and checks validity."""
    lic_file = get_license_file_path()
    if not os.path.exists(lic_file):
        return {
            "valid": False,
            "status": "NO_LICENSE",
            "message": "ยังไม่ได้เปิดใช้งานใบอนุญาตบนเครื่องนี้",
            "current_machine": get_machine_id(),
            "contact_email": CONTACT_EMAIL
        }

    try:
        with open(lic_file, "r", encoding="utf-8") as f:
            lic_str = f.read().strip()
        return verify_license_string(lic_str)
    except Exception as e:
        return {
            "valid": False,
            "status": "FILE_READ_ERROR",
            "message": f"ไม่สามารถอ่านไฟล์ใบอนุญาตได้: {e}",
            "current_machine": get_machine_id(),
            "contact_email": CONTACT_EMAIL
        }


def save_and_activate_license(license_key_str: str) -> Dict[str, Any]:
    """Validates and saves the license key to data/license.key."""
    check_result = verify_license_string(license_key_str)
    if not check_result.get("valid"):
        return check_result

    lic_file = get_license_file_path()
    try:
        with open(lic_file, "w", encoding="utf-8") as f:
            f.write(license_key_str.strip())
        check_result["saved"] = True
        check_result["message"] = "เปิดใช้งานใบอนุญาตสำเร็จเรียบร้อยแล้ว!"
        return check_result
    except Exception as e:
        return {
            "valid": False,
            "status": "SAVE_ERROR",
            "message": f"เกิดข้อผิดพลาดในการบันทึกไฟล์ใบอนุญาต: {e}",
            "current_machine": get_machine_id(),
            "contact_email": CONTACT_EMAIL
        }
