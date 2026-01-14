from dataclasses import dataclass

from adapters.dryrun_devices import DryRunGpsTransmitter, DryRunSpeedBearingDevice
from adapters.hackrf_transmitter import HackrfTransmitter
from adapters.serial_speed_bearing import SerialSpeedBearingDevice
from core.gen.iq_generator import IqGenerator
from core.gen.motion_generator import MotionGenerator
from core.gen.nmea_generator import NmeaGenerator
from core.gen.pipeline import GenerationConfig, GenerationPipeline
from core.orchestrator import RouteDemoRunner, RouteLiveRunner
from core.play.playback import PlaybackRunner
from core.play.player import MotionPlayer


@dataclass(frozen=True)
class SimFactoryConfig:
    serial_port: str = "COM3"
    nav_path: str = "brdc3140.25n"


class SimFactory:
    def __init__(self, config: SimFactoryConfig | None = None):
        self._config = config or SimFactoryConfig()

    def build_demo_runner(self, events) -> RouteDemoRunner:
        motion_gen = MotionGenerator()
        motion_player = MotionPlayer(events=events)
        return RouteDemoRunner(motion_gen, motion_player)

    def build_live_runner(self, events, dry_run: bool) -> tuple[RouteLiveRunner, PlaybackRunner]:
        pipeline = self._build_pipeline()
        gps, device = self._build_devices(dry_run)
        motion_player = MotionPlayer(events=events, device=device)
        playback = PlaybackRunner(gps=gps, motion_player=motion_player, events=events)
        return RouteLiveRunner(pipeline, playback), playback

    def _build_pipeline(self) -> GenerationPipeline:
        return GenerationPipeline(
            MotionGenerator(),
            NmeaGenerator(),
            IqGenerator(nav_path=self._config.nav_path),
            GenerationConfig(),
        )

    def _build_devices(self, dry_run: bool):
        if dry_run:
            gps = DryRunGpsTransmitter()
            device = DryRunSpeedBearingDevice()
            return gps, device
        device = SerialSpeedBearingDevice(port=self._config.serial_port)
        gps = HackrfTransmitter()
        return gps, device
