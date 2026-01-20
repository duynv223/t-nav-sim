from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from shutil import which

from app.settings import Settings
from adapters.iq_gps_sdr_sim import GpsSdrSimConfig, GpsSdrSimIqGenerator
from core.models import MotionSample
from core.port import IqGenerator
from core.models import Point, Route, SimpleMotionProfile
from core.use_cases.gen import GenRequest, generate_artifacts

from app.schemas import GenRequestPayload, MotionProfileParams


def run_gen(request: GenRequestPayload, session_root: Path, settings: Settings) -> tuple[Path, Path]:
    route = _build_route(request.scenario.route.points)
    profile = _build_profile(request.scenario.motion_profile.params)

    outputs = request.outputs
    motion_path = _resolve_output(session_root, outputs.motion_csv, "motion.csv")
    iq_path = _resolve_output(session_root, outputs.iq, "route.iq")

    iq_generator = _select_iq_generator(settings)

    gen_request = GenRequest(
        route=route,
        profile=profile,
        dt_s=request.dt_s,
        start_time=_format_start_time(request.start_time),
        iq_route_path=str(iq_path),
        samples_path=str(motion_path),
    )

    generate_artifacts(gen_request, iq_generator=iq_generator)
    return motion_path, iq_path


def _build_route(points: list) -> Route:
    return Route([Point(lat=p.lat, lon=p.lon, alt_m=p.alt_m) for p in points])


def _build_profile(params: MotionProfileParams) -> SimpleMotionProfile:
    return SimpleMotionProfile(
        cruise_speed_kmh=params.cruise_speed_kmh,
        accel_mps2=params.accel_mps2,
        decel_mps2=params.decel_mps2,
        turn_slowdown_factor_per_deg=params.turn_slowdown_factor_per_deg,
        min_turn_speed_kmh=params.min_turn_speed_kmh,
        start_hold_s=params.start_hold_s,
        turn_rate_deg_s=params.turn_rate_deg_s,
        start_speed_kmh=params.start_speed_kmh,
        start_speed_s=params.start_speed_s,
    )

class _NullIqGenerator(IqGenerator):
    def generate(
        self,
        samples: list[MotionSample],
        out_path: str,
        start_time: str | None = None,
        on_progress=None,
    ) -> str:
        path = Path(out_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"")
        if on_progress:
            on_progress(1.0, 1.0)
        return str(path)

    def generate_fixed(
        self,
        point,
        duration_s: float,
        out_path: str,
        start_time: str | None = None,
        on_progress=None,
    ) -> str:
        path = Path(out_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"")
        if on_progress:
            on_progress(1.0, 1.0)
        return str(path)


def _select_iq_generator(settings: Settings) -> IqGenerator:
    if not settings.enable_iq:
        return _NullIqGenerator()
    ephemeris_path = Path(settings.ephemeris_path)
    gps_sdr_sim_path = Path(settings.gps_sdr_sim_path)
    resolved_gps_sdr_sim = None
    if gps_sdr_sim_path.exists():
        resolved_gps_sdr_sim = str(gps_sdr_sim_path)
    else:
        resolved_gps_sdr_sim = which(settings.gps_sdr_sim_path)
    if not ephemeris_path.exists() or not resolved_gps_sdr_sim:
        return _NullIqGenerator()
    iq_config = GpsSdrSimConfig(
        ephemeris_path=settings.ephemeris_path,
        gps_sdr_sim_path=str(resolved_gps_sdr_sim),
        output_sample_rate_hz=settings.iq_sample_rate_hz,
        iq_bits=settings.iq_bits,
    )
    return GpsSdrSimIqGenerator(iq_config)


def _resolve_output(session_root: Path, value: str, fallback: str) -> Path:
    raw = value.strip() if isinstance(value, str) else ""
    name = raw or fallback
    path = Path(name)
    if path.is_absolute():
        raise ValueError("output paths must be relative")
    if ".." in path.parts:
        raise ValueError("output paths must not include '..'")
    output_path = (session_root / "out" / path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    return output_path


def _format_start_time(value: str | None) -> str | None:
    if not value:
        return None
    raw = value.strip()
    if not raw:
        return None
    if "/" in raw and "," in raw:
        return raw
    cleaned = raw.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(cleaned)
    except ValueError as exc:
        raise ValueError(f"Invalid start_time format: {value}") from exc
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed.strftime("%Y/%m/%d,%H:%M:%S")
