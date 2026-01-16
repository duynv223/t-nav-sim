from __future__ import annotations

from sim_core.models.motion import MotionPlan, MotionPoint
from sim_core.route.geo import bearing_degrees, haversine_meters
from sim_core.route.models import Route, SegmentRange
from sim_core.route.profiles import StopAtEndSpeedProfile


class MotionGenerator:
    def __init__(self, dt_default: float = 0.1, min_speed_mps: float = 0.0001):
        self._dt_default = dt_default
        self._min_speed_mps = min_speed_mps

    def generate(
        self,
        route: Route,
        segment_range: SegmentRange | None = None,
        dt: float | None = None,
    ) -> MotionPlan:
        if not route.segments:
            return MotionPlan(points=[])
        start = segment_range.start if segment_range is not None else 0
        end = segment_range.end if segment_range is not None else None
        if end is None:
            end = len(route.segments) - 1
        dt = dt if dt is not None else self._dt_default
        dt = max(0.001, dt)

        points: list[MotionPoint] = []
        prev_segment_end_speed = 0.0
        t_cursor = 0.0

        for seg_idx in range(start, end + 1):
            seg = route.segments[seg_idx]
            wp_from = route.waypoints[seg.from_idx]
            wp_to = route.waypoints[seg.to_idx]
            dist = haversine_meters(wp_from.lat, wp_from.lon, wp_to.lat, wp_to.lon)
            bearing = bearing_degrees(wp_from.lat, wp_from.lon, wp_to.lat, wp_to.lon)
            avg_speed = max(self._min_speed_mps, seg.profile.avg_speed(dist, prev_segment_end_speed))
            seg_time = dist / avg_speed if avg_speed > 0 else 0.0
            steps = max(1, int(seg_time / dt))
            for i in range(steps + 1):
                frac = i / steps
                distance_along = dist * frac
                lat = wp_from.lat + (wp_to.lat - wp_from.lat) * frac
                lon = wp_from.lon + (wp_to.lon - wp_from.lon) * frac
                time_in_seg = i * dt
                current_speed = seg.profile.speed_at(distance_along, dist, prev_segment_end_speed)
                if i == steps:
                    prev_segment_end_speed = current_speed
                points.append(
                    MotionPoint(
                        t=t_cursor + time_in_seg,
                        lat=lat,
                        lon=lon,
                        speed_mps=current_speed,
                        bearing_deg=bearing,
                        segment_idx=seg_idx,
                        segment_progress=frac,
                    )
                )

            t_cursor += steps * dt

            if isinstance(seg.profile, StopAtEndSpeedProfile) and seg.profile.stop_duration_s > 0:
                stop_steps = max(1, int(seg.profile.stop_duration_s / dt))
                for i in range(1, stop_steps + 1):
                    points.append(
                        MotionPoint(
                            t=t_cursor + i * dt,
                            lat=wp_to.lat,
                            lon=wp_to.lon,
                            speed_mps=0.0,
                            bearing_deg=bearing,
                            segment_idx=seg_idx,
                            segment_progress=1.0,
                        )
                    )
                t_cursor += stop_steps * dt
                prev_segment_end_speed = 0.0

        return MotionPlan(points=points)

