from core.gen.pipeline import GenerationPipeline
from core.gen.motion_generator import MotionGenerator
from core.play.plan import PlaybackPlan
from core.play.player import MotionPlayer
from core.play.playback import PlaybackOrchestrator
from core.route.models import Route


class RouteOrchestrator:
    def __init__(
        self,
        motion_gen: MotionGenerator,
        player: MotionPlayer,
        generator: GenerationPipeline | None = None,
        playback: PlaybackOrchestrator | None = None,
    ):
        self._motion_gen = motion_gen
        self._player = player
        self._generator = generator
        self._playback = playback

    async def run_demo(
        self,
        route: Route,
        start_idx: int = 0,
        end_idx: int | None = None,
        dt: float = 0.1,
        speed_multiplier: float = 1.0,
    ) -> None:
        plan = self._motion_gen.generate(route, start_idx, end_idx, dt=dt)
        await self._player.play(plan, speed_multiplier=speed_multiplier)

    async def run_live(
        self,
        route: Route,
        start_idx: int = 0,
        end_idx: int | None = None,
        dt: float = 0.1,
        fixed_duration_s: float = 60.0,
        speed_multiplier: float = 1.0,
    ) -> None:
        if self._generator is None or self._playback is None:
            raise RuntimeError("Live components not configured")
        result = await self._generator.generate(
            route,
            start_idx=start_idx,
            end_idx=end_idx,
            dt=dt,
            fixed_duration_s=fixed_duration_s,
        )
        plan = PlaybackPlan(
            motion=result.motion,
            iq_fixed_path=result.iq_fixed_path,
            iq_route_path=result.iq_route_path,
        )
        await self._playback.play(plan, speed_multiplier=speed_multiplier)
