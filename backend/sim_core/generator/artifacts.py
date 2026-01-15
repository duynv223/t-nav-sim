from dataclasses import dataclass

from sim_core.generator.motion import MotionPlan


@dataclass(frozen=True)
class GenerationResult:
    motion: MotionPlan
    motion_path: str | None
    nmea_route_path: str
    nmea_fixed_path: str
    iq_route_path: str
    iq_fixed_path: str
    fixed_duration_s: float

