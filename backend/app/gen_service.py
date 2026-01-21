from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from shutil import which
import logging

from app.app_settings import AppSettings
from dsim.adapters.iq_gps_sdr_sim import GpsSdrSimConfig, GpsSdrSimIqGenerator
from dsim.core.models import MotionSample
from dsim.core.models import Point, Route, SimpleMotionProfile
from dsim.core.port import IqGenerator
from dsim.core.use_cases.gen import GenRequest, generate_artifacts

from app.schemas import GenRequestPayload, MotionProfileParams

logger = logging.getLogger("sim.gen")


def run_gen(
    request: GenRequestPayload,
    session_root: Path,
    app_settings: AppSettings,
) -> tuple[Path, Path]:
    logger.info(
        "gen.run points=%d dt_s=%.3f start_time=%s",
        len(request.scenario.route.points),
        request.dt_s,
        request.start_time or "-",
    )
    route = _build_route(request.scenario.route.points)
    profile = _build_profile(request.scenario.motion_profile.params)

    outputs = request.outputs
    motion_path = _resolve_output(session_root, outputs.motion_csv, "motion.csv")
    iq_path = _resolve_output(session_root, outputs.iq, "route.iq")
    motion_tmp = _with_tmp_suffix(motion_path)
    iq_tmp = _with_tmp_suffix(iq_path)

    iq_generator = _select_iq_generator(app_settings)

    gen_request = GenRequest(
        route=route,
        profile=profile,
        dt_s=request.dt_s,
        start_time=_format_start_time(request.start_time),
        iq_route_path=str(iq_tmp),
        samples_path=str(motion_tmp),
    )
    try:
        generate_artifacts(gen_request, iq_generator=iq_generator)
        _promote_output(motion_tmp, motion_path)
        _promote_output(iq_tmp, iq_path)
        logger.info("gen.run.done motion_csv=%s iq=%s", motion_path, iq_path)
        return motion_path, iq_path
    except Exception:
        _cleanup_temp(motion_tmp)
        _cleanup_temp(iq_tmp)
        raise


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


def _select_iq_generator(app_settings: AppSettings) -> IqGenerator:
    iq_profile = app_settings.iq_generator
    ephemeris_path_value = _default_ephemeris_path()
    gps_sdr_sim_value = "gps-sdr-sim"
    ephemeris_path = Path(ephemeris_path_value)
    gps_sdr_sim_path = Path(gps_sdr_sim_value)
    resolved_gps_sdr_sim = None
    if gps_sdr_sim_path.exists():
        resolved_gps_sdr_sim = str(gps_sdr_sim_path)
    else:
        resolved_gps_sdr_sim = which(gps_sdr_sim_value)
    if not ephemeris_path.exists() or not resolved_gps_sdr_sim:
        logger.warning(
            "gen.run.iq_disabled ephemeris=%s gps_sdr_sim=%s",
            ephemeris_path_value,
            gps_sdr_sim_value,
        )
        return _NullIqGenerator()
    iq_config = GpsSdrSimConfig(
        ephemeris_path=str(ephemeris_path),
        gps_sdr_sim_path=str(resolved_gps_sdr_sim),
        output_sample_rate_hz=iq_profile.iq_sample_rate_hz,
        iq_bits=iq_profile.iq_bits,
    )
    return GpsSdrSimIqGenerator(iq_config)


def _default_ephemeris_path() -> str:
    try:
        import dsim
    except ImportError:
        base_dir = Path(__file__).resolve().parents[1]
        return str(base_dir / "assets" / "brdc0010.22n")
    assets_dir = Path(dsim.__file__).resolve().parent / "assets"
    return str(assets_dir / "brdc0010.22n")


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


def _with_tmp_suffix(path: Path) -> Path:
    suffix = path.suffix
    if suffix:
        return path.with_suffix(f"{suffix}.tmp")
    return path.with_suffix(".tmp")


def _cleanup_temp(path: Path) -> None:
    try:
        if path.exists():
            path.unlink()
    except Exception:
        logger.exception("Failed to cleanup temp output: %s", path)


def _promote_output(temp_path: Path, final_path: Path) -> None:
    if not temp_path.exists():
        return
    final_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path.replace(final_path)


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
