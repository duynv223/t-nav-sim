from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from multiprocessing import Process, Queue
from pathlib import Path
import os
import subprocess
from threading import Lock, Thread
from typing import Any, Dict, Optional
import uuid
import logging

from app.app_settings import AppSettings
from app.gen_service import run_gen
from app.schemas import GenRequestPayload
from app.logger import configure_logging


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"


@dataclass
class GenJob:
    job_id: str
    session_id: str
    status: JobStatus
    created_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    motion_csv: Optional[str] = None
    iq: Optional[str] = None
    error: Optional[str] = None
    process: Optional[Process] = None
    queue: Optional[Queue] = None


logger = logging.getLogger("sim.jobs")


def _run_gen_job(
    payload: dict,
    session_root: str,
    app_settings_data: dict,
    result_queue: Queue,
) -> None:
    configure_logging()
    try:
        logger.info("gen.worker.start session_root=%s", session_root)
        request = GenRequestPayload.model_validate(payload)
        app_settings = AppSettings.model_validate(app_settings_data)
        motion_path, iq_path = run_gen(
            request,
            Path(session_root),
            app_settings,
        )
        logger.info("gen.worker.done motion_csv=%s iq=%s", motion_path, iq_path)
        result_queue.put(
            {"status": "ok", "motion_csv": str(motion_path), "iq": str(iq_path)}
        )
    except Exception as exc:
        logger.exception("gen.worker.failed error=%s", exc)
        result_queue.put({"status": "error", "error": str(exc)})


class GenJobManager:
    def __init__(self) -> None:
        self._jobs: Dict[str, GenJob] = {}
        self._active_by_session: Dict[str, str] = {}
        self._lock = Lock()

    def start(
        self,
        session_id: str,
        session_root: Path,
        payload: dict,
        app_settings: dict,
    ) -> GenJob:
        with self._lock:
            active_id = self._active_by_session.get(session_id)
            if active_id:
                active_job = self._jobs.get(active_id)
                if active_job and active_job.status in {JobStatus.PENDING, JobStatus.RUNNING}:
                    logger.info(
                        "gen.start session_id=%s status=existing job_id=%s",
                        session_id,
                        active_id,
                    )
                    return active_job

            job_id = self._next_job_id()
            now = datetime.now(timezone.utc)
            queue: Queue = Queue()
            job = GenJob(
                job_id=job_id,
                session_id=session_id,
                status=JobStatus.PENDING,
                created_at=now,
                queue=queue,
            )
            self._jobs[job_id] = job
            self._active_by_session[session_id] = job_id

            proc = Process(
                target=_run_gen_job,
                args=(payload, str(session_root), app_settings, queue),
                daemon=True,
            )
            job.process = proc
            job.status = JobStatus.RUNNING
            job.started_at = datetime.now(timezone.utc)
            proc.start()
            logger.info("gen.start session_id=%s job_id=%s", session_id, job_id)

            watcher = Thread(target=self._watch_job, args=(job,), daemon=True)
            watcher.start()

            return job

    def _next_job_id(self) -> str:
        for _ in range(10):
            candidate = uuid.uuid4().hex[:8]
            if candidate not in self._jobs:
                return candidate
        raise RuntimeError("Failed to allocate job id")

    def _watch_job(self, job: GenJob) -> None:
        if not job.process or not job.queue:
            return
        job.process.join()
        result: Dict[str, Any] | None = None
        try:
            if not job.queue.empty():
                result = job.queue.get_nowait()
        except Exception:
            result = None

        with self._lock:
            if job.status == JobStatus.CANCELED:
                self._active_by_session.pop(job.session_id, None)
                logger.info("gen.done session_id=%s job_id=%s status=canceled", job.session_id, job.job_id)
                return
            if result and result.get("status") == "ok":
                job.status = JobStatus.COMPLETED
                job.motion_csv = result.get("motion_csv")
                job.iq = result.get("iq")
                logger.info(
                    "gen.done session_id=%s job_id=%s status=completed",
                    job.session_id,
                    job.job_id,
                )
            else:
                job.status = JobStatus.FAILED
                job.error = (result or {}).get("error") or "job failed"
                logger.info(
                    "gen.done session_id=%s job_id=%s status=failed error=%s",
                    job.session_id,
                    job.job_id,
                    job.error,
                )
            job.finished_at = datetime.now(timezone.utc)
            self._active_by_session.pop(job.session_id, None)

    def get(self, job_id: str) -> Optional[GenJob]:
        with self._lock:
            return self._jobs.get(job_id)

    def cancel(self, job_id: str) -> Optional[GenJob]:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return None
            if job.status in {JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELED}:
                return job
            job.status = JobStatus.CANCELED
            job.finished_at = datetime.now(timezone.utc)
            self._active_by_session.pop(job.session_id, None)
            if job.process and job.process.is_alive():
                _terminate_process_tree(job.process.pid)
            logger.info("gen.cancel session_id=%s job_id=%s", job.session_id, job.job_id)
            return job


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
