from typing import Any

from app.schemas.route import RouteDefinition
from sim_core.route.models import Route, Segment, Waypoint
from sim_core.route.profiles import (
    ConstantSpeedProfile,
    CruiseToSpeedProfile,
    RampToSpeedProfile,
    SpeedProfile,
    StopAtEndSpeedProfile,
)


def to_core_route(route: RouteDefinition) -> Route:
    waypoints = [Waypoint(lat=wp.lat, lon=wp.lon) for wp in route.waypoints]
    segments = []
    for seg in route.segments:
        profile = _profile_from_any(seg.speedProfile)
        segments.append(
            Segment(
                from_idx=seg.from_,
                to_idx=seg.to,
                profile=profile,
            )
        )
    return Route(route_id=route.routeId, waypoints=waypoints, segments=segments)


def _profile_from_any(profile: Any) -> SpeedProfile:
    if isinstance(profile, dict):
        profile_type = profile.get("type")
        params = profile.get("params", {})
    else:
        profile_type = getattr(profile, "type", None)
        params = getattr(profile, "params", {}) or {}
    if profile_type == "constant":
        return ConstantSpeedProfile(speed_kmh=float(params["speed_kmh"]))
    if profile_type == "ramp_to":
        return RampToSpeedProfile(target_kmh=float(params["target_kmh"]))
    if profile_type == "cruise_to":
        return CruiseToSpeedProfile(speed_kmh=float(params["speed_kmh"]))
    if profile_type == "stop_at_end":
        return StopAtEndSpeedProfile(stop_duration_s=float(params["stop_duration_s"]))
    raise ValueError(f"Invalid speed profile type: {profile_type}")
