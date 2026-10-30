import hmac
import hashlib
import time
import secrets
from fastapi import Request, HTTPException, Depends
from fastapi.security import APIKeyCookie, HTTPBearer, HTTPAuthorizationCredentials
from backend.storage import load_config

COOKIE_NAME = "auth_session"
cookie_sec = APIKeyCookie(name=COOKIE_NAME, auto_error=False)
bearer_sec = HTTPBearer(auto_error=False)

def hash_password(password: str) -> str:
    cfg = load_config()
    secret = cfg.get("auth_secret_token", "default_secret")
    return hmac.new(secret.encode(), password.encode(), hashlib.sha256).hexdigest()

def create_session_token(username: str) -> str:
    cfg = load_config()
    secret = cfg.get("auth_secret_token", "default_secret")
    expires = int(time.time()) + (30 * 86400) # 30 days
    payload = f"{username}:{expires}"
    sig = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}:{sig}"

def verify_session_token(token: str) -> str:
    """Returns username if valid, otherwise raises HTTPException"""
    if not token or str(token).strip() in ["", "undefined", "null", "None"]:
        raise HTTPException(status_code=401, detail="Missing authentication token")
    parts = token.split(":")
    if len(parts) != 3:
        raise HTTPException(status_code=401, detail="Malformed token")
    username, expires_str, sig = parts
    try:
        expires = int(expires_str)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid token expiry")
    if time.time() > expires:
        raise HTTPException(status_code=401, detail="Token expired")
    cfg = load_config()
    secret = cfg.get("auth_secret_token", "default_secret")
    expected_sig = hmac.new(secret.encode(), f"{username}:{expires}".encode(), hashlib.sha256).hexdigest()
    if not secrets.compare_digest(sig, expected_sig):
        raise HTTPException(status_code=401, detail="Invalid token signature")
    return username

async def get_current_user(
    request: Request,
    cookie_token: str = Depends(cookie_sec),
    auth_header: HTTPAuthorizationCredentials = Depends(bearer_sec)
) -> str:
    # 1. Prefer session cookie if valid
    if cookie_token and cookie_token not in ["undefined", "null", ""]:
        try:
            return verify_session_token(cookie_token)
        except Exception:
            pass

    # 2. Check Bearer token from header
    if auth_header and auth_header.credentials and auth_header.credentials not in ["undefined", "null", ""]:
        try:
            return verify_session_token(auth_header.credentials)
        except Exception:
            pass

    # 3. Check query param fallback
    token = request.query_params.get("token")
    if token and token not in ["undefined", "null", ""]:
        try:
            return verify_session_token(token)
        except Exception:
            pass

    raise HTTPException(status_code=401, detail="Not authenticated")

def authenticate_user(username: str, password: str, device_id: str = "", client_ip: str = "") -> dict:
    """
    Validates username and password, then checks expiration and hardware/device limits (max 2 devices).
    Returns {"ok": True, "user": user_dict} or raises HTTPException with specific clear Thai message.
    """
    from datetime import datetime
    from backend.storage import get_user, load_config, save_users, load_users
    clean_u = (username or "").strip()
    clean_p = (password or "").strip()
    if not clean_u or not clean_p:
        raise HTTPException(status_code=401, detail="กรุณากรอกชื่อผู้ใช้และรหัสผ่าน")

    u = get_user(clean_u)
    if not u:
        # Fallback to config default
        cfg = load_config()
        valid_u = cfg.get("web_username", "admin").strip()
        valid_p = cfg.get("web_password", "password123").strip()
        if secrets.compare_digest(clean_u, valid_u) and secrets.compare_digest(clean_p, valid_p):
            return {"ok": True, "username": valid_u, "role": "admin", "name": "ผู้ดูแลระบบ (Admin)"}
        raise HTTPException(status_code=401, detail="ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง")

    expected_p = str(u.get("password", "")).strip()
    if not secrets.compare_digest(clean_p, expected_p):
        raise HTTPException(status_code=401, detail="ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง")

    # 1. Check expiration date (Admin is never expired)
    if u.get("role") != "admin":
        expire_str = str(u.get("expire_date", "")).strip()
        if expire_str:
            try:
                # Expect YYYY-MM-DD
                exp_dt = datetime.strptime(expire_str, "%Y-%m-%d")
                # Set to end of day 23:59:59
                exp_ts = exp_dt.timestamp() + 86399
                if time.time() > exp_ts:
                    raise HTTPException(
                        status_code=403, 
                        detail=f"บัญชีผู้ใช้นี้หมดอายุการใช้งานแล้ว (หมดอายุเมื่อ: {expire_str}) กรุณาติดต่อผู้ดูแลระบบเพื่อต่ออายุ"
                    )
            except ValueError:
                pass

    # 2. Check Device / MAC Address limit (Max 2 devices) (Admin is exempt)
    if u.get("role") != "admin" and device_id:
        max_dev = int(u.get("max_devices") or 2)
        users = load_users()
        for target_u in users:
            if target_u.get("username", "").strip().lower() == clean_u.lower():
                devices = target_u.get("devices")
                if not isinstance(devices, list):
                    devices = []
                
                # Check if device_id is already registered
                existing_dev = next((d for d in devices if d.get("id") == device_id), None)
                if existing_dev:
                    existing_dev["last_seen"] = int(time.time())
                    existing_dev["ip"] = client_ip or existing_dev.get("ip", "")
                else:
                    if len(devices) >= max_dev:
                        raise HTTPException(
                            status_code=403,
                            detail=f"บัญชีนี้ถูกผูกใช้งานครบโควต้า {max_dev} เครื่องแล้ว ไม่สามารถเข้าใช้งานจากเครื่องใหม่ได้ กรุณาติดต่อผู้ดูแลระบบเพื่อรีเซ็ตเครื่อง"
                        )
                    devices.append({
                        "id": device_id,
                        "ip": client_ip,
                        "first_seen": int(time.time()),
                        "last_seen": int(time.time())
                    })
                target_u["devices"] = devices
                save_users(users)
                u = target_u
                break

    return {"ok": True, "username": u["username"], "role": u.get("role", "member"), "name": u.get("name", u["username"])}

def get_current_user_info(username: str = Depends(get_current_user)) -> dict:
    from backend.storage import get_user
    u = get_user(username)
    if u:
        return {
            "username": u["username"],
            "role": u.get("role", "member"),
            "name": u.get("name", u["username"])
        }
    return {
        "username": username,
        "role": "admin" if username.lower() == "admin" else "member",
        "name": username
    }

def require_admin(user_info: dict = Depends(get_current_user_info)) -> dict:
    if user_info.get("role") != "admin":
        raise HTTPException(status_code=403, detail="ต้องใช้สิทธิ์ Admin ในการดำเนินการ")
    return user_info
