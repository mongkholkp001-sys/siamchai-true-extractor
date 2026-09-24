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
    if not token:
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
    token = None
    if cookie_token:
        token = cookie_token
    elif auth_header:
        token = auth_header.credentials
    else:
        # Check query param as fallback for downloads / websockets
        token = request.query_params.get("token")

    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    return verify_session_token(token)

def authenticate_user(username, password) -> bool:
    cfg = load_config()
    valid_u = cfg.get("web_username", "admin").strip()
    valid_p = cfg.get("web_password", "password123").strip()
    return secrets.compare_digest(username.strip(), valid_u) and secrets.compare_digest(password.strip(), valid_p)
