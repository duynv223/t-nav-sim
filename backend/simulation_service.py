import asyncio
import logging

from adapters.dryrun_devices import DryRunGpsTransmitter, DryRunSpeedBearingDevice
from adapters.hackrf_transmitter import HackrfTransmitter
from adapters.route_mapper import to_core_route
from adapters.serial_speed_bearing import SerialSpeedBearingDevice
from adapters.ws_event_sink import NoClientsError, WsEventSink
from client_hub import get_client_hub
from core.gen.iq_generator import IqGenerator
from core.gen.motion_generator import MotionGenerator
from core.gen.nmea_generator import NmeaGenerator
from core.gen.pipeline import GenerationConfig, GenerationPipeline
from core.orchestrator import RouteOrchestrator
from core.play.player import MotionPlayer
from core.play.playback import PlaybackOrchestrator
from models import SimulationMode, SimulationState

logger = logging.getLogger(__name__)

DEFAULT_SERIAL_PORT = "COM3"


class SimulationService:
    def __init__(self, hub):
        self._hub = hub
        self._lock = asyncio.Lock()
        self._task = None
        self._state = SimulationState.IDLE
        self._stop_requested = False
        self._live_playback: PlaybackOrchestrator | None = None

    def client_count(self) -> int:
        return self._hub.count()

    def get_state(self) -> SimulationState:
        return self._state

    async def _set_state(self, state: SimulationState) -> None:
        self._state = state
        payload = {
            "type": "state",
            "state": state.value
        }
        await self.publish(payload)
        logger.info(f"Simulation state changed to: {state.value}")

    async def publish(self, payload: dict) -> bool:
        topic = payload.get("type") if isinstance(payload, dict) else None
        sent = await self._hub.publish(payload, topic=topic)
        return sent > 0

    async def run(
        self,
        route,
        start_idx: int,
        end_idx: int,
        mode: SimulationMode,
        speed_multiplier: float,
        dry_run: bool | None = None,
    ):
        async with self._lock:
            if self._task is not None and not self._task.done():
                logger.warning("Attempted to start simulation while one is already running")
                raise RuntimeError("Simulation already running")
            self._stop_requested = False
            await self._set_state(SimulationState.RUNNING)
            loop = asyncio.get_running_loop()
            events = WsEventSink(lambda obj: self.publish(obj))
            self._live_playback = None
            simulator = RouteOrchestrator(MotionGenerator(), MotionPlayer(events=events))
            core_route = to_core_route(route)
            if mode == SimulationMode.DEMO:
                speed_multiplier = speed_multiplier if speed_multiplier > 0 else 10.0
                task = loop.create_task(
                    self._run_demo(
                        simulator,
                        core_route,
                        start_idx,
                        end_idx,
                        speed_multiplier,
                    )
                )
                self._task = task
                mode_str = f"DEMO (x{speed_multiplier})"
            else:
                speed_multiplier = 1.0
                task = loop.create_task(
                    self._run_live(
                        core_route,
                        start_idx,
                        end_idx,
                        events,
                        self._resolve_dry_run(dry_run),
                    )
                )
                self._task = task
                mode_str = "LIVE"
        return mode_str, speed_multiplier

    async def _run_demo(
        self,
        simulator: RouteOrchestrator,
        route,
        start_idx: int,
        end_idx: int,
        speed_multiplier: float,
    ) -> None:
        try:
            await simulator.run_demo(
                route,
                start_idx=start_idx,
                end_idx=end_idx,
                speed_multiplier=speed_multiplier,
            )
        except NoClientsError:
            logger.warning("All WebSocket clients disconnected. Stopping simulation.")
        except asyncio.CancelledError:
            raise
        finally:
            if not self._stop_requested and self._state == SimulationState.RUNNING:
                await self._set_state(SimulationState.IDLE)

    async def _run_live(
        self,
        route,
        start_idx: int,
        end_idx: int,
        events: WsEventSink,
        dry_run: bool,
    ) -> None:
        try:
            await events.on_state("preparing")
            orchestrator, playback = self._build_live_orchestrator(events, dry_run)
            self._live_playback = playback
            await orchestrator.run_live(
                route,
                start_idx=start_idx,
                end_idx=end_idx,
                dt=0.1,
                fixed_duration_s=60.0,
                speed_multiplier=1.0,
            )
        except NoClientsError:
            logger.warning("All WebSocket clients disconnected. Stopping simulation.")
        except asyncio.CancelledError:
            raise
        finally:
            print("Live simulation ended")
            if not self._stop_requested and self._state == SimulationState.RUNNING:
                await self._set_state(SimulationState.IDLE)

    async def stop(self) -> SimulationState:
        async with self._lock:
            if self._task is None or self._task.done():
                logger.info("Stop requested but no simulation running")
                await self._set_state(SimulationState.IDLE)
                return self._state
            self._stop_requested = True
            if self._live_playback is not None:
                await self._live_playback.stop()
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                logger.info("Simulation Stopped (manually)")
            self._task = None
            await self._set_state(SimulationState.STOPPED)
            return self._state

    def _resolve_dry_run(self, dry_run: bool | None) -> bool:
        if dry_run is not None:
            return dry_run
        return True

    def _build_live_orchestrator(
        self,
        events: WsEventSink,
        dry_run: bool,
    ) -> tuple[RouteOrchestrator, PlaybackOrchestrator]:
        motion_gen = MotionGenerator()
        pipeline = GenerationPipeline(
            motion_gen,
            NmeaGenerator(),
            IqGenerator(),
            GenerationConfig(),
        )

        if dry_run:
            gps = DryRunGpsTransmitter()
            device = DryRunSpeedBearingDevice()
        else:
            device = SerialSpeedBearingDevice(port=DEFAULT_SERIAL_PORT)
            gps = HackrfTransmitter()
        motion_player = MotionPlayer(events=events, device=device)
        playback = PlaybackOrchestrator(gps=gps, motion_player=motion_player, events=events)
        orchestrator = RouteOrchestrator(motion_gen, motion_player, pipeline, playback)
        return orchestrator, playback


def get_sim_service(app) -> SimulationService:
    if not hasattr(app.state, "sim_service") or app.state.sim_service is None:
        hub = get_client_hub(app)
        app.state.sim_service = SimulationService(hub)
    return app.state.sim_service
