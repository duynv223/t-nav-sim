import asyncio
import logging

from models import SimulationMode, SimulationState
from simulation import SimulationEngine
from client_hub import get_client_hub

logger = logging.getLogger(__name__)


class SimulationService:
    def __init__(self, hub):
        self._hub = hub
        self._lock = asyncio.Lock()
        self._task = None
        self._state = SimulationState.IDLE

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

    async def run(self, route, start_idx: int, end_idx: int, mode: SimulationMode, speed_multiplier: float):
        async with self._lock:
            if self._task is not None and not self._task.done():
                logger.warning("Attempted to start simulation while one is already running")
                raise RuntimeError("Simulation already running")
            await self._set_state(SimulationState.RUNNING)
            loop = asyncio.get_running_loop()
            engine = SimulationEngine(
                publish=lambda obj: self.publish(obj),
                set_sim_state=lambda state: self._set_state(state),
            )
            if mode == SimulationMode.DEMO:
                speed_multiplier = speed_multiplier if speed_multiplier > 0 else 10.0
                task = loop.create_task(engine.run_demo(
                    route, start_idx, end_idx,
                    speed_multiplier=speed_multiplier,
                ))
                self._task = task
                mode_str = f"DEMO (x{speed_multiplier})"
            else:
                speed_multiplier = 1.0
                task = loop.create_task(engine.run_live(
                    route, start_idx, end_idx,
                ))
                self._task = task
                mode_str = "LIVE"
        return mode_str, speed_multiplier

    async def stop(self) -> SimulationState:
        async with self._lock:
            if self._task is None or self._task.done():
                logger.info("Stop requested but no simulation running")
                await self._set_state(SimulationState.IDLE)
                return self._state
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                logger.info("Simulation Stopped (manually)")
            self._task = None
            await self._set_state(SimulationState.STOPPED)
            return self._state


def get_sim_service(app) -> SimulationService:
    if not hasattr(app.state, "sim_service") or app.state.sim_service is None:
        hub = get_client_hub(app)
        app.state.sim_service = SimulationService(hub)
    return app.state.sim_service
