from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class Point:
    lat: float
    lon: float
    alt_m: float = 0.0


@dataclass(frozen=True)
class Route:
    points: List[Point]


@dataclass(frozen=True, slots=True)
class MotionProfile:
    pass


@dataclass(frozen=True, slots=True)
class SimpleMotionProfile(MotionProfile):
    cruise_speed_kmh: float
    accel_mps2: float
    decel_mps2: float
    turn_slowdown_factor_per_deg: float = 0.0
    min_turn_speed_kmh: float = 0.0
    start_hold_s: float = 0.0
    turn_rate_deg_s: float = 0.0
    start_speed_kmh: float = 0.0
    start_speed_s: float = 0.0

# TODO: add other motion profile types (e.g., per-segment customization).


@dataclass(frozen=True)
class Scenario:
    route: Route
    motion: MotionProfile


@dataclass(frozen=True)
class MotionSample:
    t_s: float
    lat: float
    lon: float
    speed_mps: float
    bearing_deg: float
    alt_m: float = 0.0
