from __future__ import annotations

import logging
import time

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from app.gen_service import run_gen
from app.schemas import (
    GenRequestPayload,
    GenResultPayload,
    SessionCreatePayload,
    SessionInfoPayload,
)
from app.session_store import SessionStore
from app.settings import load_settings

settings = load_settings()
session_store = SessionStore(settings.session_root)

app = FastAPI(title="Nav Sim Backend", version="0.1.0")

logger = logging.getLogger("sim.api")
logger.setLevel(logging.INFO)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.monotonic()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    finally:
        duration_ms = (time.monotonic() - start) * 1000.0
        client_host = request.client.host if request.client else "-"
        logger.info(
            "%s %s %s %d %.1fms",
            client_host,
            request.method,
            request.url.path,
            status_code,
            duration_ms,
        )


@app.post("/sessions", response_model=SessionInfoPayload)
def create_session(payload: SessionCreatePayload | None = None) -> SessionInfoPayload:
    info = session_store.create(name=payload.name if payload else None)
    logger.info("session.create id=%s name=%s", info.session_id, info.name or "-")
    return SessionInfoPayload(
        session_id=info.session_id,
        created_at=info.created_at,
        work_dir=str(info.root),
        name=info.name,
    )


@app.get("/sessions/{session_id}", response_model=SessionInfoPayload)
def get_session(session_id: str) -> SessionInfoPayload:
    print('Getting session:', session_id)
    info = session_store.get(session_id)
    if not info:
        logger.info("session.get id=%s status=not_found", session_id)
        raise HTTPException(status_code=404, detail="session not found")
    logger.info("session.get id=%s status=ok", session_id)
    return SessionInfoPayload(
        session_id=info.session_id,
        created_at=info.created_at,
        work_dir=str(info.root),
        name=info.name,
    )


@app.delete("/sessions/{session_id}")
def delete_session(session_id: str) -> dict:
    removed = session_store.delete(session_id)
    if not removed:
        logger.info("session.delete id=%s status=not_found", session_id)
        raise HTTPException(status_code=404, detail="session not found")
    logger.info("session.delete id=%s status=deleted", session_id)
    return {"status": "deleted", "session_id": session_id}


@app.post("/sessions/{session_id}/gen", response_model=GenResultPayload)
def generate(session_id: str, payload: GenRequestPayload) -> GenResultPayload:
    info = session_store.get(session_id)
    if not info:
        logger.info("gen.start id=%s status=not_found", session_id)
        raise HTTPException(status_code=404, detail="session not found")
    try:
        logger.info("gen.start id=%s", session_id)
        motion_path, iq_path = run_gen(payload, info.root, settings)
    except Exception as exc:
        logger.info("gen.fail id=%s error=%s", session_id, exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    logger.info("gen.ok id=%s motion=%s iq=%s", session_id, motion_path, iq_path)
    return GenResultPayload(
        session_id=session_id,
        motion_csv=str(motion_path),
        iq=str(iq_path),
    )
