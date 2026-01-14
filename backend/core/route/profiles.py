from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass

from core.route.geo import kmh_to_mps

DEFAULT_ACCEL_MPS2 = 2.0
DEFAULT_DECEL_MPS2 = 3.0


class SpeedProfile(ABC):
    @abstractmethod
    def speed_at(
        self, distance_along_m: float, segment_len_m: float, prev_speed_mps: float
    ) -> float:
        raise NotImplementedError

    @abstractmethod
    def avg_speed(self, segment_len_m: float, prev_speed_mps: float) -> float:
        raise NotImplementedError


@dataclass(frozen=True)
class ConstantSpeedProfile(SpeedProfile):
    speed_kmh: float

    def speed_at(self, distance_along_m: float, segment_len_m: float, prev_speed_mps: float) -> float:
        return kmh_to_mps(self.speed_kmh)

    def avg_speed(self, segment_len_m: float, prev_speed_mps: float) -> float:
        return kmh_to_mps(self.speed_kmh)


@dataclass(frozen=True)
class RampToSpeedProfile(SpeedProfile):
    target_kmh: float

    def speed_at(self, distance_along_m: float, segment_len_m: float, prev_speed_mps: float) -> float:
        start_mps = max(prev_speed_mps, 0.0)
        target_mps = kmh_to_mps(self.target_kmh)
        progress = distance_along_m / segment_len_m if segment_len_m > 0 else 0.0
        return start_mps + (target_mps - start_mps) * progress

    def avg_speed(self, segment_len_m: float, prev_speed_mps: float) -> float:
        target_mps = kmh_to_mps(self.target_kmh)
        return (prev_speed_mps + target_mps) / 2


@dataclass(frozen=True)
class CruiseToSpeedProfile(SpeedProfile):
    speed_kmh: float

    def speed_at(self, distance_along_m: float, segment_len_m: float, prev_speed_mps: float) -> float:
        cruise_mps = kmh_to_mps(self.speed_kmh)
        start_mps = prev_speed_mps
        if start_mps < cruise_mps:
            accel_time = (cruise_mps - start_mps) / DEFAULT_ACCEL_MPS2
            accel_dist = start_mps * accel_time + 0.5 * DEFAULT_ACCEL_MPS2 * accel_time * accel_time
        else:
            accel_dist = 0.0
            start_mps = cruise_mps
        end_target_mps = cruise_mps * 0.5
        decel_time = (cruise_mps - end_target_mps) / DEFAULT_DECEL_MPS2
        decel_dist = cruise_mps * decel_time - 0.5 * DEFAULT_DECEL_MPS2 * decel_time * decel_time
        if distance_along_m < accel_dist:
            if accel_dist > 0:
                t = math.sqrt(2 * distance_along_m / DEFAULT_ACCEL_MPS2) if distance_along_m > 0 else 0.0
                return start_mps + DEFAULT_ACCEL_MPS2 * t
            return cruise_mps
        if distance_along_m < segment_len_m - decel_dist:
            return cruise_mps
        remaining = segment_len_m - distance_along_m
        if remaining > 0 and decel_dist > 0:
            v_squared = cruise_mps * cruise_mps - 2 * DEFAULT_DECEL_MPS2 * (decel_dist - remaining)
            return math.sqrt(max(0.0, v_squared))
        return end_target_mps

    def avg_speed(self, segment_len_m: float, prev_speed_mps: float) -> float:
        return kmh_to_mps(self.speed_kmh) * 0.85


@dataclass(frozen=True)
class StopAtEndSpeedProfile(SpeedProfile):
    stop_duration_s: float

    def speed_at(self, distance_along_m: float, segment_len_m: float, prev_speed_mps: float) -> float:
        start_mps = prev_speed_mps if prev_speed_mps > 0 else kmh_to_mps(25.0)
        stop_dist = (start_mps * start_mps) / (2 * DEFAULT_DECEL_MPS2)
        if distance_along_m < segment_len_m - stop_dist:
            return start_mps
        remaining = segment_len_m - distance_along_m
        if remaining > 0:
            v_squared = 2 * DEFAULT_DECEL_MPS2 * remaining
            return math.sqrt(max(0.0, v_squared))
        return 0.0

    def avg_speed(self, segment_len_m: float, prev_speed_mps: float) -> float:
        if prev_speed_mps > 0:
            return prev_speed_mps * 0.5
        return kmh_to_mps(20.0)
