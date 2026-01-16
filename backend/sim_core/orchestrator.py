from sim_core.generate.generate_pipeline import GenerationPipeline
from sim_core.models.playback import PlaybackPlan
from sim_core.playback.runner import PlaybackRunner
from sim_core.route.models import Route, SegmentRange


class RoutePlaybackRunner:
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

