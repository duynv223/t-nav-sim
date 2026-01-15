from pydantic import BaseModel, Field

from runtime.sim_state import SimulationMode


class SegmentRange(BaseModel):
    start: int = 0
    end: int | None = None


class SimRunRequest(BaseModel):
    segmentRange: SegmentRange = Field(default_factory=SegmentRange)
    mode: SimulationMode = SimulationMode.DEMO
    speedMultiplier: float = 1.0
    dryRun: bool | None = None
    enableGps: bool | None = None
    enableMotion: bool | None = None
