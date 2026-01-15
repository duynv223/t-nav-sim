import asyncio
import logging

from sim_core.player.plan import PlaybackPlan
from sim_core.player.player import MotionPlayer
from sim_core.ports import EventSink, GpsTransmitter

logger = logging.getLogger(__name__)


class PlaybackRunner:
    def __init__(
        self,
        gps: GpsTransmitter,
        motion_player: MotionPlayer,
        events: EventSink | None = None,
    ):
        self._gps = gps
        self._motion_player = motion_player
        self._events = events

    async def play(self, plan: PlaybackPlan, speed_multiplier: float = 1.0) -> None:
        logger.info("Playback start: speed_multiplier=%s", speed_multiplier)
        if self._events is not None:
            await self._events.on_state("gps_fixed")
        logger.info("Playback GPS fixed: %s", plan.iq_fixed_path)
        await self._gps.play_iq(plan.iq_fixed_path)
        if self._events is not None:
            await self._events.on_state("gps_route")
        logger.info("Playback GPS route: %s", plan.iq_route_path)
        gps_task = asyncio.create_task(self._gps.play_iq(plan.iq_route_path))
        motion_task = asyncio.create_task(
            self._motion_player.play(plan.motion, speed_multiplier=speed_multiplier)
        )
        try:
            await asyncio.gather(gps_task, motion_task)
        except Exception:
            logger.info("Playback failed")
            for task in (gps_task, motion_task):
                if not task.done():
                    task.cancel()
            await asyncio.gather(gps_task, motion_task, return_exceptions=True)
            raise
        if self._events is not None:
            await self._events.on_state("completed")
        logger.info("Playback completed")

    async def stop(self) -> None:
        logger.info("Playback stop requested")
        await asyncio.gather(
            self._gps.stop(),
            self._motion_player.stop(),
        )

