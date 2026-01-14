from dataclasses import dataclass

from core.gen.motion import MotionPlan


@dataclass(frozen=True)
class GenerationResult:
    motion: MotionPlan
    nmea_route_path: str
    nmea_fixed_path: str
    iq_route_path: str
    iq_fixed_path: str
    fixed_duration_s: float
