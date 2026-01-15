from dataclasses import dataclass
from pathlib import Path

from runtime.adapters.dryrun_devices import DryRunGpsTransmitter, DryRunSpeedBearingDevice
from runtime.adapters.hackrf_transmitter import HackrfTransmitter
from runtime.adapters.serial_speed_bearing import SerialSpeedBearingDevice
from sim_core.generator.iq_generator import IqGenerator
from sim_core.generator.motion_generator import MotionGenerator
from sim_core.generator.nmea_generator import NmeaGenerator
from sim_core.generator.pipeline import GenerationConfig, GenerationPipeline
from sim_core.pipeline import RouteDemoRunner, RouteLiveRunner
from sim_core.player.playback import PlaybackRunner
from sim_core.player.player import MotionPlayer


@dataclass(frozen=True)
class SimFactoryConfig:
    serial_port: str = "COM3"
    nav_path: str = str(Path(__file__).resolve().parent / "assets" / "brdc3140.25n")


class SimFactory:
    def __init__(self, config: SimFactoryConfig | None = None):
        self._config = config or SimFactoryConfig()

    def build_demo_runner(self, events) -> RouteDemoRunner:
        motion_gen = MotionGenerator()
        motion_player = MotionPlayer(events=events)
        return RouteDemoRunner(motion_gen, motion_player)

    def build_live_runner(self, events, dry_run: bool) -> tuple[RouteLiveRunner, PlaybackRunner]:
        gen_pipeline = self._build_generation_pipeline()
        gps, device = self._build_devices(dry_run)
        motion_player = MotionPlayer(events=events, device=device)
        playback = PlaybackRunner(gps=gps, motion_player=motion_player, events=events)
        return RouteLiveRunner(gen_pipeline, playback), playback

    def _build_generation_pipeline(self) -> GenerationPipeline:
        output_dir = Path(__file__).resolve().parent / "artifacts"
        return GenerationPipeline(
            MotionGenerator(),
            NmeaGenerator(),
            IqGenerator(nav_path=self._config.nav_path),
            GenerationConfig(output_dir=str(output_dir)),
        )

    def _build_devices(self, dry_run: bool):
        if dry_run:
            gps = DryRunGpsTransmitter()
            device = DryRunSpeedBearingDevice()
            return gps, device
        device = SerialSpeedBearingDevice(port=self._config.serial_port)
        gps = HackrfTransmitter()
        return gps, device
