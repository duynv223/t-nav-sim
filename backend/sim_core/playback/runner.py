import asyncio
import logging

from sim_core.models.playback import PlaybackPlan
from sim_core.playback.motion_player import MotionPlayer
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

    async def change_status(self, status: str) -> None:
        if self._events is not None:
            await self._events.on_state(status)

    async def play(self, plan: PlaybackPlan, speed_multiplier: float = 1.0) -> None:
        # Initialize position by playing fixed IQ data
        logger.info("Playback GPS fixed: %s", plan.iq_fixed_path)
        await self.change_status("gps_fixed")
        await self._gps.play_iq(plan.iq_fixed_path)

        # Playback gps and motion concurrently
        logger.info("Playback start: speed_multiplier=%s", speed_multiplier)
        await self.change_status("gps_route")
        gps_task = asyncio.create_task(self._gps.play_iq(plan.iq_route_path))
        motion_task = asyncio.create_task(
            self._motion_player.play(plan.motion, speed_multiplier=speed_multiplier)
        )
        try:
            await asyncio.gather(gps_task, motion_task)
        except Exception:
            logger.error("Playback failed")
            for task in (gps_task, motion_task):
                if not task.done():
                    task.cancel()
            await asyncio.gather(gps_task, motion_task, return_exceptions=True)
            raise
        await self.change_status("completed")
        logger.info("Playback completed")

    async def stop(self) -> None:
        logger.info("Playback stop requested")
        await asyncio.gather(
            self._gps.stop(),
            self._motion_player.stop(),
        )

