"""
SAAB-SUITE cloud backend — FastAPI application entry point.

Run:  uvicorn backend.app.main:app --reload --port 8000
"""

from __future__ import annotations
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from backend.app.db import get_db, init_db
from backend.app.auth import authenticate_user, create_access_token, hash_password
from backend.app.schemas import Token
from backend.app.models import User
from backend.app import routes_vehicles, routes_dtc, routes_sync, websocket_remote


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="SAAB-SUITE Cloud & Remote Diagnostics API",
    description="Vehicle history sync + remote diagnostics backend for the SAAB-SUITE ecosystem.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # tighten to known desktop/Android/web origins in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/oauth/token", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    token = create_access_token(subject=user.username, role=user.role)
    return Token(access_token=token)


@app.post("/oauth/register", response_model=Token)
def register(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """First-run / admin-created technician accounts. In a shared
    deployment, gate this behind an existing admin token instead of
    leaving it open — left simple here for the single-shop default."""
    existing = db.query(User).filter(User.username == form_data.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username already registered")
    user = User(username=form_data.username, hashed_password=hash_password(form_data.password),
                role="technician")
    db.add(user)
    db.commit()
    token = create_access_token(subject=user.username, role=user.role)
    return Token(access_token=token)


@app.get("/health")
def health():
    return {"status": "ok"}


app.include_router(routes_vehicles.router)
app.include_router(routes_dtc.router)
app.include_router(routes_sync.router)
app.include_router(websocket_remote.router)
