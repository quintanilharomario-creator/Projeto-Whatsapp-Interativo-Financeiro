# backend/app/core/security.py
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt
from jwt.exceptions import InvalidTokenError as JWTError  # noqa: F401 — re-exported for callers

from app.core.config import settings


# ─── SENHA ────────────────────────────────────────────────────────────────────


def hash_password(plain_password: str) -> str:
    return bcrypt.hashpw(plain_password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode(), hashed_password.encode())


# ─── JWT ──────────────────────────────────────────────────────────────────────


def create_access_token(
    subject: str | Any, expires_delta: timedelta | None = None
) -> str:
    """
    Cria token JWT de acesso.

    Args:
        subject: geralmente o user_id
        expires_delta: tempo de expiração (padrão: 30 min)
    """
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload = {
        "sub": str(subject),  # "sub" é padrão JWT para o ID do dono
        "exp": expire,
        "type": "access",
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    """
    Decodifica e valida um token JWT.

    Raises:
        JWTError: se o token for inválido ou expirado
    """
    return jwt.decode(
        token,
        settings.SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
        options={"require": ["exp", "sub"]},
    )
