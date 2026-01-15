import asyncio
import logging

from sim_core.generator.motion import MotionPlan
from sim_core.ports import EventSink, SpeedBearingDevice

logger = logging.getLogger(__name__)


class MotionPlayer:
    def __init__(self, events: EventSink | None = None, device: SpeedBearingDevice | None = None):
        self._events = events
        self._device = device

    async def play(self, plan: MotionPlan, speed_multiplier: float = 1.0) -> None:
        logger.debug(
            "Motion play start: points=%s speed_multiplier=%s",
            len(plan.points),
            speed_multiplier,
        )
        speed_multiplier = max(0.001, speed_multiplier)
        last_t = None
        for point in plan.points:
            if last_t is not None:
                delay = (point.t - last_t) / speed_multiplier
                if delay > 0:
                    await asyncio.sleep(delay)
            last_t = point.t
            if self._device is not None:
                await self._device.set_speed_kmh(point.speed_mps * 3.6)
                await self._device.set_bearing_deg(point.bearing_deg)
            if self._events is not None:
                await self._events.on_data(point)
        logger.debug("Motion play completed")

    async def stop(self) -> None:
        logger.debug("Motion stop requested")
        if self._device is not None:
            await self._device.stop()

