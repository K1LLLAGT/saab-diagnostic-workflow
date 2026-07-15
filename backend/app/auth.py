"""
SAAB-SUITE cloud backend — OAuth2 password-flow authentication + RBAC.

Minimal OAuth2-compatible token issuance (JWT bearer tokens) for a
single-technician / small-shop deployment. Roles: technician, lead,
admin, readonly. This is NOT a full OAuth2 authorization-server
implementation (no third-party client registration/consent) — it
implements the "password" grant type against the local user table,
which is the grant FastAPI's OAuth2PasswordBearer expects.
"""

from __future__ import annotations
import os
import time
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from backend.app.db import get_db
from backend.app.models import User

SECRET_KEY = os.environ.get("SAABSUITE_JWT_SECRET", "dev-only-secret-change-me")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 8

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="oauth/token")

ROLE_HIERARCHY = {"readonly": 0, "technician": 1, "lead": 2, "admin": 3}


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(subject: str, role: str) -> str:
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": subject, "role": role, "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def authenticate_user(db: Session, username: str, password: str) -> Optional[User]:
    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(password, user.hashed_password):
        return None
    return user


async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise credentials_exception
    return user


def require_role(minimum_role: str):
    def _dep(user: User = Depends(get_current_user)) -> User:
        if ROLE_HIERARCHY.get(user.role, -1) < ROLE_HIERARCHY.get(minimum_role, 99):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                 detail=f"Requires role >= {minimum_role}")
        return user
    return _dep
