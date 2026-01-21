from __future__ import annotations

import csv
import logging
import queue as queue_module
import time
from datetime import datetime
from multiprocessing import Queue
from pathlib import Path

from app.app_settings import AppSettings
from app.schemas import RunRequestPayload
from dsim.adapters.gps_hackrf import HackrfGpsTransmitter, HackrfTxConfig
from dsim.adapters.speed_bearing_serial import (
    SerialSpeedBearingController,
    SpeedBearingSerialConfig,
)
from dsim.core.models import MotionSample
from dsim.core.port import GpsTransmitter, SpeedBearingController
from dsim.core.use_cases.play import PlayRequest, play_simulation

logger = logging.getLogger("sim.run")


def run_play(
    request: RunRequestPayload,
    session_root: Path,
    app_settings: AppSettings,
    event_queue: Queue,
) -> None:
    motion_path = _resolve_input(session_root, request.motion_csv, "motion.csv")
    iq_path = _resolve_input(session_root, request.iq, "route.iq")
    logger.info(
        "run.play.start motion_csv=%s iq=%s realtime=%s gps_only=%s",
        motion_path,
        iq_path,
        request.realtime,
        request.gps_only,
    )
    if not motion_path.exists():
        raise FileNotFoundError(motion_path)
    if not iq_path.exists():
        raise FileNotFoundError(iq_path)

    samples = _load_motion_csv(motion_path)
    if request.realtime and request.start_time:
        target = _parse_start_time(request.start_time)
        if target:
            _emit_status(event_queue, "waiting")
            _sleep_until(target)

    gps_transmitter = _build_gps_transmitter(app_settings)
    controller = _build_controller(app_settings, request.gps_only)
    try:
        _emit_status(event_queue, "running")
        play_simulation(
            PlayRequest(samples, str(iq_path)),
            gps_transmitter=gps_transmitter,
            controller=controller,
            on_motion=_build_motion_cb(event_queue),
        )
    finally:
        _close_controller(controller)
    logger.info("run.play.done")
    _emit_status(event_queue, "completed")


def _resolve_input(session_root: Path, value: str, fallback: str) -> Path:
    raw = value.strip() if isinstance(value, str) else ""
    name = raw or fallback
    path = Path(name)
    if path.is_absolute():
        raise ValueError("input paths must be relative")
    if ".." in path.parts:
        raise ValueError("input paths must not include '..'")
    return (session_root / "out" / path).resolve()


def _load_motion_csv(path: Path) -> list[MotionSample]:
    samples: list[MotionSample] = []
    with path.open("r", encoding="ascii", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            samples.append(
                MotionSample(
                    t_s=float(row["t_s"]),
                    lat=float(row["lat"]),
                    lon=float(row["lon"]),
                    alt_m=float(row.get("alt_m", 0.0)),
                    speed_mps=float(row["speed_mps"]),
                    bearing_deg=float(row["bearing_deg"]),
                )
            )
    if not samples:
        raise ValueError("motion samples are empty")
    return samples


def _build_gps_transmitter(app_settings: AppSettings) -> GpsTransmitter:
    cfg = app_settings.gps_transmitter
    hackrf_config = HackrfTxConfig(
        center_freq_hz=cfg.center_freq_hz,
        sample_rate_hz=cfg.sample_rate_hz,
        txvga_gain=cfg.txvga_gain,
        amp_enabled=cfg.amp_enabled,
    )
    return HackrfGpsTransmitter(hackrf_config)


def _build_controller(app_settings: AppSettings, gps_only: bool) -> SpeedBearingController:
    if gps_only:
        return _NullController()
    cfg = app_settings.controller
    serial_config = SpeedBearingSerialConfig(port=cfg.port)
    return SerialSpeedBearingController(serial_config)


def _close_controller(controller: SpeedBearingController) -> None:
    close = getattr(controller, "close", None)
    if callable(close):
        close()


def _parse_start_time(value: str) -> datetime | None:
    raw = value.strip()
    if not raw:
        return None
    cleaned = raw.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(cleaned)
    except ValueError as exc:
        raise ValueError(f"Invalid start_time format: {value}") from exc
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone().replace(tzinfo=None)
    return parsed


def _sleep_until(target: datetime) -> None:
    while True:
        remaining = (target - datetime.now()).total_seconds()
        if remaining <= 0:
            return
        time.sleep(min(0.5, remaining))


def _emit_status(event_queue: Queue, status: str) -> None:
    _emit_event(event_queue, {"event": "status", "status": status})


def _build_motion_cb(event_queue: Queue):
    last_sent = -1.0

    def _on_motion(sample: MotionSample) -> None:
        nonlocal last_sent
        if sample.t_s <= last_sent:
            return
        last_sent = sample.t_s
        payload = {
            "t": sample.t_s,
            "lat": sample.lat,
            "lon": sample.lon,
            "alt_m": sample.alt_m,
            "speed_mps": sample.speed_mps,
            "speed_kmh": sample.speed_mps * 3.6,
            "bearing": sample.bearing_deg,
        }
        _emit_event(event_queue, {"event": "telemetry", "data": payload})

    return _on_motion


def _emit_event(event_queue: Queue, payload: dict) -> None:
    try:
        event_queue.put_nowait(payload)
    except queue_module.Full:
        logger.warning("run.event_queue.full")


class _NullController(SpeedBearingController):
    def prepaire_start_deg(self, bearing_deg: float) -> None:
        return None

    def set_speed_kmh(self, speed_kmh: float) -> None:
        return None

    def set_bearing_deg(self, bearing_deg: float) -> None:
        return None

    def stop(self) -> None:
        return None
