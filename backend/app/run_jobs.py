from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from multiprocessing import Process, Queue
from pathlib import Path
import os
import queue as queue_module
import subprocess
from threading import Lock, Thread
from typing import Any, Dict, Optional
import uuid

import logging

from app.app_settings import AppSettings
from app.logger import configure_logging
from app.run_service import run_play
from app.schemas import RunRequestPayload


logger = logging.getLogger("sim.run.jobs")


class RunStatus(str, Enum):
    PENDING = "pending"
    WAITING = "waiting"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"


@dataclass
class RunJob:
    job_id: str
    session_id: str
    status: RunStatus
    created_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    motion_csv: Optional[str] = None
    iq: Optional[str] = None
    error: Optional[str] = None
    process: Optional[Process] = None
    result_queue: Optional[Queue] = None
    event_queue: Optional[Queue] = None
    event_buffer: Optional[queue_module.Queue] = None


def _run_play_job(
    payload: dict,
    session_root: str,
    app_settings_data: dict,
    event_queue: Queue,
    result_queue: Queue,
) -> None:
    configure_logging()
    try:
        logger.info("run.worker.start session_root=%s", session_root)
        request = RunRequestPayload.model_validate(payload)
        app_settings = AppSettings.model_validate(app_settings_data)
        run_play(request, Path(session_root), app_settings, event_queue)
        result_queue.put({"status": "ok"})
        logger.info("run.worker.done")
    except Exception as exc:
        logger.exception("run.worker.failed error=%s", exc)
        try:
            event_queue.put_nowait(
                {"event": "status", "status": "failed", "error": str(exc)}
            )
        except queue_module.Full:
            pass
        result_queue.put({"status": "error", "error": str(exc)})


class RunJobManager:
    def __init__(self) -> None:
        self._jobs: Dict[str, RunJob] = {}
        self._active_by_session: Dict[str, str] = {}
        self._lock = Lock()

    def start(
        self,
        session_id: str,
        session_root: Path,
        payload: dict,
        app_settings: dict,
    ) -> RunJob:
        with self._lock:
            active_id = self._active_by_session.get(session_id)
            if active_id:
                active_job = self._jobs.get(active_id)
                if active_job and active_job.status in {
                    RunStatus.PENDING,
                    RunStatus.WAITING,
                    RunStatus.RUNNING,
                }:
                    logger.info(
                        "run.start session_id=%s status=existing job_id=%s",
                        session_id,
                        active_id,
                    )
                    return active_job

            job_id = self._next_job_id()
            now = datetime.now(timezone.utc)
            result_queue: Queue = Queue()
            event_queue: Queue = Queue(maxsize=1000)
            event_buffer: queue_module.Queue = queue_module.Queue(maxsize=2000)
            job = RunJob(
                job_id=job_id,
                session_id=session_id,
                status=RunStatus.PENDING,
                created_at=now,
                result_queue=result_queue,
                event_queue=event_queue,
                event_buffer=event_buffer,
            )
            job.motion_csv = payload.get("motion_csv")
            job.iq = payload.get("iq")
            self._jobs[job_id] = job
            self._active_by_session[session_id] = job_id

            proc = Process(
                target=_run_play_job,
                args=(payload, str(session_root), app_settings, event_queue, result_queue),
                daemon=True,
            )
            job.process = proc
            proc.start()

            pump = Thread(target=self._pump_events, args=(job,), daemon=True)
            pump.start()

            watcher = Thread(target=self._watch_job, args=(job,), daemon=True)
            watcher.start()

            logger.info("run.start session_id=%s job_id=%s", session_id, job_id)
            return job

    def _next_job_id(self) -> str:
        for _ in range(10):
            candidate = uuid.uuid4().hex[:8]
            if candidate not in self._jobs:
                return candidate
        raise RuntimeError("Failed to allocate job id")

    def _pump_events(self, job: RunJob) -> None:
        if not job.event_queue or not job.event_buffer:
            return
        terminal = {RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELED}
        while True:
            try:
                message = job.event_queue.get(timeout=0.5)
            except queue_module.Empty:
                if job.status in terminal and (not job.process or not job.process.is_alive()):
                    return
                continue
            if isinstance(message, dict):
                if message.get("event") == "status":
                    status = message.get("status")
                    if status:
                        try:
                            job.status = RunStatus(status)
                        except ValueError:
                            pass
                    error = message.get("error")
                    if error:
                        job.error = str(error)
                    if job.status == RunStatus.RUNNING and job.started_at is None:
                        job.started_at = datetime.now(timezone.utc)
                if message.get("event") == "telemetry":
                    pass
                _push_event(job.event_buffer, message)

    def _watch_job(self, job: RunJob) -> None:
        if not job.process or not job.result_queue:
            return
        job.process.join()
        result: Dict[str, Any] | None = None
        try:
            if not job.result_queue.empty():
                result = job.result_queue.get_nowait()
        except Exception:
            result = None

        with self._lock:
            if job.status == RunStatus.CANCELED:
                self._active_by_session.pop(job.session_id, None)
                return
            if result and result.get("status") == "ok":
                job.status = RunStatus.COMPLETED
                logger.info(
                    "run.done session_id=%s job_id=%s status=completed",
                    job.session_id,
                    job.job_id,
                )
            else:
                job.status = RunStatus.FAILED
                job.error = (result or {}).get("error") or "job failed"
                logger.info(
                    "run.done session_id=%s job_id=%s status=failed error=%s",
                    job.session_id,
                    job.job_id,
                    job.error,
                )
            job.finished_at = datetime.now(timezone.utc)
            self._active_by_session.pop(job.session_id, None)
            if job.event_buffer:
                _push_event(
                    job.event_buffer,
                    {
                        "event": "status",
                        "status": job.status.value,
                        "error": job.error,
                    },
                )

    def get(self, job_id: str) -> Optional[RunJob]:
        with self._lock:
            return self._jobs.get(job_id)

    def cancel(self, job_id: str) -> Optional[RunJob]:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return None
            if job.status in {RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELED}:
                return job
            job.status = RunStatus.CANCELED
            job.finished_at = datetime.now(timezone.utc)
            self._active_by_session.pop(job.session_id, None)
            if job.process and job.process.is_alive():
                _terminate_process_tree(job.process.pid)
            if job.event_buffer:
                _push_event(
                    job.event_buffer,
                    {"event": "status", "status": job.status.value},
                )
            logger.info("run.cancel session_id=%s job_id=%s", job.session_id, job.job_id)
            return job


def _push_event(buffer: queue_module.Queue, message: dict) -> None:
    try:
        buffer.put_nowait(message)
    except queue_module.Full:
        try:
            _ = buffer.get_nowait()
            buffer.put_nowait(message)
        except queue_module.Empty:
            pass


def _terminate_process_tree(pid: int) -> None:
    if os.name == "nt":
        try:
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception:
            logger.exception("Failed to taskkill pid=%s", pid)
        return
    try:
        os.kill(pid, 15)
    except Exception:
        logger.exception("Failed to terminate pid=%s", pid)
