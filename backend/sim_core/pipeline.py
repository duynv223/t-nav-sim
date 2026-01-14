from sim_core.generator.pipeline import GenerationPipeline
from sim_core.generator.motion_generator import MotionGenerator
from sim_core.player.plan import PlaybackPlan
from sim_core.player.player import MotionPlayer
from sim_core.player.playback import PlaybackRunner
from sim_core.route.models import Route, SegmentRange


class RouteDemoRunner:
    def __init__(self, motion_gen: MotionGenerator, player: MotionPlayer):
        self._motion_gen = motion_gen
        self._player = player

    async def run(
        self,
        route: Route,
        segment_range: SegmentRange | None = None,
        dt: float = 0.1,
        speed_multiplier: float = 1.0,
    ) -> None:
        plan = self._motion_gen.generate(route, segment_range, dt=dt)
        await self._player.play(plan, speed_multiplier=speed_multiplier)


class RouteLiveRunner:
    def __init__(
        self,
        generator: GenerationPipeline,
        playback: PlaybackRunner,
    ):
        self._generator = generator
        self._playback = playback

    async def run(
        self,
        route: Route,
        segment_range: SegmentRange | None = None,
        dt: float = 0.1,
        fixed_duration_s: float = 60.0,
        speed_multiplier: float = 1.0,
    ) -> None:
        result = await self._generator.generate(
            route,
            segment_range=segment_range,
            dt=dt,
            fixed_duration_s=fixed_duration_s,
        )
        plan = PlaybackPlan(
            motion=result.motion,
            iq_fixed_path=result.iq_fixed_path,
            iq_route_path=result.iq_route_path,
        )
        await self._playback.play(plan, speed_multiplier=speed_multiplier)

