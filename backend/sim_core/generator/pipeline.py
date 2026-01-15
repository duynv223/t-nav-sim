from __future__ import annotations

from dataclasses import dataclass
import csv
from pathlib import Path

from sim_core.generator.artifacts import GenerationResult
from sim_core.generator.iq_generator import IqGenerator
from sim_core.generator.motion_generator import MotionGenerator
from sim_core.generator.nmea_generator import NmeaGenerator
from sim_core.route.models import Route, SegmentRange


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
        segment_range: SegmentRange | None = None,
        dt: float = 0.1,
        fixed_duration_s: float = 60.0,
    ) -> GenerationResult:
        if not route.segments:
            raise ValueError("Route has no segments")

        start = segment_range.start if segment_range is not None else 0
        end = segment_range.end if segment_range is not None else None
        if end is None:
            end = len(route.segments) - 1

        plan = self._motion_gen.generate(route, segment_range, dt=dt)

        output_dir = Path(self._config.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        # Example: route_id "Hanoi - QL1A #1" -> safe name "Hanoi_-_QL1A__1"
        route_tag = _safe_name(route.route_id)
        motion_path = output_dir / f"{route_tag}_motion.csv"
        nmea_route_path = output_dir / f"{route_tag}_route.nmea"
        nmea_fixed_path = output_dir / f"{route_tag}_fixed.nmea"
        iq_route_path = output_dir / f"{route_tag}_route.iq"
        iq_fixed_path = output_dir / f"{route_tag}_fixed.iq"

        _write_motion_csv(plan, motion_path)
        self._nmea_gen.generate(plan, str(nmea_route_path))
        start_wp = route.waypoints[route.segments[start].from_idx]
        self._nmea_gen.generate_fixed(
            start_wp.lat,
            start_wp.lon,
            duration_s=fixed_duration_s,
            dt=dt,
            out_path=str(nmea_fixed_path),
        )

        await self._iq_gen.generate_static(
            start_wp.lat,
            start_wp.lon,
            0.0,
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
            motion_path=str(motion_path),
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


def _write_motion_csv(plan, path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "t",
                "lat",
                "lon",
                "speed_mps",
                "bearing_deg",
                "segment_idx",
                "segment_progress",
            ]
        )
        for point in plan.points:
            writer.writerow(
                [
                    f"{point.t:.3f}",
                    f"{point.lat:.7f}",
                    f"{point.lon:.7f}",
                    f"{point.speed_mps:.3f}",
                    f"{point.bearing_deg:.2f}",
                    str(point.segment_idx),
                    f"{point.segment_progress:.4f}",
                ]
            )
