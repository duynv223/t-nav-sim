import asyncio
import logging
from typing import Awaitable

from runtime.adapters.route_mapper import to_core_route
from runtime.adapters.ws_event_sink import NoClientsError, WsEventSink
from runtime.sim_factory import SimFactory
from runtime.sim_state import SimulationMode, SimulationState
from sim_core.player.playback import PlaybackRunner
from sim_core.route.models import SegmentRange

logger = logging.getLogger(__name__)

DEMO_SPEED_MULTIPLIER_DEFAULT = 10.0
LIVE_DT = 0.1
LIVE_FIXED_DURATION_S = 60.0


class SimManager:
    def __init__(self, hub, factory: SimFactory | None = None):
        self._hub = hub
        self._factory = factory or SimFactory()

        self._lock = asyncio.Lock()
        self._task: asyncio.Task[None] | None = None

        self._state = SimulationState.IDLE
        self._stop_requested = False

        # Only used for graceful stop() before task cancellation
        self._live_playback: PlaybackRunner | None = None

    # -----------------------------
    # Public API
    # -----------------------------
    def client_count(self) -> int:
        return self._hub.count()

    def get_state(self) -> SimulationState:
        return self._state

    async def run(
        self,
        route,
        segment_range: SegmentRange | None,
        mode: SimulationMode,
        speed_multiplier: float,
        dry_run: bool | None = None,
    ) -> tuple[str, float]:
        """
        Start a new simulation run.
        - Spawns a single background task that owns simulator lifecycle.
        - Returns a user-friendly mode string and effective speed multiplier.
        """
        async with self._lock:
            self._ensure_not_running()

            self._stop_requested = False
            self._live_playback = None
            await self._set_state(SimulationState.RUNNING)

            mode_str, eff_speed = self._describe_run(mode, speed_multiplier)

            self._task = asyncio.create_task(
                self._run_with_guard(
                    self._run_entrypoint(
                        route=route,
                        segment_range=segment_range,
                        mode=mode,
                        speed_multiplier=speed_multiplier,
                        dry_run=dry_run,
                    )
                )
            )

            return mode_str, eff_speed

    async def stop(self) -> SimulationState:
        """
        Stop the currently running simulation (if any).
        - Gracefully stops live playback if available
        - Cancels the background task
        - Sets state STOPPED
        """
        async with self._lock:
            if not self._task or self._task.done():
                logger.info("Stop requested but no simulation running")
                await self._set_state(SimulationState.IDLE)
                return self._state

            self._stop_requested = True

            # Graceful stop for LIVE playback (if started)
            if self._live_playback is not None:
                try:
                    await self._live_playback.stop()
                except Exception:
                    logger.exception("Failed to stop live playback gracefully")

            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                logger.info("Simulation stopped (manually)")

            self._task = None
            self._live_playback = None
            await self._set_state(SimulationState.STOPPED)
            return self._state

    # -----------------------------
    # Core worker (task entrypoint)
    # -----------------------------
    async def _run_entrypoint(
        self,
        *,
        route,
        segment_range: SegmentRange | None,
        mode: SimulationMode,
        speed_multiplier: float,
        dry_run: bool | None,
    ) -> None:
        """
        Runs inside background task. Owns simulator creation + execution.
        """
        events = WsEventSink(self.publish)
        core_route = to_core_route(route)

        if mode == SimulationMode.DEMO:
            eff_speed = self._normalize_speed_multiplier(speed_multiplier)
            simulator = self._factory.build_demo_runner(events)
            await simulator.run(
                core_route,
                segment_range=segment_range,
                speed_multiplier=eff_speed,
            )
            return

        # LIVE
        await events.on_state("preparing")
        resolved_dry_run = self._dry_run_or_default(dry_run)

        runner, playback = self._factory.build_live_runner(events, resolved_dry_run)
        self._live_playback = playback

        await runner.run(
            core_route,
            segment_range=segment_range,
            dt=LIVE_DT,
            fixed_duration_s=LIVE_FIXED_DURATION_S,
            speed_multiplier=1.0,
        )

    # -----------------------------
    # Guard / lifecycle
    # -----------------------------
    async def _run_with_guard(self, work: Awaitable[None]) -> None:
        try:
            await work
        except NoClientsError:
            logger.warning("All WebSocket clients disconnected. Stopping simulation.")
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Simulation crashed")
        finally:
            await self._cleanup_after_task()

    async def _cleanup_after_task(self) -> None:
        """
        Cleanup that must always happen at the end of the background task.
        Ensures playback is stopped and state is finalized.
        """
        # Ensure playback is stopped (defensive)
        if self._live_playback is not None:
            try:
                await self._live_playback.stop()
            except Exception:
                logger.exception("Failed to stop live playback in cleanup")
            finally:
                self._live_playback = None

        await self._finalize_run()

    async def _finalize_run(self) -> None:
        """
        If run completed naturally (not manually stopped), transition RUNNING -> IDLE.
        """
        if not self._stop_requested and self._state == SimulationState.RUNNING:
            await self._set_state(SimulationState.IDLE)

    def _ensure_not_running(self) -> None:
        if self._task and not self._task.done():
            logger.warning("Attempted to start simulation while one is already running")
            raise RuntimeError("Simulation already running")

    # -----------------------------
    # Publish + state
    # -----------------------------
    async def publish(self, payload: dict) -> bool:
        topic = payload.get("type")
        return (await self._hub.publish(payload, topic=topic)) > 0

    async def _set_state(self, state: SimulationState) -> None:
        self._state = state
        try:
            await self.publish({"type": "state", "state": state.value})
        except Exception:
            logger.exception("Failed to publish state update")
        logger.info("Simulation state changed to: %s", state.value)

    # -----------------------------
    # Small helpers
    # -----------------------------
    def _dry_run_or_default(self, dry_run: bool | None) -> bool:
        return True if dry_run is None else dry_run

    def _normalize_speed_multiplier(self, speed_multiplier: float) -> float:
        return speed_multiplier if speed_multiplier > 0 else DEMO_SPEED_MULTIPLIER_DEFAULT

    def _describe_run(self, mode: SimulationMode, speed_multiplier: float) -> tuple[str, float]:
        if mode == SimulationMode.DEMO:
            eff_speed = self._normalize_speed_multiplier(speed_multiplier)
            return f"DEMO (x{eff_speed})", eff_speed
        return "LIVE", 1.0


