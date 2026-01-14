from dataclasses import dataclass

from core.gen.motion import MotionPlan


@dataclass(frozen=True)
class PlaybackPlan:
    motion: MotionPlan
    iq_fixed_path: str
    iq_route_path: str
