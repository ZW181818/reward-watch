from __future__ import annotations

import base64
import hashlib
import hmac
import os
from datetime import UTC, datetime, timedelta

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError
from sqlalchemy.orm import Session

from .database import AdminUserRow, initialize_database


TOKEN_ALGORITHM = "HS256"
TOKEN_HOURS = 8
bearer_scheme = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    if len(password) < 12:
        raise ValueError("Administrator passwords must contain at least 12 characters")

    salt = os.urandom(16)
    work_factor = 2**14
    digest = hashlib.scrypt(
        password.encode("utf-8"), salt=salt, n=work_factor, r=8, p=1, dklen=32
    )
    return "scrypt${}${}${}${}${}".format(
        work_factor,
        8,
        1,
        base64.urlsafe_b64encode(salt).decode("ascii"),
        base64.urlsafe_b64encode(digest).decode("ascii"),
    )


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, work_factor, block_size, parallelism, salt_value, digest_value = encoded.split("$")
        if algorithm != "scrypt":
            return False
        salt = base64.urlsafe_b64decode(salt_value.encode("ascii"))
        expected = base64.urlsafe_b64decode(digest_value.encode("ascii"))
        actual = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=int(work_factor),
            r=int(block_size),
            p=int(parallelism),
            dklen=len(expected),
        )
        return hmac.compare_digest(actual, expected)
    except (TypeError, ValueError):
        return False


def _jwt_secret() -> str:
    configured = os.getenv("ADMIN_JWT_SECRET")
    if configured:
        return configured
    if os.getenv("APP_ENV", "development").lower() == "production":
        raise RuntimeError("ADMIN_JWT_SECRET is required in production")
    return "reward-watch-local-development-secret-change-me"


def create_access_token(user: AdminUserRow) -> str:
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "sub": user.email,
            "role": user.role,
            "iat": now,
            "exp": now + timedelta(hours=TOKEN_HOURS),
        },
        _jwt_secret(),
        algorithm=TOKEN_ALGORITHM,
    )


def require_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> str:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Admin login required")

    try:
        payload = jwt.decode(
            credentials.credentials,
            _jwt_secret(),
            algorithms=[TOKEN_ALGORITHM],
        )
        email = str(payload["sub"])
    except (InvalidTokenError, KeyError, RuntimeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin session is invalid or expired",
        ) from None

    engine = initialize_database()
    try:
        with Session(engine) as session:
            user = session.query(AdminUserRow).filter(AdminUserRow.email == email).one_or_none()
            if user is None or not user.is_active:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access disabled")
    finally:
        engine.dispose()

    return email
