from __future__ import annotations

import math
from typing import List

from dsim.core.geo import bearing_deg, haversine_m, interpolate
from dsim.core.models import MotionProfile, MotionSample, Route, SimpleMotionProfile


def _turn_delta_deg(prev_bearing: float, next_bearing: float) -> float:
    return (next_bearing - prev_bearing + 180.0) % 360.0 - 180.0


def _turn_angle_deg(prev_bearing: float, next_bearing: float) -> float:
    return abs(_turn_delta_deg(prev_bearing, next_bearing))


def generate_motion_samples(
    route: Route,
    profile: MotionProfile,
    dt_s: float = 1.0,
) -> List[MotionSample]:
    if dt_s <= 0.0:
        raise ValueError("dt_s must be > 0")
    if not isinstance(profile, SimpleMotionProfile):
        raise NotImplementedError(f"Unsupported motion profile type: {type(profile).__name__}")
    if len(route.points) < 2:
        return []

    points = route.points
    seg_count = len(points) - 1
    seg_lengths_m: List[float] = []
    seg_bearings_deg: List[float] = []

    for idx in range(seg_count):
        a = points[idx]
        b = points[idx + 1]
        length = haversine_m(a.lat, a.lon, b.lat, b.lon)
        seg_lengths_m.append(length)
        seg_bearings_deg.append(bearing_deg(a.lat, a.lon, b.lat, b.lon))

    cruise_mps = profile.cruise_speed_kmh / 3.6
    min_turn_mps = max(profile.min_turn_speed_kmh, 1.0) / 3.6
    accel_mps2 = profile.accel_mps2
    decel_mps2 = profile.decel_mps2
    turn_rate_deg_s = profile.turn_rate_deg_s
    start_speed_s = profile.start_speed_s
    start_speed_kmh = profile.start_speed_kmh
    if turn_rate_deg_s < 0.0:
        raise ValueError("turn_rate_deg_s must be >= 0")

    seg_target_mps: List[float] = []
    for idx in range(seg_count):
        if idx == 0:
            target = cruise_mps
        else:
            turn_angle = _turn_angle_deg(seg_bearings_deg[idx - 1], seg_bearings_deg[idx])
            slow = cruise_mps - (profile.turn_slowdown_factor_per_deg * turn_angle) / 3.6
            target = max(min_turn_mps, slow)
        seg_target_mps.append(min(cruise_mps, max(0.0, target)))

    samples: List[MotionSample] = []
    t_s = 0.0
    speed_mps = 0.0

    samples.append(
        MotionSample(
            t_s=t_s,
            lat=points[0].lat,
            lon=points[0].lon,
            speed_mps=speed_mps,
            bearing_deg=seg_bearings_deg[0],
            alt_m=points[0].alt_m,
        )
    )

    if profile.start_hold_s < 0.0:
        raise ValueError("start_hold_s must be >= 0")
    if start_speed_s < 0.0:
        raise ValueError("start_speed_s must be >= 0")
    if start_speed_kmh < 0.0:
        raise ValueError("start_speed_kmh must be >= 0")

    if profile.start_hold_s > 0.0:
        hold_steps = int(math.ceil(profile.start_hold_s / dt_s))
        for _ in range(hold_steps):
            t_s += dt_s
            samples.append(
                MotionSample(
                    t_s=t_s,
                    lat=points[0].lat,
                    lon=points[0].lon,
                    speed_mps=0.0,
                    bearing_deg=seg_bearings_deg[0],
                    alt_m=points[0].alt_m,
                )
            )

    start_seg_idx = 0
    start_seg_offset_m = 0.0
    if start_speed_s > 0.0:
        if start_speed_kmh <= 0.0:
            raise ValueError("start_speed_kmh must be > 0 when start_speed_s > 0")
        start_speed_mps = min(start_speed_kmh, profile.cruise_speed_kmh) / 3.6
        remaining_s = start_speed_s
        seg_idx = 0
        seg_offset_m = 0.0
        while remaining_s > 0.0 and seg_idx < seg_count:
            seg_len = seg_lengths_m[seg_idx]
            if seg_len <= 0.0:
                seg_idx += 1
                seg_offset_m = 0.0
                continue
            start = points[seg_idx]
            end = points[seg_idx + 1]
            bearing = seg_bearings_deg[seg_idx]

            dt_eff = min(dt_s, remaining_s)
            step_m = start_speed_mps * dt_eff
            remaining_m = seg_len - seg_offset_m
            if step_m > remaining_m:
                step_m = remaining_m
                dt_eff = step_m / start_speed_mps

            if dt_eff <= 0.0 or step_m <= 0.0:
                break

            seg_offset_m += step_m
            ratio = seg_offset_m / seg_len
            lat, lon = interpolate(start.lat, start.lon, end.lat, end.lon, ratio)
            alt_m = start.alt_m + (end.alt_m - start.alt_m) * ratio
            t_s += dt_eff
            samples.append(
                MotionSample(
                    t_s=t_s,
                    lat=lat,
                    lon=lon,
                    speed_mps=start_speed_mps,
                    bearing_deg=bearing,
                    alt_m=alt_m,
                )
            )
            remaining_s -= dt_eff

            if seg_offset_m >= seg_len:
                seg_idx += 1
                seg_offset_m = 0.0

        speed_mps = start_speed_mps
        start_seg_idx = seg_idx
        start_seg_offset_m = seg_offset_m
        if start_seg_idx >= seg_count:
            return samples

    for idx in range(start_seg_idx, seg_count):
        seg_len = seg_lengths_m[idx]
        if seg_len <= 0.0:
            continue
        start = points[idx]
        end = points[idx + 1]
        bearing = seg_bearings_deg[idx]
        target_mps = seg_target_mps[idx]
        next_bearing = seg_bearings_deg[idx + 1] if idx + 1 < seg_count else None
        turn_delta = _turn_delta_deg(bearing, next_bearing) if next_bearing is not None else 0.0
        turn_angle = abs(turn_delta)
        turn_in_place = turn_rate_deg_s > 0.0 and turn_angle > 0.0
        next_target_mps = seg_target_mps[idx + 1] if idx + 1 < seg_count else 0.0
        if turn_in_place:
            next_target_mps = 0.0
        if speed_mps > target_mps:
            speed_mps = target_mps

        s_m = start_seg_offset_m if idx == start_seg_idx else 0.0
        if idx == start_seg_idx:
            start_seg_offset_m = 0.0
        while s_m < seg_len:
            rem_m = seg_len - s_m
            v_allow = math.sqrt(max(0.0, next_target_mps * next_target_mps + 2.0 * decel_mps2 * rem_m))
            desired_mps = min(target_mps, v_allow)

            if speed_mps < desired_mps:
                speed_mps = min(desired_mps, speed_mps + accel_mps2 * dt_s)
            elif speed_mps > desired_mps:
                speed_mps = max(desired_mps, speed_mps - decel_mps2 * dt_s)

            if speed_mps <= 0.0:
                if desired_mps <= 0.0:
                    break
                speed_mps = desired_mps

            step_m = min(speed_mps * dt_s, rem_m)
            if step_m <= 0.0:
                break

            s_m += step_m
            ratio = s_m / seg_len
            lat, lon = interpolate(start.lat, start.lon, end.lat, end.lon, ratio)
            alt_m = start.alt_m + (end.alt_m - start.alt_m) * ratio
            dt_eff = step_m / speed_mps
            t_s += dt_eff
            samples.append(
                MotionSample(
                    t_s=t_s,
                    lat=lat,
                    lon=lon,
                    speed_mps=speed_mps,
                    bearing_deg=bearing,
                    alt_m=alt_m,
                )
            )

        if turn_in_place:
            speed_mps = 1/3.6
            remaining = turn_angle
            direction = 1.0 if turn_delta >= 0.0 else -1.0
            turn_bearing = bearing
            while remaining > 0.0:
                step_angle = min(turn_rate_deg_s * dt_s, remaining)
                step_dt = step_angle / turn_rate_deg_s
                t_s += step_dt
                turn_bearing = (turn_bearing + direction * step_angle) % 360.0
                samples.append(
                    MotionSample(
                        t_s=t_s,
                        lat=end.lat,
                        lon=end.lon,
                        speed_mps=1/3.6,
                        bearing_deg=turn_bearing,
                        alt_m=end.alt_m,
                    )
                )
                remaining -= step_angle

    return samples
