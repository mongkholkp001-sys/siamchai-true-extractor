import os
import time
import socket
import asyncio
import threading
from typing import List, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends, UploadFile, File, Response, Request
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.storage import (
    BUNDLE_DIR, BASE_DIR, DATA_DIR, RESULTS_DIR, load_config, save_config,
    parse_excel_cids, parse_cids_from_text,
    load_users, save_users, get_user, add_user, update_user_password, delete_user,
    reset_user_devices, update_user_details
)
from backend.auth import (
    authenticate_user, create_session_token, get_current_user,
    get_current_user_info, require_admin, COOKIE_NAME,
    verify_session_token
)
import requests
from backend.unified_engine import job_manager, UnifiedJobState
from backend.license_manager import (
    get_machine_id,
    get_current_license_status,
    save_and_activate_license,
    generate_license_key,
    CONTACT_EMAIL,
    CENTRAL_SERVER_URL,
    check_customer_quota,
    check_user_quota,
    create_approval_token,
    verify_approval_token,
    record_approval,
    get_online_activation
)

app = FastAPI(title="Siamchai & TrueCorp Unified Extractor")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_no_cache_headers(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/static") or request.url.path in ["/", "/login"]:
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response

STATIC_DIR = os.path.join(BUNDLE_DIR, "static")
os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

active_websockets: List[WebSocket] = []

def get_lan_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

# ------------------ Request Models ------------------
class LoginRequest(BaseModel):
    username: str
    password: str
    device_id: Optional[str] = ""

class StartRequest(BaseModel):
    cids: List[str]
    mode: str = "both" # "both", "siamchai", "true"
    job_name: str = "unified_search"
    headless: bool = True

class StopRequest(BaseModel):
    job_id: Optional[str] = None

class JobResetRequest(BaseModel):
    job_id: Optional[str] = None
    user: Optional[str] = None

class ConfigUpdateRequest(BaseModel):
    web_username: Optional[str] = None
    web_password: Optional[str] = None
    siamchai_username: Optional[str] = None
    siamchai_password: Optional[str] = None
    true_username: Optional[str] = None
    true_password: Optional[str] = None
    headless: Optional[bool] = None

class CreateUserRequest(BaseModel):
    username: str
    password: str
    role: str = "member"
    name: Optional[str] = ""
    expire_date: Optional[str] = ""
    max_devices: Optional[int] = 2

class UpdateUserRequest(BaseModel):
    name: Optional[str] = None
    expire_date: Optional[str] = None
    max_devices: Optional[int] = None

class ResetPasswordRequest(BaseModel):
    password: str

class LicenseActivateRequest(BaseModel):
    license_key: str

class LicenseGenerateRequest(BaseModel):
    customer: str
    expire_date: str # YYYY-MM-DD
    machines: List[str]
    max_machines: Optional[int] = 3

class LicenseEmailRequest(BaseModel):
    username: str
    password: str
    customer_name: Optional[str] = ""
    phone: Optional[str] = ""
    email: Optional[str] = ""
    machine_id: str
    note: Optional[str] = ""

def find_static_file(filename: str) -> Optional[str]:
    candidates = [
        os.path.join(STATIC_DIR, filename),
        os.path.join(BUNDLE_DIR, "static", filename),
        os.path.join(BASE_DIR, "static", filename),
        os.path.join(r"C:\Siamchai_True_Hub", "static", filename),
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", filename),
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return None

# ------------------ Page Routes ------------------
@app.get("/", response_class=HTMLResponse)
async def serve_index(request: Request):
    # Check if user is logged in
    token = request.cookies.get(COOKIE_NAME)
    is_authenticated = False
    if token:
        try:
            verify_session_token(token)
            is_authenticated = True
        except Exception:
            pass

    # If license is not active on this machine or user wants to activate, allow index.html to show activation modal directly
    lic_status = get_current_license_status()
    if not lic_status.get("valid") or request.query_params.get("activate") == "1":
        index_path = find_static_file("index.html")
        if index_path and os.path.exists(index_path):
            with open(index_path, "r", encoding="utf-8") as f:
                return HTMLResponse(content=f.read())

    if not is_authenticated:
        return HTMLResponse("<script>window.location.href='/login';</script>")

    index_path = find_static_file("index.html")
    if index_path and os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("<h1>Unified Extractor Ready</h1>")

@app.get("/login", response_class=HTMLResponse)
async def serve_login():
    login_path = find_static_file("login.html")
    if login_path and os.path.exists(login_path):
        with open(login_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("<h1>Login Page Missing</h1>")

# ------------------ Auth API Endpoints ------------------
@app.post("/api/auth/login")
async def api_login(req: LoginRequest, request: Request, response: Response):
    client_ip = request.client.host if request.client else ""
    auth_result = authenticate_user(req.username, req.password, device_id=req.device_id, client_ip=client_ip)
    
    token = create_session_token(auth_result["username"])
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=False,
        max_age=30 * 86400,
        samesite="lax"
    )
    user_info = get_user(auth_result["username"]) or {}
    return {
        "status": "ok",
        "token": token,
        "username": auth_result["username"],
        "role": auth_result.get("role", "member"),
        "name": auth_result.get("name", auth_result["username"]),
        "expire_date": user_info.get("expire_date", ""),
        "devices_count": len(user_info.get("devices", [])),
        "max_devices": user_info.get("max_devices", 2)
    }

@app.post("/api/auth/logout")
async def api_logout(response: Response):
    response.delete_cookie(key=COOKIE_NAME)
    return {"status": "ok"}

@app.get("/api/auth/me")
async def api_me(user_info: dict = Depends(get_current_user_info)):
    u = get_user(user_info["username"]) or {}
    return {
        "status": "ok",
        **user_info,
        "expire_date": u.get("expire_date", ""),
        "devices": u.get("devices", []),
        "max_devices": u.get("max_devices", 2)
    }

# ------------------ User Management Endpoints (Admin Only) ------------------
@app.get("/api/users")
async def list_users(admin: dict = Depends(require_admin)):
    users = load_users()
    safe_users = [
        {
            "username": u["username"],
            "role": u.get("role", "member"),
            "name": u.get("name", u["username"]),
            "expire_date": u.get("expire_date", ""),
            "max_devices": u.get("max_devices", 2),
            "devices_count": len(u.get("devices", [])),
            "devices": u.get("devices", []),
            "created_at": u.get("created_at")
        }
        for u in users
    ]
    return {"status": "ok", "users": safe_users}

@app.post("/api/users")
async def create_new_user(req: CreateUserRequest, admin: dict = Depends(require_admin)):
    try:
        new_u = add_user(
            req.username, 
            req.password, 
            role=req.role, 
            name=req.name or "",
            expire_date=req.expire_date or "",
            max_devices=req.max_devices or 2
        )
        return {
            "status": "ok",
            "user": {
                "username": new_u["username"],
                "role": new_u["role"],
                "name": new_u["name"],
                "expire_date": new_u.get("expire_date", ""),
                "max_devices": new_u.get("max_devices", 2),
                "created_at": new_u["created_at"]
            }
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.put("/api/users/{username}")
async def edit_user(username: str, req: UpdateUserRequest, admin: dict = Depends(require_admin)):
    ok = update_user_details(username, name=req.name, expire_date=req.expire_date, max_devices=req.max_devices)
    if not ok:
        raise HTTPException(status_code=404, detail=f"ไม่พบผู้ใช้ '{username}'")
    return {"status": "ok", "message": f"อัปเดตข้อมูลผู้ใช้ '{username}' สำเร็จ"}

@app.post("/api/users/{username}/reset-devices")
async def reset_devices(username: str, admin: dict = Depends(require_admin)):
    ok = reset_user_devices(username)
    if not ok:
        raise HTTPException(status_code=404, detail=f"ไม่พบผู้ใช้ '{username}'")
    return {"status": "ok", "message": f"รีเซ็ตสิทธิ์อุปกรณ์สำหรับผู้ใช้ '{username}' เรียบร้อยแล้ว (สามารถผูกเครื่องใหม่ได้)"}

@app.put("/api/users/{username}/password")
async def change_user_password(username: str, req: ResetPasswordRequest, admin: dict = Depends(require_admin)):
    try:
        update_user_password(username, req.password)
        return {"status": "ok", "message": f"เปลี่ยนรหัสผ่านสำหรับผู้ใช้ '{username}' สำเร็จ"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.delete("/api/users/{username}")
async def remove_existing_user(username: str, admin: dict = Depends(require_admin)):
    try:
        delete_user(username, current_admin=admin["username"])
        return {"status": "ok", "message": f"ลบผู้ใช้ '{username}' สำเร็จ"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

# ------------------ Process & Control Endpoints ------------------
@app.get("/api/license/status")
async def api_license_status():
    """Returns license status, current machine ID, and contact details."""
    return get_current_license_status()

@app.get("/api/license/check-user-quota")
async def api_license_check_user_quota(u: str, p: str, mch: str, request: Request):
    """
    Checks user credentials and quota against central or local DB.
    """
    clean_u = (u or "").strip().lower()
    clean_p = (p or "").strip()
    clean_mch = (mch or "").strip().upper()

    host_hdr = (request.headers.get("host") or "").lower()
    is_central = (
        "119.10.137.52" in host_hdr
        or "119.10.137.52" in get_lan_ip()
        or os.path.exists("/root/siamchai-true-extractor")
        or os.environ.get("IS_CENTRAL_SERVER") == "1"
        or CENTRAL_SERVER_URL.lower().rstrip('/') in str(request.url).lower()
    )
    if not is_central:
        try:
            params = {"u": clean_u, "p": clean_p, "mch": clean_mch}
            r = requests.get(f"{CENTRAL_SERVER_URL}/api/license/check-user-quota", params=params, timeout=5)
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass

    return check_user_quota(clean_u, clean_p, clean_mch)

@app.post("/api/license/request")
async def api_license_request_email(req: LicenseEmailRequest, request: Request):
    """
    Sends activation request with customer info, User credentials, Machine ID, quota status,
    and 1-Click Approval Links directly to mongkholkp001@gmail.com.
    """
    from datetime import datetime
    import urllib.parse
    import base64
    clean_u = (req.username or "").strip().lower()
    clean_p = (req.password or "").strip()
    clean_machine = (req.machine_id or "").strip() or get_machine_id()
    cust_name = (req.customer_name or "").strip() or clean_u
    cust_encoded = urllib.parse.quote(cust_name)
    phone = (req.phone or "").strip() or "-"

    if not clean_u or len(clean_u) < 3:
        raise HTTPException(status_code=400, detail="กรุณาระบุชื่อผู้ใช้ (Username) อย่างน้อย 3 ตัวอักษร")
    if not clean_p or len(clean_p) < 4:
        raise HTTPException(status_code=400, detail="กรุณากำหนดรหัสผ่าน (Password) อย่างน้อย 4 ตัวอักษร")

    # Check credentials & 3-machine quota status (query central VPS if local)
    quota = None
    host_hdr = (request.headers.get("host") or "").lower()
    is_central = (
        "119.10.137.52" in host_hdr
        or "119.10.137.52" in get_lan_ip()
        or os.path.exists("/root/siamchai-true-extractor")
        or os.environ.get("IS_CENTRAL_SERVER") == "1"
        or CENTRAL_SERVER_URL.lower().rstrip('/') in str(request.url).lower()
    )
    if not is_central:
        try:
            params = {"u": clean_u, "p": clean_p, "mch": clean_machine}
            r = requests.get(f"{CENTRAL_SERVER_URL}/api/license/check-user-quota", params=params, timeout=5)
            if r.status_code == 200:
                quota = r.json()
        except Exception:
            pass

    if not quota:
        quota = check_user_quota(clean_u, clean_p, clean_machine)

    if not quota.get("ok"):
        raise HTTPException(status_code=400, detail=quota.get("error", "การตรวจสอบชื่อผู้ใช้และรหัสผ่านไม่ผ่าน"))

    is_new = quota.get("is_new", True)
    user_status_label = "บัญชีผู้ใช้ใหม่ (เพิ่งลงทะเบียน)" if is_new else "บัญชีเดิมที่มีอยู่แล้ว"
    quota_desc = f"เครื่องที่ {quota['slot_for_this_machine']} จากทั้งหมด {quota['max_machines']} เครื่อง (ปัจจุบันผูกแล้ว {quota['machine_count']} เครื่อง)"
    if quota.get("quota_exceeded"):
        quota_desc = f"⚠️ แจ้งเตือน: ผู้ใช้ '{clean_u}' ใช้โควต้าครบ {quota['max_machines']} เครื่องแล้ว! (เครื่องเดิม: {', '.join(quota.get('current_machines', []))})"

    # Encode password for approval link
    pwd_b64 = base64.urlsafe_b64encode(clean_p.encode("utf-8")).decode("ascii")

    # Generate 1-Click approval links for Admin
    t30 = create_approval_token(clean_machine, 30, clean_u)
    t60 = create_approval_token(clean_machine, 60, clean_u)
    t90 = create_approval_token(clean_machine, 90, clean_u)
    t365 = create_approval_token(clean_machine, 365, clean_u)

    base_link = f"{CENTRAL_SERVER_URL}/api/license/approve?mch={clean_machine}&user={clean_u}&name={cust_encoded}&phone={phone}&pwd={pwd_b64}"
    link_30 = f"{base_link}&days=30&token={t30}"
    link_60 = f"{base_link}&days=60&token={t60}"
    link_90 = f"{base_link}&days=90&token={t90}"
    link_365 = f"{base_link}&days=365&token={t365}"

    payload = {
        "_subject": f"[Customer Data Hub] ขอเปิดใช้งาน: User {clean_u} ({quota_desc})",
        "_template": "table",
        "1. ชื่อผู้ใช้ (Username)": clean_u,
        "2. ประเภทบัญชี": user_status_label,
        "3. ชื่อลูกค้า / บริษัท": cust_name,
        "4. เบอร์โทรติดต่อ": phone,
        "5. รหัสประจำเครื่อง (Machine ID)": clean_machine,
        "6. ลำดับโควต้าเครื่อง": quota_desc,
        "7. วันเวลาที่ส่งคำขอ": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "👉 [คลิกอนุมัติ 30 วัน (1 เดือน)]": link_30,
        "👉 [คลิกอนุมัติ 60 วัน (2 เดือน)]": link_60,
        "👉 [คลิกอนุมัติ 90 วัน (3 เดือน)]": link_90,
        "👉 [คลิกอนุมัติ 1 ปี (365 วัน)]": link_365
    }

    try:
        res = requests.post(
            f"https://formsubmit.co/ajax/{CONTACT_EMAIL}",
            json=payload,
            headers={
                "Accept": "application/json",
                "Origin": "http://localhost:8088",
                "Referer": "http://localhost:8088/"
            },
            timeout=12
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ส่งอีเมลไม่สำเร็จ: {e}")

    return {
        "status": "ok", 
        "message": f"ระบบได้ส่งคำขอพร้อมรหัสเครื่องนี้ไปยังอีเมล {CONTACT_EMAIL} เรียบร้อยแล้ว! (ผู้ดูแลระบบสามารถกดอนุมัติในอีเมลได้ทันที)",
        "username": clean_u,
        "machine_id": clean_machine,
        "quota": quota
    }

@app.get("/api/license/approve", response_class=HTMLResponse)
async def api_license_approve(
    mch: str,
    days: int,
    token: str,
    user: Optional[str] = "",
    name: Optional[str] = "",
    phone: Optional[str] = "",
    pwd: Optional[str] = "",
    force: Optional[int] = 0
):
    """
    1-Click Email Approval Endpoint.
    Admin clicks link in Gmail, which calls this endpoint on the Central Server (119.10.137.52:8000).
    """
    import urllib.parse
    import base64
    clean_u = (user or name or "ลูกค้า").strip().lower()
    clean_name = urllib.parse.unquote(name or user or "ลูกค้า")
    clean_mch = mch.strip().upper()
    raw_pwd = ""
    if pwd:
        try:
            raw_pwd = base64.urlsafe_b64decode(pwd.encode("ascii")).decode("utf-8")
        except Exception:
            raw_pwd = pwd

    # 1. Verify Token (supports both clean_u and clean_name)
    is_valid_tok = verify_approval_token(clean_mch, days, clean_u, token) or verify_approval_token(clean_mch, days, clean_name, token)
    if not is_valid_tok:
        return HTMLResponse(
            f"""
            <!DOCTYPE html>
            <html lang="th">
            <head><meta charset="utf-8"><title>ข้อผิดพลาดการอนุมัติ</title><meta name="viewport" content="width=device-width, initial-scale=1"></head>
            <body style="font-family: sans-serif; background: #0f172a; color: #fff; padding: 2rem; display: flex; justify-content: center; align-items: center; min-height: 80vh;">
                <div style="background: #1e293b; border: 1px solid #ef4444; border-radius: 1rem; padding: 2rem; max-width: 500px; text-align: center;">
                    <h2 style="color: #ef4444; margin-top: 0;">❌ ลิงก์อนุมัติไม่ถูกต้องหรือหมดอายุ</h2>
                    <p style="color: #94a3b8;">รหัสความปลอดภัย (Security Token) ไม่ตรงกับคำขอ กรุณาตรวจสอบอีเมลล่าสุดอีกครั้ง</p>
                </div>
            </body>
            </html>
            """,
            status_code=403
        )

    # 2. Record Approval and enforce max 3 machines (role is set to 'member')
    res = record_approval(
        customer_name=clean_name,
        machine_id=clean_mch,
        days=days,
        phone=phone,
        password=raw_pwd,
        username=clean_u,
        force_add=(force == 1)
    )
    if not res.get("ok"):
        # Quota exceeded prompt
        force_url = f"/api/license/approve?mch={clean_mch}&days={days}&user={clean_u}&name={urllib.parse.quote(clean_name)}&phone={phone}&pwd={pwd}&token={token}&force=1"
        return HTMLResponse(
            f"""
            <!DOCTYPE html>
            <html lang="th">
            <head><meta charset="utf-8"><title>โควต้าเครื่องเต็ม</title><meta name="viewport" content="width=device-width, initial-scale=1"></head>
            <body style="font-family: sans-serif; background: #0f172a; color: #fff; padding: 2rem; display: flex; justify-content: center; align-items: center; min-height: 80vh;">
                <div style="background: #1e293b; border: 1px solid #f59e0b; border-radius: 1rem; padding: 2rem; max-width: 540px;">
                    <h2 style="color: #f59e0b; margin-top: 0;">⚠️ ผู้ใช้ '{clean_u}' ใช้โควต้าครบ 3 เครื่องแล้ว!</h2>
                    <p style="color: #cbd5e1;">ชื่อผู้ใช้: <b>{clean_u}</b> ({clean_name})</p>
                    <p style="color: #cbd5e1;">รหัสเครื่องใหม่นี้: <code>{clean_mch}</code></p>
                    <p style="color: #fca5a5; font-size: 0.9rem;">{res.get('error')}</p>
                    <hr style="border: 0; border-top: 1px solid #334155; margin: 1.5rem 0;">
                    <p style="color: #94a3b8; font-size: 0.85rem;">หากคุณต้องการยืนยันอนุมัติเป็นกรณีพิเศษ (เพิ่มเครื่องนี้ให้ผู้ใช้รายนี้) ให้กดปุ่มด้านล่าง:</p>
                    <a href="{force_url}" style="display: block; text-align: center; background: #f59e0b; color: #000; padding: 0.75rem 1rem; border-radius: 0.5rem; text-decoration: none; font-weight: bold; margin-top: 1rem;">
                        ⚠️ ยืนยันอนุมัติพิเศษ (เพิ่มเครื่องนี้)
                    </a>
                </div>
            </body>
            </html>
            """
        )

    # Success HTML Page
    slot_num = res["machine_slot"]
    total_mch = res["total_machines"]
    max_mch = res["max_machines"]
    exp_date = res["expire_date"]

    return HTMLResponse(
        f"""
        <!DOCTYPE html>
        <html lang="th">
        <head>
            <meta charset="utf-8">
            <title>อนุมัติสิทธิ์สำเร็จ - Customer Data Hub</title>
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <link href="https://fonts.googleapis.com/css2?family=Prompt:wght@400;600;700&family=JetBrains+Mono:wght@500&display=swap" rel="stylesheet">
            <style>
                body {{ font-family: 'Prompt', sans-serif; background: radial-gradient(circle at 10% 10%, #0f172a 0%, #090d16 100%); color: #f8fafc; padding: 1.5rem; display: flex; justify-content: center; align-items: center; min-height: 90vh; margin: 0; }}
                .card {{ background: rgba(30, 41, 59, 0.85); backdrop-filter: blur(12px); border: 1px solid rgba(16, 185, 129, 0.4); border-radius: 1.25rem; padding: 2.25rem; max-width: 520px; width: 100%; box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5); }}
                .badge {{ display: inline-block; background: rgba(16, 185, 129, 0.15); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.3); border-radius: 9999px; padding: 0.25rem 0.75rem; font-size: 0.75rem; font-weight: 600; margin-bottom: 1rem; }}
                .title {{ font-size: 1.5rem; font-weight: 700; color: #fff; margin: 0 0 0.5rem 0; display: flex; align-items: center; gap: 0.5rem; }}
                .subtitle {{ color: #94a3b8; font-size: 0.875rem; margin: 0 0 1.5rem 0; }}
                .row {{ display: flex; justify-content: space-between; padding: 0.65rem 0; border-bottom: 1px solid rgba(255, 255, 255, 0.08); font-size: 0.875rem; }}
                .label {{ color: #94a3b8; }}
                .val {{ font-weight: 600; color: #f1f5f9; }}
                .code {{ font-family: 'JetBrains Mono', monospace; color: #38bdf8; font-size: 0.85rem; }}
                .quota-box {{ background: rgba(15, 23, 42, 0.8); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 0.75rem; padding: 1rem; margin-top: 1.25rem; font-size: 0.85rem; text-align: center; color: #cbd5e1; }}
                .footer-notice {{ margin-top: 1.5rem; text-align: center; color: #10b981; font-size: 0.875rem; font-weight: 600; }}
            </style>
        </head>
        <body>
            <div class="card">
                <span class="badge">● ระบบอนุมัติสิทธิ์และสร้างบัญชีอัตโนมัติ</span>
                <h1 class="title">🎉 อนุมัติสิทธิ์สำเร็จ!</h1>
                <p class="subtitle">ระบบได้เปิดสิทธิ์และสร้างบัญชีผู้ใช้ (Member) เรียบร้อยแล้ว</p>

                <div class="row"><span class="label">ชื่อผู้ใช้ (Username):</span><span class="val" style="color: #38bdf8;">{clean_u}</span></div>
                <div class="row"><span class="label">ชื่อลูกค้า / บริษัท:</span><span class="val">{clean_name}</span></div>
                <div class="row"><span class="label">สิทธิ์การใช้งาน:</span><span class="val" style="color: #a78bfa;">User (Member) ทั่วไป</span></div>
                <div class="row"><span class="label">ระยะเวลาที่อนุมัติ:</span><span class="val" style="color: #34d399;">{days} วัน</span></div>
                <div class="row"><span class="label">ใช้งานได้ถึงวันที่:</span><span class="val" style="color: #38bdf8;">{exp_date}</span></div>
                <div class="row"><span class="label">รหัสเครื่องที่อนุมัติ:</span><span class="val code">{clean_mch}</span></div>
                <div class="row"><span class="label">ลำดับโควต้าเครื่อง:</span><span class="val" style="color: #fbbf24;">เครื่องที่ {slot_num} จากทั้งหมด {max_mch} เครื่อง (ผูกแล้ว {total_mch}/{max_mch})</span></div>

                <div class="quota-box">
                    💻 <b>สถานะโควต้า</b>: ผู้ใช้ <b>{clean_u}</b> ได้รับอนุมัติเครื่องนี้เรียบร้อยแล้ว<br>
                    เครื่องของลูกค้าจะปลดล็อกและเริ่มใช้งานได้โดยอัตโนมัติทันที โดยมีสิทธิ์เป็น User ทั่วไป (ไม่เห็นเมนูแอดมิน) ครับ
                </div>

                <div class="footer-notice">
                    ✅ ดำเนินการเสร็จสมบูรณ์ คุณสามารถปิดหน้านี้ได้เลยครับ
                </div>
            </div>
        </body>
        </html>
        """
    )

@app.get("/api/license/check-online")
async def api_license_check_online(mch: str, request: Request, response: Response):
    """
    Called by client machines (localhost:8088) to check if admin approved their machine.
    Queries local DB first; if not found, queries the Central VPS Server (119.10.137.52:8000).
    If approved, automatically saves license locally, sets member session cookie, and unlocks!
    """
    clean_mch = mch.strip().upper()
    
    # 1. Check local DB first
    local_rec = get_online_activation(clean_mch)
    if local_rec.get("approved"):
        username = local_rec.get("username", "member")
        try:
            token = create_session_token(username)
            response.set_cookie(key=COOKIE_NAME, value=token, max_age=30*86400, httponly=True, samesite="lax")
            local_rec["auth_token"] = token
        except Exception:
            pass
        return local_rec

    # 2. Only query Central Server if we are NOT on the Central Server itself!
    host_hdr = (request.headers.get("host") or "").lower()
    is_central = (
        "119.10.137.52" in host_hdr
        or "119.10.137.52" in get_lan_ip()
        or os.path.exists("/root/siamchai-true-extractor")
        or os.environ.get("IS_CENTRAL_SERVER") == "1"
        or CENTRAL_SERVER_URL.lower().rstrip('/') in str(request.url).lower()
    )
    if not is_central:
        try:
            r = requests.get(f"{CENTRAL_SERVER_URL}/api/license/check-online?mch={clean_mch}", timeout=3)
            if r.status_code == 200:
                data = r.json()
                if data.get("approved") and data.get("license_key"):
                    save_and_activate_license(data["license_key"])
                    username = data.get("username", "member")
                    try:
                        token = create_session_token(username)
                        response.set_cookie(key=COOKIE_NAME, value=token, max_age=30*86400, httponly=True, samesite="lax")
                        data["auth_token"] = token
                    except Exception:
                        pass
                    return data
        except Exception:
            pass

    return {"approved": False, "machine_id": clean_mch}

@app.post("/api/license/activate")
async def api_license_activate(req: LicenseActivateRequest):
    """Activates the system using provided license key."""
    res = save_and_activate_license(req.license_key)
    if not res.get("valid"):
        raise HTTPException(status_code=400, detail=res.get("message", "รหัสเปิดใช้งานไม่ถูกต้อง"))
    return res

@app.post("/api/license/generate")
async def api_license_generate(req: LicenseGenerateRequest, admin: dict = Depends(require_admin)):
    """Admin endpoint to generate a license key directly from dashboard."""
    key = generate_license_key(
        customer=req.customer,
        expire_date=req.expire_date,
        machines=req.machines,
        max_machines=req.max_machines or 3
    )
    return {
        "status": "ok",
        "license_key": key,
        "customer": req.customer,
        "expire_date": req.expire_date,
        "machines": req.machines
    }

@app.get("/api/status")
async def get_status(job_id: Optional[str] = None, user: str = Depends(get_current_user)):
    if job_id:
        job = job_manager.get_job_by_id(job_id)
        if job:
            return job.to_dict()
    job = job_manager.get_user_current_job(user)
    return job.to_dict()

@app.post("/api/start")
async def start_crawl(req: StartRequest, user: str = Depends(get_current_user)):
    # Verify Machine Hardware ID and License validity before running
    lic = get_current_license_status()
    if not lic.get("valid"):
        raise HTTPException(
            status_code=403, 
            detail=lic.get("message", "ระบบยังไม่ได้รับการเปิดใช้งาน หรือใบอนุญาตหมดอายุ กรุณาเปิดใช้งานก่อนเริ่มค้นหา")
        )

    if not req.cids:
        raise HTTPException(status_code=400, detail="กรุณาระบุเลขค้นหาอย่างน้อย 1 รายการ")

    try:
        job = job_manager.submit_job(
            user=user,
            cids=req.cids,
            mode=req.mode,
            job_name=req.job_name,
            headless=req.headless
        )
        return {
            "status": "started",
            "job_id": job.job_id,
            "total": len(req.cids),
            "mode": req.mode
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/stop")
async def stop_crawl(
    req: Optional[StopRequest] = None,
    job_id: Optional[str] = None,
    user: str = Depends(get_current_user)
):
    target_id = None
    if req and req.job_id:
        target_id = req.job_id
    elif job_id:
        target_id = job_id

    stopped = job_manager.stop_job(user=user, job_id=target_id)
    if stopped:
        return {"status": "stopping", "job_id": target_id}
    return {"status": "not_running_or_not_found"}

@app.post("/api/job/reset")
async def reset_single_job(
    req: Optional[JobResetRequest] = None,
    user: str = Depends(get_current_user)
):
    target_user = (req.user if req and req.user else user)
    target_job_id = (req.job_id if req and req.job_id else None)
    
    # Regular users can only reset their own jobs, Admin can reset any user's job
    if user.strip().lower() != "admin" and target_user.strip().lower() != user.strip().lower():
        raise HTTPException(status_code=403, detail="คุณสามารถรีเซ็ตเฉพาะงานของตนเองได้")

    cnt = job_manager.reset_user_job(user=target_user, job_id=target_job_id)
    return {
        "status": "ok",
        "message": f"รีเซ็ตและปลดล็อคสถานะงานสำเร็จ ({cnt} งาน)",
        "reset_count": cnt
    }

@app.post("/api/admin/reset-system")
async def admin_reset_system(admin: dict = Depends(require_admin)):
    cnt = job_manager.force_reset_all(admin_user=admin.get("username", "admin"))
    return {
        "status": "ok", 
        "message": f"รีเซ็ตระบบและสั่งหยุดงานที่ค้างสำเร็จ ({cnt} งาน)",
        "stopped_count": cnt
    }

@app.get("/api/jobs")
async def get_jobs_history(user: str = Depends(get_current_user)):
    history = job_manager.get_user_jobs_history(user=user)
    return {"status": "ok", "jobs": history}

# ------------------ Upload & Download ------------------
@app.post("/api/upload_excel")
async def upload_excel(file: UploadFile = File(...), user: str = Depends(get_current_user)):
    ext = os.path.splitext(file.filename)[1].lower()
    temp_path = os.path.join(DATA_DIR, f"upload_{int(time.time())}{ext}")
    with open(temp_path, "wb") as f:
        content = await file.read()
        f.write(content)

    cids = parse_excel_cids(temp_path)
    try:
        os.remove(temp_path)
    except Exception:
        pass

    if not cids:
        raise HTTPException(status_code=400, detail="ไม่พบเลขบัตรประชาชนในคอลัมน์แรกของไฟล์")

    return {
        "status": "ok",
        "filename": file.filename,
        "count": len(cids),
        "cids": cids[:5000],
        "preview": cids[:10]
    }

@app.get("/api/download")
async def download_excel(
    type: str = "combined",
    job_id: Optional[str] = None,
    token: Optional[str] = None,
    request: Request = None
):
    # Verify token from query or cookie
    auth_t = token or (request.cookies.get(COOKIE_NAME) if request else None)
    current_username = "admin"
    if auth_t:
        try:
            current_username = verify_session_token(auth_t)
        except Exception:
            raise HTTPException(status_code=401, detail="Unauthorized")

    target_job = None
    if job_id:
        target_job = job_manager.get_job_by_id(job_id)
    if not target_job:
        target_job = job_manager.get_user_current_job(current_username)

    target_path = None
    if type == "siamchai":
        target_path = target_job.sc_excel_path
    elif type == "true":
        target_path = target_job.tr_excel_path
    else: # combined
        target_path = target_job.combined_excel_path or target_job.sc_excel_path or target_job.tr_excel_path

    if not target_path or not os.path.exists(target_path):
        raise HTTPException(status_code=404, detail="ยังไม่มีไฟล์ Excel ให้ดาวน์โหลดสำหรับส่วนนี้")

    return FileResponse(
        path=target_path,
        filename=os.path.basename(target_path),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

@app.get("/api/download/siamchai")
async def download_siamchai_excel(job_id: Optional[str] = None, token: Optional[str] = None, request: Request = None):
    return await download_excel(type="siamchai", job_id=job_id, token=token, request=request)

@app.get("/api/download/true")
async def download_true_excel(job_id: Optional[str] = None, token: Optional[str] = None, request: Request = None):
    return await download_excel(type="true", job_id=job_id, token=token, request=request)

@app.get("/api/download/combined")
async def download_combined_excel(job_id: Optional[str] = None, token: Optional[str] = None, request: Request = None):
    return await download_excel(type="combined", job_id=job_id, token=token, request=request)

# ------------------ Config Endpoints ------------------
@app.get("/api/config")
async def get_config_endpoint(admin: dict = Depends(require_admin)):
    cfg = load_config()
    # Mask passwords
    masked = cfg.copy()
    if masked.get("web_password"):
        masked["web_password"] = "••••••••"
    if masked.get("siamchai_password"):
        masked["siamchai_password"] = "••••••••"
    if masked.get("true_password"):
        masked["true_password"] = "••••••••"
    return masked

@app.post("/api/config")
async def update_config_endpoint(req: ConfigUpdateRequest, admin: dict = Depends(require_admin)):
    cfg = load_config()
    if req.web_username is not None and req.web_username.strip():
        cfg["web_username"] = req.web_username.strip()
    if req.web_password is not None and req.web_password.strip() and "••••" not in req.web_password:
        cfg["web_password"] = req.web_password.strip()

    if req.siamchai_username is not None:
        cfg["siamchai_username"] = req.siamchai_username.strip()
    if req.siamchai_password is not None and "••••" not in req.siamchai_password:
        cfg["siamchai_password"] = req.siamchai_password.strip()

    if req.true_username is not None:
        cfg["true_username"] = req.true_username.strip()
    if req.true_password is not None and "••••" not in req.true_password:
        cfg["true_password"] = req.true_password.strip()

    if req.headless is not None:
        cfg["headless"] = req.headless

    save_config(cfg)
    return {"status": "ok"}

# ------------------ WebSocket ------------------
@app.websocket("/ws/status")
async def websocket_status(websocket: WebSocket, token: Optional[str] = None, job_id: Optional[str] = None):
    await websocket.accept()
    active_websockets.append(websocket)
    user = "admin"
    if token:
        try:
            user = verify_session_token(token)
        except Exception:
            pass
    try:
        while True:
            if job_id:
                job = job_manager.get_job_by_id(job_id)
                if not job:
                    job = job_manager.get_user_current_job(user)
            else:
                job = job_manager.get_user_current_job(user)
            data = job.to_dict()
            await websocket.send_json(data)
            await asyncio.sleep(0.7)
    except (WebSocketDisconnect, Exception):
        pass
    finally:
        if websocket in active_websockets:
            active_websockets.remove(websocket)
