import os
import secrets
from datetime import datetime, timedelta

from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

load_dotenv()

SECRET_KEY     = os.getenv("SECRET_KEY", "change-me")
ALGORITHM      = "HS256"
EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "1440"))
APP_USERNAME   = os.getenv("APP_USERNAME", "admin")
APP_PASSWORD   = os.getenv("APP_PASSWORD", "aurum2024")

_bearer = HTTPBearer()


def verify_credentials(username: str, password: str) -> bool:
    ok_user = secrets.compare_digest(username.encode(), APP_USERNAME.encode())
    ok_pass = secrets.compare_digest(password.encode(), APP_PASSWORD.encode())
    return ok_user and ok_pass


def create_token(username: str) -> str:
    expire  = datetime.utcnow() + timedelta(minutes=EXPIRE_MINUTES)
    payload = {"sub": username, "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def require_auth(credentials: HTTPAuthorizationCredentials = Depends(_bearer)):
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("sub") is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token tidak valid")
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token tidak valid atau sudah kadaluarsa")
