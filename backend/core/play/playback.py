import asyncio

from core.play.plan import PlaybackPlan
from core.play.player import MotionPlayer
from core.ports import EventSink, GpsTransmitter


class PlaybackOrchestrator:
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
        if self._events is not None:
            await self._events.on_state("gps_fixed")
        await self._gps.play_iq(plan.iq_fixed_path)
        if self._events is not None:
            await self._events.on_state("gps_route")
        gps_task = asyncio.create_task(self._gps.play_iq(plan.iq_route_path))
        motion_task = asyncio.create_task(
            self._motion_player.play(plan.motion, speed_multiplier=speed_multiplier)
        )
        try:
            await asyncio.gather(gps_task, motion_task)
        except Exception:
            for task in (gps_task, motion_task):
                if not task.done():
                    task.cancel()
            await asyncio.gather(gps_task, motion_task, return_exceptions=True)
            raise
        if self._events is not None:
            await self._events.on_state("completed")

    async def stop(self) -> None:
        await asyncio.gather(
            self._gps.stop(),
            self._motion_player.stop(),
        )
