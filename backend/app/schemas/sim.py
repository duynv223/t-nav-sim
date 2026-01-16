from pydantic import BaseModel, Field


class SegmentRange(BaseModel):
    start: int = 0
    end: int | None = None


class SimRunRequest(BaseModel):
    segmentRange: SegmentRange = Field(default_factory=SegmentRange)
    dryRun: bool | None = None
    enableGps: bool | None = None
    enableMotion: bool | None = None
