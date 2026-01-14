from pydantic import BaseModel, Field, field_validator, model_validator
from typing import List, Dict, Union, Literal
from enum import Enum

class SimulationState(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"

class SimulationMode(str, Enum):
    DEMO = "demo"
    LIVE = "live"

class Waypoint(BaseModel):
    lat: float
    lon: float

class ConstantSpeedProfile(BaseModel):
    type: Literal['constant']
    params: Dict[str, float]

class RampToSpeedProfile(BaseModel):
    type: Literal['ramp_to']
    params: Dict[str, float]

class CruiseToSpeedProfile(BaseModel):
    type: Literal['cruise_to']
    params: Dict[str, float]

class StopAtEndSpeedProfile(BaseModel):
    type: Literal['stop_at_end']
    params: Dict[str, float]

SpeedProfile = Union[ConstantSpeedProfile, RampToSpeedProfile, CruiseToSpeedProfile, StopAtEndSpeedProfile]

class Segment(BaseModel):
    from_: int = Field(alias='from')
    to: int
    speedProfile: SpeedProfile
    class Config:
        populate_by_name = True
    @property
    def from_idx(self) -> int:
        return self.from_
    @field_validator('speedProfile', mode='before')
    @classmethod
    def validate_speed_profile(cls, v):
        if not isinstance(v, dict):
            raise ValueError("speedProfile must be an object")
        profile_type = v.get('type')
        params = v.get('params', {})
        if profile_type == 'constant':
            if 'speed_kmh' not in params:
                raise ValueError("constant profile requires speed_kmh")
            if params['speed_kmh'] < 0:
                raise ValueError("speed_kmh must be non-negative")
        elif profile_type == 'ramp_to':
            if 'target_kmh' not in params:
                raise ValueError("ramp_to profile requires target_kmh")
            if params['target_kmh'] < 0:
                raise ValueError("target_kmh must be non-negative")
        elif profile_type == 'cruise_to':
            if 'speed_kmh' not in params:
                raise ValueError("cruise_to profile requires speed_kmh")
            if params['speed_kmh'] < 0:
                raise ValueError("speed_kmh must be non-negative")
        elif profile_type == 'stop_at_end':
            if 'stop_duration_s' not in params:
                raise ValueError("stop_at_end profile requires stop_duration_s")
            if params['stop_duration_s'] < 0:
                raise ValueError("stop_duration_s must be non-negative")
        else:
            raise ValueError(f"Invalid profile type: {profile_type}")
        return v

class RouteDefinition(BaseModel):
    routeId: str
    waypoints: List[Waypoint]
    segments: List[Segment]
    @model_validator(mode='after')
    def validate_route(self):
        if not self.routeId or not self.routeId.strip():
            raise ValueError("routeId cannot be empty")
        if len(self.waypoints) < 2:
            raise ValueError("Route must have at least 2 waypoints")
        waypoint_count = len(self.waypoints)
        for seg in self.segments:
            from_idx = seg.from_
            if from_idx < 0 or from_idx >= waypoint_count:
                raise ValueError(f"Invalid segment from: {from_idx}")
            if seg.to < 0 or seg.to >= waypoint_count:
                raise ValueError(f"Invalid segment to: {seg.to}")
            if from_idx == seg.to:
                raise ValueError(f"Segment cannot connect waypoint to itself: {from_idx}")
        return self

class SimRunRequest(BaseModel):
    startSegmentIdx: int = 0
    endSegmentIdx: int | None = None
    mode: SimulationMode = SimulationMode.DEMO
    speedMultiplier: float = 1.0
    dryRun: bool | None = None
