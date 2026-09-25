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
    BASE_DIR, RESULTS_DIR, load_config, save_config,
    parse_excel_cids, parse_cids_from_text,
    load_users, save_users, get_user, add_user, update_user_password, delete_user
)
from backend.auth import (
    authenticate_user, create_session_token, get_current_user,
    get_current_user_info, require_admin, COOKIE_NAME,
    verify_session_token
)
from backend.unified_engine import job_manager, UnifiedJobState

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

STATIC_DIR = os.path.join(BASE_DIR, "static")
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

class StartRequest(BaseModel):
    cids: List[str]
    mode: str = "both" # "both", "siamchai", "true"
    job_name: str = "unified_search"
    headless: bool = True

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

class ResetPasswordRequest(BaseModel):
    password: str

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

    if not is_authenticated:
        return HTMLResponse("<script>window.location.href='/login';</script>")

    index_file = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_file):
        with open(index_file, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("<h1>Unified Extractor Ready</h1>")

@app.get("/login", response_class=HTMLResponse)
async def serve_login():
    login_file = os.path.join(STATIC_DIR, "login.html")
    if os.path.exists(login_file):
        with open(login_file, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("<h1>Login Page Missing</h1>")

# ------------------ Auth API Endpoints ------------------
@app.post("/api/auth/login")
async def api_login(req: LoginRequest, response: Response):
    if not authenticate_user(req.username, req.password):
        raise HTTPException(status_code=401, detail="ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง")
    token = create_session_token(req.username)
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=False,
        max_age=30 * 86400,
        samesite="lax"
    )
    user_info = get_user(req.username) or {}
    return {
        "status": "ok",
        "token": token,
        "username": req.username,
        "role": user_info.get("role", "member" if req.username.lower() != "admin" else "admin"),
        "name": user_info.get("name", req.username)
    }

@app.post("/api/auth/logout")
async def api_logout(response: Response):
    response.delete_cookie(key=COOKIE_NAME)
    return {"status": "ok"}

@app.get("/api/auth/me")
async def api_me(user_info: dict = Depends(get_current_user_info)):
    return {"status": "ok", **user_info}

# ------------------ User Management Endpoints (Admin Only) ------------------
@app.get("/api/users")
async def list_users(admin: dict = Depends(require_admin)):
    users = load_users()
    safe_users = [
        {
            "username": u["username"],
            "role": u.get("role", "member"),
            "name": u.get("name", u["username"]),
            "created_at": u.get("created_at")
        }
        for u in users
    ]
    return {"status": "ok", "users": safe_users}

@app.post("/api/users")
async def create_new_user(req: CreateUserRequest, admin: dict = Depends(require_admin)):
    try:
        new_u = add_user(req.username, req.password, role=req.role, name=req.name or "")
        return {
            "status": "ok",
            "user": {
                "username": new_u["username"],
                "role": new_u["role"],
                "name": new_u["name"],
                "created_at": new_u["created_at"]
            }
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

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
    if not req.cids:
        raise HTTPException(status_code=400, detail="กรุณาระบุเลขค้นหาอย่างน้อย 1 รายการ")

    job = job_manager.submit_job(
        user=user,
        cids=req.cids,
        mode=req.mode,
        job_name=req.job_name,
        headless=req.headless
    )
    return {
        "status": "queued" if job.queue_position > 1 else "started",
        "job_id": job.job_id,
        "queue_position": job.queue_position,
        "total": len(req.cids),
        "mode": req.mode
    }

@app.post("/api/stop")
async def stop_crawl(job_id: Optional[str] = None, user: str = Depends(get_current_user)):
    stopped = job_manager.stop_job(user=user, job_id=job_id)
    if stopped:
        return {"status": "stopping"}
    return {"status": "not_running_or_not_found"}

@app.get("/api/jobs")
async def get_jobs_history(user: str = Depends(get_current_user)):
    history = job_manager.get_user_jobs_history(user=user)
    return {"status": "ok", "jobs": history}

# ------------------ Upload & Download ------------------
@app.post("/api/upload_excel")
async def upload_excel(file: UploadFile = File(...), user: str = Depends(get_current_user)):
    ext = os.path.splitext(file.filename)[1].lower()
    temp_path = os.path.join(BASE_DIR, "data", f"upload_{int(time.time())}{ext}")
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
async def websocket_status(websocket: WebSocket, token: Optional[str] = None):
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
            job = job_manager.get_user_current_job(user)
            data = job.to_dict()
            await websocket.send_json(data)
            await asyncio.sleep(0.7)
    except (WebSocketDisconnect, Exception):
        pass
    finally:
        if websocket in active_websockets:
            active_websockets.remove(websocket)
