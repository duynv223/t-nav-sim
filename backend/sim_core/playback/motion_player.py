import asyncio
import logging
from collections.abc import Awaitable, Callable

from sim_core.models.motion import MotionPlan, MotionPoint
from sim_core.ports import SpeedBearingDevice

logger = logging.getLogger(__name__)


PointCallback = Callable[[MotionPoint], Awaitable[None]]


class MotionPlayer:
    def __init__(
        self,
        device: SpeedBearingDevice,
        on_point: PointCallback | None = None,
    ):
        self._on_point = on_point
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
            await self._device.set_speed_kmh(point.speed_mps * 3.6)
            await self._device.set_bearing_deg(point.bearing_deg)
            if self._on_point is not None:
                await self._on_point(point)
        logger.debug("Motion play completed")

    async def stop(self) -> None:
        logger.debug("Motion stop requested")
        await self._device.stop()

