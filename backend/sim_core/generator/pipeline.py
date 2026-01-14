from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sim_core.generator.artifacts import GenerationResult
from sim_core.generator.iq_generator import IqGenerator
from sim_core.generator.motion_generator import MotionGenerator
from sim_core.generator.nmea_generator import NmeaGenerator
from sim_core.route.models import Route


@dataclass(frozen=True)
class GenerationConfig:
    output_dir: str = "output"
    sample_rate_hz: int = 2600000


class GenerationPipeline:
    def __init__(
        self,
        motion_gen: MotionGenerator,
        nmea_gen: NmeaGenerator,
        iq_gen: IqGenerator,
        config: GenerationConfig | None = None,
    ):
        self._motion_gen = motion_gen
        self._nmea_gen = nmea_gen
        self._iq_gen = iq_gen
        self._config = config or GenerationConfig()

    async def generate(
        self,
        route: Route,
        start_idx: int = 0,
        end_idx: int | None = None,
        dt: float = 0.1,
        fixed_duration_s: float = 60.0,
    ) -> GenerationResult:
        if not route.segments:
            raise ValueError("Route has no segments")
        if end_idx is None:
            end_idx = len(route.segments) - 1

        plan = self._motion_gen.generate(route, start_idx, end_idx, dt=dt)

        output_dir = Path(self._config.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        # Example: route_id "Hanoi - QL1A #1" -> safe name "Hanoi_-_QL1A__1"
        route_tag = _safe_name(route.route_id)
        nmea_route_path = output_dir / f"{route_tag}_route.nmea"
        nmea_fixed_path = output_dir / f"{route_tag}_fixed.nmea"
        iq_route_path = output_dir / f"{route_tag}_route.iq"
        iq_fixed_path = output_dir / f"{route_tag}_fixed.iq"

        self._nmea_gen.generate(plan, str(nmea_route_path))
        start_wp = route.waypoints[route.segments[start_idx].from_idx]
        self._nmea_gen.generate_fixed(
            start_wp.lat,
            start_wp.lon,
            duration_s=fixed_duration_s,
            dt=dt,
            out_path=str(nmea_fixed_path),
        )

        await self._iq_gen.generate(
            str(nmea_fixed_path),
            str(iq_fixed_path),
            sample_rate_hz=self._config.sample_rate_hz,
            duration_s=fixed_duration_s,
        )
        await self._iq_gen.generate(
            str(nmea_route_path),
            str(iq_route_path),
            sample_rate_hz=self._config.sample_rate_hz,
        )

        return GenerationResult(
            motion=plan,
            nmea_route_path=str(nmea_route_path),
            nmea_fixed_path=str(nmea_fixed_path),
            iq_route_path=str(iq_route_path),
            iq_fixed_path=str(iq_fixed_path),
            fixed_duration_s=fixed_duration_s,
        )


def _safe_name(route_id: str) -> str:
    # Keep only [A-Za-z0-9_-] for filenames; others become "_" to avoid filesystem issues.
    cleaned = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in route_id.strip())
    return cleaned or "route"

