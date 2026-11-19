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


# ==========================================================================
# 🌐 ONLINE ACTIVATION & 1-CLICK EMAIL APPROVAL ENGINE (Max 3 Machines per User)
# ==========================================================================
CENTRAL_SERVER_URL = "http://119.10.137.52:8000"

def get_customers_db_path() -> str:
    from backend.storage import DATA_DIR
    return os.path.join(DATA_DIR, "online_customers.json")

def load_online_customers() -> Dict[str, Any]:
    path = get_customers_db_path()
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
        except Exception:
            pass
    return {}

def save_online_customers(data: Dict[str, Any]) -> bool:
    path = get_customers_db_path()
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception:
        return False

def check_customer_quota(customer_name: str, machine_id: str) -> Dict[str, Any]:
    """
    Checks customer's machine quota (strictly max 3 machines).
    """
    customers = load_online_customers()
    clean_key = customer_name.strip().lower()
    clean_mch = machine_id.strip().upper()

    rec = customers.get(clean_key)
    if not rec:
        return {
            "customer": customer_name.strip(),
            "is_registered": False,
            "current_machines": [],
            "machine_count": 0,
            "max_machines": 3,
            "slot_for_this_machine": 1,
            "quota_exceeded": False
        }

    machines = [m.strip().upper() for m in rec.get("machines", [])]
    max_machines = int(rec.get("max_machines", 3))

    if clean_mch in machines:
        slot = machines.index(clean_mch) + 1
        return {
            "customer": rec.get("customer_name", customer_name),
            "is_registered": True,
            "current_machines": machines,
            "machine_count": len(machines),
            "max_machines": max_machines,
            "slot_for_this_machine": slot,
            "quota_exceeded": False,
            "expire_date": rec.get("expire_date", "")
        }

    quota_exceeded = len(machines) >= max_machines
    return {
        "customer": rec.get("customer_name", customer_name),
        "is_registered": False,
        "current_machines": machines,
        "machine_count": len(machines),
        "max_machines": max_machines,
        "slot_for_this_machine": len(machines) + 1,
        "quota_exceeded": quota_exceeded,
        "expire_date": rec.get("expire_date", "")
    }

def create_approval_token(machine_id: str, days: int, customer_name: str) -> str:
    clean_mch = machine_id.strip().upper()
    clean_cust = customer_name.strip().lower()
    raw = f"{clean_mch}:{days}:{clean_cust}"
    return hmac.new(MASTER_SIGNING_SECRET.encode("utf-8"), raw.encode("utf-8"), hashlib.sha256).hexdigest()[:16]

def verify_approval_token(machine_id: str, days: int, customer_name: str, token: str) -> bool:
    expected = create_approval_token(machine_id, days, customer_name)
    return hmac.compare_digest(token.lower(), expected.lower())

def record_approval(customer_name: str, machine_id: str, days: int, phone: str = "", force_add: bool = False) -> Dict[str, Any]:
    """
    Approves a machine for a customer, binds up to 3 machines, and creates a signed license key.
    """
    from datetime import date, timedelta
    customers = load_online_customers()
    clean_key = customer_name.strip().lower()
    clean_mch = machine_id.strip().upper()

    rec = customers.get(clean_key, {
        "customer_name": customer_name.strip(),
        "phone": phone.strip(),
        "max_machines": 3,
        "machines": [],
        "created_at": date.today().strftime("%Y-%m-%d")
    })

    machines = [m.strip().upper() for m in rec.get("machines", [])]
    max_machines = int(rec.get("max_machines", 3))

    if clean_mch not in machines:
        if len(machines) >= max_machines and not force_add:
            return {
                "ok": False,
                "error": f"ลูกค้ารายนี้ใช้โควต้าครบ {max_machines} เครื่องแล้ว ({', '.join(machines)}) ไม่สามารถลงทะเบียนเครื่องที่ {len(machines)+1} ได้"
            }
        machines.append(clean_mch)

    exp_date = (date.today() + timedelta(days=int(days))).strftime("%Y-%m-%d")
    rec["customer_name"] = customer_name.strip()
    rec["machines"] = machines
    rec["expire_date"] = exp_date
    rec["last_approved"] = date.today().strftime("%Y-%m-%d")
    rec["days_approved"] = int(days)
    if phone:
        rec["phone"] = phone.strip()

    # Generate signed key for these machines
    license_key = generate_license_key(
        customer=rec.get("customer_name", customer_name),
        expire_date=exp_date,
        machines=machines,
        max_machines=max_machines
    )
    rec["license_key"] = license_key

    customers[clean_key] = rec
    save_online_customers(customers)

    return {
        "ok": True,
        "customer": rec["customer_name"],
        "machine_id": clean_mch,
        "machine_slot": machines.index(clean_mch) + 1,
        "max_machines": max_machines,
        "total_machines": len(machines),
        "machines": machines,
        "expire_date": exp_date,
        "days": days,
        "license_key": license_key
    }

def get_online_activation(machine_id: str) -> Dict[str, Any]:
    """Checks if this machine has an approved license in the online database."""
    clean_mch = machine_id.strip().upper()
    customers = load_online_customers()
    today = date.today()

    for key, rec in customers.items():
        machines = [m.strip().upper() for m in rec.get("machines", [])]
        if clean_mch in machines:
            exp_str = rec.get("expire_date", "")
            try:
                exp_d = datetime.strptime(exp_str, "%Y-%m-%d").date()
                days_left = (exp_d - today).days
                if days_left >= 0:
                    return {
                        "approved": True,
                        "customer": rec.get("customer_name", key),
                        "expire_date": exp_str,
                        "days_left": days_left,
                        "machine_id": clean_mch,
                        "machine_slot": machines.index(clean_mch) + 1,
                        "total_machines": len(machines),
                        "max_machines": int(rec.get("max_machines", 3)),
                        "license_key": rec.get("license_key", "")
                    }
            except Exception:
                pass

    return {"approved": False, "machine_id": clean_mch}

