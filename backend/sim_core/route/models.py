from dataclasses import dataclass

from sim_core.route.profiles import SpeedProfile


@dataclass(frozen=True)
class Waypoint:
    lat: float
    lon: float


@dataclass(frozen=True)
class Segment:
    from_idx: int
    to_idx: int
    profile: SpeedProfile


@dataclass(frozen=True)
class Route:
    route_id: str
    waypoints: list[Waypoint]
    segments: list[Segment]

    def segment_count(self) -> int:
        return len(self.segments)

