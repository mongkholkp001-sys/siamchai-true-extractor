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

def authenticate_user(username: str, password: str) -> bool:
    from backend.storage import get_user, load_config
    clean_u = (username or "").strip()
    clean_p = (password or "").strip()
    if not clean_u or not clean_p:
        return False

    u = get_user(clean_u)
    if u:
        expected_p = str(u.get("password", "")).strip()
        return secrets.compare_digest(clean_p, expected_p)

    # Fallback to config default
    cfg = load_config()
    valid_u = cfg.get("web_username", "admin").strip()
    valid_p = cfg.get("web_password", "password123").strip()
    return secrets.compare_digest(clean_u, valid_u) and secrets.compare_digest(clean_p, valid_p)

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
