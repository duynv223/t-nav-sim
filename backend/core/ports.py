from typing import Protocol

from core.gen.motion import MotionPoint


class EventSink(Protocol):
    async def on_state(self, state: str, detail: str | None = None) -> None:
        ...

    async def on_data(self, point: MotionPoint) -> None:
        ...


class SpeedBearingDevice(Protocol):
    async def set_speed_kmh(self, kmh: float) -> None:
        ...

    async def set_bearing_deg(self, deg: float) -> None:
        ...

    async def stop(self) -> None:
        ...


class GpsTransmitter(Protocol):
    async def play_iq(self, iq_path: str) -> None:
        ...

    async def stop(self) -> None:
        ...
