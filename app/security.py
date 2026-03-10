from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from typing import Optional

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app import models

# ----------------------------
# Config
# ----------------------------

TOKEN_SECRET = os.getenv("GYM_TOKEN_SECRET", "dev-change-me")
API_KEY = os.getenv("GYM_API_KEY", "key")

TOKEN_TTL_SECONDS = 60 * 60 * 8  # 8 hours
PWD_ITERATIONS = 210_000
PWD_SALT_BYTES = 16

bearer_scheme = HTTPBearer(auto_error=False)


# ----------------------------
# Password hashing (PBKDF2)
# Stored format: pbkdf2$<iterations>$<salt_b64>$<hash_b64>
# ----------------------------

def hash_password(password: str) -> str:
    if not isinstance(password, str) or len(password) < 8:
        raise ValueError("Password must be at least 8 characters")

    salt = os.urandom(PWD_SALT_BYTES)
    dk = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PWD_ITERATIONS,
    )
    return "pbkdf2${}${}${}".format(
        PWD_ITERATIONS,
        base64.urlsafe_b64encode(salt).decode("utf-8").rstrip("="),
        base64.urlsafe_b64encode(dk).decode("utf-8").rstrip("="),
    )


def verify_password(password: str, stored: str) -> bool:
    try:
        prefix, iters_s, salt_b64, hash_b64 = stored.split("$", 3)
        if prefix != "pbkdf2":
            return False
        iters = int(iters_s)
        salt = base64.urlsafe_b64decode(_pad_b64(salt_b64))
        expected = base64.urlsafe_b64decode(_pad_b64(hash_b64))

        dk = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            iters,
        )
        return hmac.compare_digest(dk, expected)
    except Exception:
        return False


# ----------------------------
# Token helpers (JWT-like)
# token format: <payload_b64>.<sig_b64>
# payload is JSON with exp, sub, role, username
# ----------------------------

def _pad_b64(s: str) -> str:
    return s + "=" * (-len(s) % 4)


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")


def _b64url_decode(s: str) -> bytes:
    return base64.urlsafe_b64decode(_pad_b64(s))


def create_access_token(*, user_id: int, username: str, role: str) -> str:
    payload = {
        "sub": int(user_id),
        "username": username,
        "role": role,
        "exp": int(time.time()) + TOKEN_TTL_SECONDS,
    }
    payload_bytes = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    payload_b64 = _b64url_encode(payload_bytes)

    sig = hmac.new(TOKEN_SECRET.encode("utf-8"), payload_b64.encode("utf-8"), hashlib.sha256).digest()
    sig_b64 = _b64url_encode(sig)

    return f"{payload_b64}.{sig_b64}"


def decode_access_token(token: str) -> dict:
    try:
        payload_b64, sig_b64 = token.split(".", 1)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token format")

    expected_sig = hmac.new(TOKEN_SECRET.encode("utf-8"), payload_b64.encode("utf-8"), hashlib.sha256).digest()
    if not hmac.compare_digest(_b64url_encode(expected_sig), sig_b64):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token signature")

    payload = json.loads(_b64url_decode(payload_b64).decode("utf-8"))

    exp = int(payload.get("exp", 0))
    if time.time() > exp:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")

    if "sub" not in payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    return payload


# ----------------------------
# FastAPI dependencies
# ----------------------------

def require_api_key(x_api_key: Optional[str] = Header(default=None)) -> None:
    if x_api_key is None or x_api_key != API_KEY:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing/invalid API key")


def get_current_user(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> models.User:
    if creds is None or creds.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")

    payload = decode_access_token(creds.credentials)
    user_id = int(payload["sub"])

    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    return user


def require_admin(current_user: models.User = Depends(get_current_user)) -> models.User:
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
    return current_user


def require_self_or_admin(
    user_id: int,
    current_user: models.User = Depends(get_current_user),
) -> models.User:
    if current_user.role == "admin":
        return current_user
    if current_user.id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not permitted")
    return current_user