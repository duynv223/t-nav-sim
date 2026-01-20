from __future__ import annotations

import errno
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Iterable, List

from core.models import MotionSample
from core.port import GpsTransmitter, SpeedBearingController
from core.reporting import ReporterProtocol, StepInfo, StepStatus, StepUpdate, step_context


@dataclass(frozen=True)
class PlayRequest:
    samples: Iterable[MotionSample]
    iq_route_path: str


def play_simulation(
    request: PlayRequest,
    *,
    gps_transmitter: GpsTransmitter,
    controller: SpeedBearingController,
    reporter: ReporterProtocol | None = None,
    on_motion: Callable[[MotionSample], None] | None = None,
) -> None:
    samples = list(request.samples)
    if not samples:
        raise ValueError("samples must not be empty")

    _validate_samples(samples)

    steps = [
        StepInfo("play", "Play motions and GPS signals", weight=100),
    ]
    if reporter:
        reporter.on_setup_steps(steps)

    gps_error: list[BaseException] = []
    gps_thread = threading.Thread(
        target=_play_gps,
        args=(gps_transmitter, request.iq_route_path, gps_error),
        daemon=True,
    )

    try:
        controller.stop()
        controller.prepaire_start_deg(samples[0].bearing_deg)
        with step_context(
            "play",
            reporter,
            "Playing motion and GPS signals",
            "Motions and GPS signals played",
        ):
            gps_thread.start()
            try:
                _play_motion(
                    samples,
                    controller,
                    on_motion,
                    _motion_progress_cb(reporter),
                    gps_error,
                )
            finally:
                gps_thread.join()
            if gps_error:
                err = gps_error[0]
                raise err
    finally:
        controller.stop()


def _play_gps(
    gps_transmitter: GpsTransmitter,
    iq_route_path: str,
    errors: list[BaseException],
) -> None:
    try:
        gps_transmitter.play(iq_route_path)
    except BaseException as exc:  # noqa: BLE001
        errors.append(exc)


def _play_motion(
    samples: List[MotionSample],
    controller: SpeedBearingController,
    on_motion: Callable[[MotionSample], None] | None,
    on_progress: Callable[[int], None] | None,
    errors: list[BaseException] | None = None,
) -> None:
    if not samples:
        return
    if errors:
        return
    total_s = samples[-1].t_s - samples[0].t_s
    last_percent = 0

    controller.set_bearing_deg(samples[0].bearing_deg)
    controller.set_speed_kmh(samples[0].speed_mps * 3.6)
    if on_motion:
        on_motion(samples[0])

    base_t = samples[0].t_s
    start_time = time.monotonic()
    for curr in samples[1:]:
        if errors:
            break
        target = start_time + (curr.t_s - base_t)
        remaining = target - time.monotonic()
        if remaining > 0:
            time.sleep(remaining)
            if errors:
                break
        controller.set_bearing_deg(curr.bearing_deg)
        controller.set_speed_kmh(curr.speed_mps * 3.6)
        if on_motion:
            on_motion(curr)
        if on_progress and total_s > 0:
            percent = int(((curr.t_s - samples[0].t_s) / total_s) * 100)
            percent = min(max(percent, 0), 99)
            if percent > last_percent:
                on_progress(percent)
                last_percent = percent


def _validate_samples(samples: List[MotionSample]) -> None:
    prev_t = None
    for sample in samples:
        if sample.t_s < 0.0:
            raise ValueError("sample t_s must be >= 0")
        if prev_t is not None and sample.t_s < prev_t:
            raise ValueError("samples must be ordered by non-decreasing t_s")
        prev_t = sample.t_s


def _motion_progress_cb(
    reporter: ReporterProtocol | None,
) -> Callable[[int], None] | None:
    if reporter is None:
        return None

    def _notify(percent: int) -> None:
        reporter.on_update(
            StepUpdate("play", StepStatus.RUNNING, "Playing motion and GPS signals", percent)
        )

    return _notify
