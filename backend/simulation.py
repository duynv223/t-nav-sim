from typing import Awaitable, Callable, Optional
import asyncio
import logging
import math

from models import RouteDefinition, SimulationState
from utils import haversine_meters, bearing_degrees, kmh_to_mps

logger = logging.getLogger(__name__)

PublishFn = Callable[[dict], Awaitable[bool]]
SetStateFn = Callable[[SimulationState], Awaitable[None]]


class SimulationEngine:
    def __init__(self, publish: Optional[PublishFn] = None, set_sim_state: Optional[SetStateFn] = None):
        self._publish = publish
        self._set_sim_state = set_sim_state

    async def run_demo(
        self,
        route: RouteDefinition,
        start_seg_idx: int = 0,
        end_seg_idx: int | None = None,
        dt: float = 0.1,
        speed_multiplier: float = 1.0,
    ):
        start_time = asyncio.get_running_loop().time()
        elapsed = 0.0
        waypoints = route.waypoints
        if end_seg_idx is None:
            end_seg_idx = len(route.segments) - 1
        segments_to_run = route.segments[start_seg_idx:end_seg_idx + 1]
        prev_segment_end_speed = 0.0
        for seg_idx, s in enumerate(segments_to_run, start=start_seg_idx):
            wp_from = waypoints[s.from_]
            wp_to = waypoints[s.to]
            dist = haversine_meters(wp_from.lat, wp_from.lon, wp_to.lat, wp_to.lon)
            bearing = bearing_degrees(wp_from.lat, wp_from.lon, wp_to.lat, wp_to.lon)
            profile = s.speedProfile if isinstance(s.speedProfile, dict) else s.speedProfile.dict()
            params_str = ', '.join(f"{k}={v}" for k, v in profile['params'].items())
            logger.info(f"Executing Seg {seg_idx}: {s.from_} ƒ+' {s.to} | dist={dist:.1f}m | {profile['type']}({params_str}) | prev_speed={prev_segment_end_speed:.1f}m/s")
            if profile['type'] == 'constant':
                avg_speed = kmh_to_mps(profile['params']['speed_kmh'])
            elif profile['type'] == 'ramp_to':
                target_mps = kmh_to_mps(profile['params']['target_kmh'])
                avg_speed = (prev_segment_end_speed + target_mps) / 2
            elif profile['type'] == 'cruise_to':
                avg_speed = kmh_to_mps(profile['params']['speed_kmh']) * 0.85
            elif profile['type'] == 'stop_at_end':
                avg_speed = prev_segment_end_speed * 0.5 if prev_segment_end_speed > 0 else kmh_to_mps(20.0)
            else:
                avg_speed = kmh_to_mps(25.0)
            avg_speed = max(0.0001, avg_speed)
            seg_time = dist / avg_speed
            steps = max(1, int(seg_time / dt))
            for i in range(steps + 1):
                frac = i / steps
                distance_along = dist * frac
                lat = wp_from.lat + (wp_to.lat - wp_from.lat) * frac
                lon = wp_from.lon + (wp_to.lon - wp_from.lon) * frac
                t_now = asyncio.get_running_loop().time()
                elapsed = t_now - start_time
                time_in_seg = i * dt
                current_speed = self.sample_speed(profile, dist, distance_along, time_in_seg, prev_segment_end_speed)
                if i == steps:
                    prev_segment_end_speed = current_speed
                payload = {
                    "type": "data",
                    "t": round(elapsed, 3),
                    "lat": lat,
                    "lon": lon,
                    "speed": round(current_speed, 3),
                    "bearing": round(bearing, 2),
                    "segmentIdx": seg_idx,
                    "segmentProgress": round(frac, 3)
                }
                if self._publish is None:
                    raise RuntimeError("Publish callback is required for demo simulation")
                has_clients = await self._publish(payload)
                if not has_clients:
                    logger.warning("All WebSocket clients disconnected. Stopping simulation.")
                    if self._set_sim_state is not None:
                        await self._set_sim_state(SimulationState.IDLE)
                    return
                await asyncio.sleep(dt / speed_multiplier)
            if profile['type'] == 'stop_at_end' and profile['params'].get('stop_duration_s', 0) > 0:
                stop_duration = profile['params']['stop_duration_s']
                logger.info(f"Stopping at end of segment {seg_idx} for {stop_duration}s")
                await asyncio.sleep(stop_duration / speed_multiplier)
                prev_segment_end_speed = 0.0
        logger.info(f"Simulation Completed: {elapsed:.2f}s | {len(segments_to_run)} segments executed")
        if self._set_sim_state is not None:
            await self._set_sim_state(SimulationState.IDLE)

    @staticmethod
    def sample_speed(
        profile: dict,
        segment_distance: float,
        distance_along_segment: float,
        time_in_segment: float,
        prev_segment_speed: float = 0.0
    ) -> float:
        profile_type = profile['type']
        params = profile['params']
        DEFAULT_ACCEL = 2.0
        DEFAULT_DECEL = 3.0
        if profile_type == 'constant':
            return kmh_to_mps(params['speed_kmh'])
        elif profile_type == 'ramp_to':
            start_mps = prev_segment_speed
            target_mps = kmh_to_mps(params['target_kmh'])
            progress = distance_along_segment / segment_distance if segment_distance > 0 else 0
            return start_mps + (target_mps - start_mps) * progress
        elif profile_type == 'cruise_to':
            cruise_mps = kmh_to_mps(params['speed_kmh'])
            start_mps = prev_segment_speed
            if start_mps < cruise_mps:
                accel_time = (cruise_mps - start_mps) / DEFAULT_ACCEL
                accel_dist = start_mps * accel_time + 0.5 * DEFAULT_ACCEL * accel_time * accel_time
            else:
                accel_dist = 0
                start_mps = cruise_mps
            end_target_mps = cruise_mps * 0.5
            decel_time = (cruise_mps - end_target_mps) / DEFAULT_DECEL
            decel_dist = cruise_mps * decel_time - 0.5 * DEFAULT_DECEL * decel_time * decel_time
            if distance_along_segment < accel_dist:
                if accel_dist > 0:
                    t = math.sqrt(2 * distance_along_segment / DEFAULT_ACCEL) if distance_along_segment > 0 else 0
                    return start_mps + DEFAULT_ACCEL * t
                else:
                    return cruise_mps
            elif distance_along_segment < segment_distance - decel_dist:
                return cruise_mps
            else:
                remaining = segment_distance - distance_along_segment
                if remaining > 0 and decel_dist > 0:
                    v_squared = cruise_mps * cruise_mps - 2 * DEFAULT_DECEL * (decel_dist - remaining)
                    return math.sqrt(max(0, v_squared))
                else:
                    return end_target_mps
        elif profile_type == 'stop_at_end':
            start_mps = prev_segment_speed if prev_segment_speed > 0 else kmh_to_mps(25.0)
            stop_dist = (start_mps * start_mps) / (2 * DEFAULT_DECEL)
            if distance_along_segment < segment_distance - stop_dist:
                return start_mps
            else:
                remaining = segment_distance - distance_along_segment
                if remaining > 0:
                    v_squared = 2 * DEFAULT_DECEL * remaining
                    return math.sqrt(max(0, v_squared))
                else:
                    return 0.0
        return kmh_to_mps(25.0)

    async def run_live(
        self,
        route: RouteDefinition,
        start_seg_idx: int = 0,
        end_seg_idx: int | None = None,
    ):
        if end_seg_idx is None:
            end_seg_idx = len(route.segments) - 1
        segments_to_run = route.segments[start_seg_idx:end_seg_idx + 1]
        logger.info(f"LIVE simulation requested: {len(segments_to_run)} segments")
        if self._publish is not None:
            await self._publish({"type": "status", "stage": "preparing"})
        await asyncio.sleep(5)
        if self._publish is not None:
            await self._publish({"type": "status", "stage": "fail", "detail": "LIVE simulation not implemented"})
        logger.warning("LIVE simulation not yet implemented")
        if self._set_sim_state is not None:
            await self._set_sim_state(SimulationState.IDLE)
