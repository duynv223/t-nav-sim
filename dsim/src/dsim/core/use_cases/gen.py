from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List

from dsim.core.models import MotionProfile, MotionSample, Route
from dsim.core.motion import generate_motion_samples
from dsim.core.port import IqGenerator
from dsim.core.reporting import ReporterProtocol, StepInfo, step_context


@dataclass(frozen=True)
class GenRequest:
    route: Route
    profile: MotionProfile
    dt_s: float = 0.1
    start_time: str | None = None
    iq_route_path: str = "route.iq"
    samples_path: str | None = None


@dataclass(frozen=True)
class GenResult:
    samples: List[MotionSample]
    iq_route_path: str
    samples_path: str | None


def generate_artifacts(
    request: GenRequest,
    *,
    iq_generator: IqGenerator,
    reporter: ReporterProtocol | None = None,
) -> GenResult:
    if len(request.route.points) < 2:
        raise ValueError("route must have at least 2 points")

    steps = [
        StepInfo("gen-motion", "Generate motion samples", weight=30),
        StepInfo("gen-gps-iq", "Generate GPS IQ stream", weight=70),
    ]
    if reporter:
        reporter.on_setup_steps(steps)

    # Step: Generate motion samples
    with step_context(
        "gen-motion",
        reporter,
        "Generating motion samples",
        lambda: f"Generated {len(samples)} samples",
    ):
        samples = generate_motion_samples(request.route, request.profile, request.dt_s)
        if not samples:
            raise ValueError("no motion samples generated")
        if request.samples_path:
            _write_samples_csv(samples, request.samples_path)

    # Step: Generate GPS IQ stream
    with step_context(
        "gen-gps-iq",
        reporter,
        "Generating GPS IQ stream",
        "GPS IQ stream generated",
    ):
        iq_route_path = iq_generator.generate(
            samples,
            request.iq_route_path,
            start_time=request.start_time,
        )

    return GenResult(
        samples=samples,
        iq_route_path=iq_route_path,
        samples_path=request.samples_path,
    )


def _write_samples_csv(samples: list[MotionSample], out_path: str) -> None:
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="ascii", newline="") as handle:
        handle.write("t_s,lat,lon,alt_m,speed_mps,bearing_deg\n")
        for sample in samples:
            handle.write(
                f"{sample.t_s:.3f},{sample.lat:.8f},{sample.lon:.8f},"
                f"{sample.alt_m:.3f},{sample.speed_mps:.3f},{sample.bearing_deg:.3f}\n"
            )

