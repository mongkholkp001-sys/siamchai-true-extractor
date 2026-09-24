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
    parse_excel_cids, parse_cids_from_text
)
from backend.auth import (
    authenticate_user, create_session_token, get_current_user, COOKIE_NAME,
    verify_session_token
)
from backend.unified_engine import unified_job, run_unified_process

app = FastAPI(title="Siamchai & TrueCorp Unified Extractor")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
        # Redirect to login page
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
    # Set HTTP-only Cookie
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=False, # Allow JS to read for websocket or API
        max_age=30 * 86400,
        samesite="lax"
    )
    return {"status": "ok", "token": token, "username": req.username}

@app.post("/api/auth/logout")
async def api_logout(response: Response):
    response.delete_cookie(key=COOKIE_NAME)
    return {"status": "ok"}

@app.get("/api/auth/me")
async def api_me(user: str = Depends(get_current_user)):
    return {"status": "ok", "username": user}

# ------------------ Process & Control Endpoints ------------------
@app.get("/api/status")
async def get_status(user: str = Depends(get_current_user)):
    return unified_job.to_dict()

@app.post("/api/start")
async def start_crawl(req: StartRequest, user: str = Depends(get_current_user)):
    if unified_job.status == "running":
        raise HTTPException(status_code=400, detail="ระบบกำลังทำงานอยู่ กรุณารอให้เสร็จหรือกดหยุดก่อน")
    if not req.cids:
        raise HTTPException(status_code=400, detail="กรุณาระบุเลขค้นหาอย่างน้อย 1 รายการ")

    t = threading.Thread(
        target=run_unified_process,
        kwargs={
            "cids": req.cids,
            "mode": req.mode,
            "job_name": req.job_name,
            "headless": req.headless,
        },
        daemon=True
    )
    t.start()
    return {"status": "started", "total": len(req.cids), "mode": req.mode}

@app.post("/api/stop")
async def stop_crawl(user: str = Depends(get_current_user)):
    unified_job.stop_requested = True
    if unified_job.siamchai_crawler:
        unified_job.siamchai_crawler.stop_requested = True
    if unified_job.true_crawler:
        unified_job.true_crawler.stop_requested = True
    unified_job.add_log("🛑 ได้รับคำสั่งหยุดการทำงานจากผู้ใช้...")
    return {"status": "stopping"}

# ------------------ Dual Screenshot Streaming ------------------
@app.get("/api/screenshot/siamchai")
async def get_siamchai_screen():
    crawler = unified_job.siamchai_crawler
    if crawler:
        img_bytes = crawler.get_screenshot_bytes()
        if img_bytes:
            return Response(content=img_bytes, media_type="image/png")
    # Return placeholder
    return FileResponse(os.path.join(STATIC_DIR, "placeholder_siamchai.png")) if os.path.exists(os.path.join(STATIC_DIR, "placeholder_siamchai.png")) else Response(status_code=204)

@app.get("/api/screenshot/true")
async def get_true_screen():
    crawler = unified_job.true_crawler
    if crawler:
        img_bytes = crawler.get_screenshot_bytes()
        if img_bytes:
            return Response(content=img_bytes, media_type="image/png")
    # Return placeholder
    return FileResponse(os.path.join(STATIC_DIR, "placeholder_true.png")) if os.path.exists(os.path.join(STATIC_DIR, "placeholder_true.png")) else Response(status_code=204)

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
async def download_excel(type: str = "combined", token: Optional[str] = None, request: Request = None):
    # Verify token from query or cookie
    auth_t = token or (request.cookies.get(COOKIE_NAME) if request else None)
    if auth_t:
        try:
            verify_session_token(auth_t)
        except Exception:
            raise HTTPException(status_code=401, detail="Unauthorized")
    
    target_path = None
    if type == "siamchai":
        target_path = unified_job.sc_excel_path
    elif type == "true":
        target_path = unified_job.tr_excel_path
    else: # combined
        target_path = unified_job.combined_excel_path or unified_job.sc_excel_path or unified_job.tr_excel_path

    if not target_path or not os.path.exists(target_path):
        raise HTTPException(status_code=404, detail="ยังไม่มีไฟล์ Excel ให้ดาวน์โหลดสำหรับส่วนนี้")

    return FileResponse(
        path=target_path,
        filename=os.path.basename(target_path),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

@app.get("/api/download/siamchai")
async def download_siamchai_excel(token: Optional[str] = None, request: Request = None):
    return await download_excel(type="siamchai", token=token, request=request)

@app.get("/api/download/true")
async def download_true_excel(token: Optional[str] = None, request: Request = None):
    return await download_excel(type="true", token=token, request=request)

@app.get("/api/download/combined")
async def download_combined_excel(token: Optional[str] = None, request: Request = None):
    return await download_excel(type="combined", token=token, request=request)


# ------------------ Config Endpoints ------------------
@app.get("/api/config")
async def get_config_endpoint(user: str = Depends(get_current_user)):
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
async def update_config_endpoint(req: ConfigUpdateRequest, user: str = Depends(get_current_user)):
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
async def websocket_status(websocket: WebSocket):
    await websocket.accept()
    active_websockets.append(websocket)
    try:
        while True:
            data = unified_job.to_dict()
            await websocket.send_json(data)
            await asyncio.sleep(0.7)
    except (WebSocketDisconnect, Exception):
        pass
    finally:
        if websocket in active_websockets:
            active_websockets.remove(websocket)
