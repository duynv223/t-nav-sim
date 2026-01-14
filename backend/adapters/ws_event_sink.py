from core.gen.motion import MotionPoint
from core.ports import EventSink


class NoClientsError(RuntimeError):
    pass


class WsEventSink(EventSink):
    def __init__(self, publish):
        self._publish = publish

    async def on_state(self, state: str, detail: str | None = None) -> None:
        payload = {"type": "status", "stage": state}
        if detail:
            payload["detail"] = detail
        await self._publish(payload)

    async def on_data(self, point: MotionPoint) -> None:
        payload = {
            "type": "data",
            "t": round(point.t, 3),
            "lat": point.lat,
            "lon": point.lon,
            "speed": round(point.speed_mps, 3),
            "bearing": round(point.bearing_deg, 2),
            "segmentIdx": point.segment_idx,
            "segmentProgress": round(point.segment_progress, 3),
        }
        has_clients = await self._publish(payload)
        if not has_clients:
            raise NoClientsError("No WebSocket clients connected")
