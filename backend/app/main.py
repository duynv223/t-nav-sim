from __future__ import annotations

import asyncio
import logging
import time

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from app.app_settings import AppSettings
from app.jobs import GenJobManager, JobStatus
from app.schemas import (
    GenRequestPayload,
    GenJobStatusPayload,
    SessionCreatePayload,
    SessionInfoPayload,
)
from app.settings_store import SettingsStore
from app.session_store import SessionStore
from app.settings import load_settings

settings = load_settings()
session_store = SessionStore(settings.session_root)
job_manager = GenJobManager(settings)
settings_store = SettingsStore(settings.app_settings_path)

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


@app.post("/sessions/{session_id}/gen", response_model=GenJobStatusPayload)
def generate(session_id: str, payload: GenRequestPayload) -> GenJobStatusPayload:
    info = session_store.get(session_id)
    if not info:
        logger.info("gen.start id=%s status=not_found", session_id)
        raise HTTPException(status_code=404, detail="session not found")
    try:
        logger.info("gen.start id=%s", session_id)
        iq_settings = settings_store.get().iq_generator.model_dump()
        job = job_manager.start(session_id, info.root, payload.model_dump(), iq_settings)
    except Exception as exc:
        logger.info("gen.fail id=%s error=%s", session_id, exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    logger.info("gen.job id=%s job_id=%s status=%s", session_id, job.job_id, job.status)
    return _job_payload(job)


@app.get("/sessions/{session_id}/gen/{job_id}", response_model=GenJobStatusPayload)
def get_gen_status(session_id: str, job_id: str) -> GenJobStatusPayload:
    job = job_manager.get(job_id)
    if not job or job.session_id != session_id:
        logger.info("gen.status id=%s job_id=%s status=not_found", session_id, job_id)
        raise HTTPException(status_code=404, detail="job not found")
    logger.info("gen.status id=%s job_id=%s status=%s", session_id, job_id, job.status)
    return _job_payload(job)


@app.post("/sessions/{session_id}/gen/{job_id}/cancel", response_model=GenJobStatusPayload)
def cancel_gen(session_id: str, job_id: str) -> GenJobStatusPayload:
    job = job_manager.get(job_id)
    if not job or job.session_id != session_id:
        logger.info("gen.cancel id=%s job_id=%s status=not_found", session_id, job_id)
        raise HTTPException(status_code=404, detail="job not found")
    job = job_manager.cancel(job_id)
    if not job:
        logger.info("gen.cancel id=%s job_id=%s status=not_found", session_id, job_id)
        raise HTTPException(status_code=404, detail="job not found")
    logger.info("gen.cancel id=%s job_id=%s status=%s", session_id, job_id, job.status)
    return _job_payload(job)


@app.get("/settings", response_model=AppSettings)
def get_settings() -> AppSettings:
    logger.info("settings.get status=ok")
    return settings_store.get()


@app.put("/settings", response_model=AppSettings)
def update_settings(payload: AppSettings) -> AppSettings:
    settings_store.update(payload)
    logger.info("settings.update status=ok")
    return settings_store.get()


@app.get("/sessions/{session_id}/gen/{job_id}/events")
async def stream_gen_events(session_id: str, job_id: str, request: Request) -> StreamingResponse:
    job = job_manager.get(job_id)
    if not job or job.session_id != session_id:
        logger.info("gen.events id=%s job_id=%s status=not_found", session_id, job_id)
        raise HTTPException(status_code=404, detail="job not found")
    logger.info("gen.events id=%s job_id=%s status=connected", session_id, job_id)
    generator = _gen_job_events(request, session_id, job_id)
    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
    }
    return StreamingResponse(generator, media_type="text/event-stream", headers=headers)


def _job_payload(job) -> GenJobStatusPayload:
    return GenJobStatusPayload(
        job_id=job.job_id,
        session_id=job.session_id,
        status=job.status.value,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
        motion_csv=job.motion_csv,
        iq=job.iq,
        error=job.error,
    )


async def _gen_job_events(request: Request, session_id: str, job_id: str):
    last_status = None
    last_ping = time.monotonic()
    terminal_states = {JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELED}

    while True:
        if await request.is_disconnected():
            logger.info("gen.events id=%s job_id=%s status=disconnected", session_id, job_id)
            break
        job = job_manager.get(job_id)
        if not job:
            logger.info("gen.events id=%s job_id=%s status=missing", session_id, job_id)
            break

        if job.status != last_status:
            payload = _job_payload(job).model_dump_json()
            yield f"event: status\ndata: {payload}\n\n"
            last_status = job.status

        if job.status in terminal_states:
            break

        now = time.monotonic()
        if now - last_ping >= 10:
            yield ": ping\n\n"
            last_ping = now

        await asyncio.sleep(0.5)
