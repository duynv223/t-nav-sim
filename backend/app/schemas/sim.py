from pydantic import BaseModel

from runtime.sim_state import SimulationMode


class SimRunRequest(BaseModel):
    startSegmentIdx: int = 0
    endSegmentIdx: int | None = None
    mode: SimulationMode = SimulationMode.DEMO
    speedMultiplier: float = 1.0
    dryRun: bool | None = None
