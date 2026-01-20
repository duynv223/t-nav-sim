from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, root_validator, validator


class PointPayload(BaseModel):
    lat: float
    lon: float
    alt_m: float = 0.0


class RoutePayload(BaseModel):
    points: List[PointPayload]

    @validator("points")
    def _check_points(cls, value: List[PointPayload]) -> List[PointPayload]:
        if len(value) < 2:
            raise ValueError("route must have at least 2 points")
        return value


class MotionProfileParams(BaseModel):
    cruise_speed_kmh: float
    accel_mps2: float
    decel_mps2: float
    turn_slowdown_factor_per_deg: float = 0.0
    min_turn_speed_kmh: float = 0.0
    turn_rate_deg_s: float = 0.0
    start_hold_s: float = 0.0
    start_speed_kmh: float = 0.0
    start_speed_s: float = 0.0


class MotionProfilePayload(BaseModel):
    type: str = "simple"
    params: MotionProfileParams

    @root_validator(pre=True)
    def _normalize(cls, values: dict) -> dict:
        if not isinstance(values, dict):
            return values
        if "params" in values:
            profile_type = values.get("type") or values.get("kind") or "simple"
            return {"type": profile_type, "params": values.get("params")}
        raw = dict(values)
        profile_type = raw.pop("type", None) or raw.pop("kind", None) or "simple"
        params = {key: raw[key] for key in list(raw.keys())}
        return {"type": profile_type, "params": params}

    @validator("type")
    def _check_type(cls, value: str) -> str:
        if value.lower() != "simple":
            raise ValueError("only 'simple' motion profile is supported")
        return value


class ScenarioMetaPayload(BaseModel):
    id: Optional[str] = None
    name: Optional[str] = None
    created_at: Optional[str] = None
    app_version: Optional[str] = None


class ScenarioPayload(BaseModel):
    meta: Optional[ScenarioMetaPayload] = None
    route: RoutePayload
    motion_profile: MotionProfilePayload


class ScenarioEnvelope(BaseModel):
    schema_version: int = Field(1, ge=1)
    scenario: ScenarioPayload


class GenOutputsPayload(BaseModel):
    motion_csv: str = "motion.csv"
    iq: str = "route.iq"


class GenRequestPayload(ScenarioEnvelope):
    dt_s: float = 0.1
    start_time: Optional[str] = None
    outputs: GenOutputsPayload = GenOutputsPayload()

    @validator("dt_s")
    def _check_dt(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("dt_s must be > 0")
        return value


class SessionCreatePayload(BaseModel):
    name: Optional[str] = None


class SessionInfoPayload(BaseModel):
    session_id: str
    created_at: datetime
    work_dir: str
    name: Optional[str] = None


class GenResultPayload(BaseModel):
    session_id: str
    motion_csv: str
    iq: str
