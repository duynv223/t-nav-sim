from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from multiprocessing import Process, Queue
from pathlib import Path
from threading import Lock, Thread
from typing import Any, Dict, Optional
import uuid

from app.app_settings import IqGeneratorSettings
from app.gen_service import run_gen
from app.schemas import GenRequestPayload
from app.settings import Settings


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


def _run_gen_job(
    payload: dict,
    session_root: str,
    settings_data: dict,
    iq_settings: dict | None,
    result_queue: Queue,
) -> None:
    try:
        request = GenRequestPayload.model_validate(payload)
        settings = Settings(
            session_root=Path(session_root),
            gps_sdr_sim_path=settings_data["gps_sdr_sim_path"],
            ephemeris_path=settings_data["ephemeris_path"],
            iq_bits=settings_data["iq_bits"],
            iq_sample_rate_hz=settings_data["iq_sample_rate_hz"],
            enable_iq=settings_data["enable_iq"],
            app_settings_path=Path(settings_data["app_settings_path"]),
        )
        iq_profile = None
        if iq_settings:
            iq_profile = IqGeneratorSettings.model_validate(iq_settings)
        motion_path, iq_path = run_gen(
            request,
            Path(session_root),
            settings,
            iq_settings=iq_profile,
        )
        result_queue.put(
            {"status": "ok", "motion_csv": str(motion_path), "iq": str(iq_path)}
        )
    except Exception as exc:
        result_queue.put({"status": "error", "error": str(exc)})


class GenJobManager:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._jobs: Dict[str, GenJob] = {}
        self._active_by_session: Dict[str, str] = {}
        self._lock = Lock()

    def start(
        self,
        session_id: str,
        session_root: Path,
        payload: dict,
        iq_settings: dict | None = None,
    ) -> GenJob:
        with self._lock:
            active_id = self._active_by_session.get(session_id)
            if active_id:
                active_job = self._jobs.get(active_id)
                if active_job and active_job.status in {JobStatus.PENDING, JobStatus.RUNNING}:
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

            settings_data = {
                "gps_sdr_sim_path": self._settings.gps_sdr_sim_path,
                "ephemeris_path": self._settings.ephemeris_path,
                "iq_bits": self._settings.iq_bits,
                "iq_sample_rate_hz": self._settings.iq_sample_rate_hz,
                "enable_iq": self._settings.enable_iq,
                "app_settings_path": str(self._settings.app_settings_path),
            }

            proc = Process(
                target=_run_gen_job,
                args=(payload, str(session_root), settings_data, iq_settings, queue),
                daemon=True,
            )
            job.process = proc
            job.status = JobStatus.RUNNING
            job.started_at = datetime.now(timezone.utc)
            proc.start()

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
                return
            if result and result.get("status") == "ok":
                job.status = JobStatus.COMPLETED
                job.motion_csv = result.get("motion_csv")
                job.iq = result.get("iq")
            else:
                job.status = JobStatus.FAILED
                job.error = (result or {}).get("error") or "job failed"
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
                job.process.terminate()
            return job
