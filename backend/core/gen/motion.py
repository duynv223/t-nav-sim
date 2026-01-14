from dataclasses import dataclass


@dataclass(frozen=True)
class MotionPoint:
    t: float
    lat: float
    lon: float
    speed_mps: float
    bearing_deg: float
    segment_idx: int
    segment_progress: float


@dataclass(frozen=True)
class MotionPlan:
    points: list[MotionPoint]

    def duration_s(self) -> float:
        if not self.points:
            return 0.0
        return self.points[-1].t
