from dataclasses import dataclass
from pathlib import Path

import logging
from runtime.adapters.dryrun_devices import DryRunGpsTransmitter, DryRunSpeedBearingDevice
from runtime.adapters.hackrf_transmitter import HackrfTransmitter
from runtime.adapters.null_devices import NullGpsTransmitter, NullSpeedBearingDevice
from runtime.adapters.serial_speed_bearing import SerialSpeedBearingDevice
from sim_core.generator.iq_generator import IqGenerator
from sim_core.generator.motion_generator import MotionGenerator
from sim_core.generator.nmea_generator import NmeaGenerator
from sim_core.generator.pipeline import GenerationConfig, GenerationPipeline
from sim_core.pipeline import RouteDemoRunner, RouteLiveRunner
from sim_core.player.playback import PlaybackRunner
from sim_core.player.player import MotionPlayer


logger = logging.getLogger(__name__)

@dataclass(frozen=True)
class SimFactoryConfig:
    serial_port: str = "COM4"
    nav_path: str = str(Path(__file__).resolve().parent / "assets" / "brdc0010.22n")


class SimFactory:
    def __init__(self, config: SimFactoryConfig | None = None):
        self._config = config or SimFactoryConfig()

    def build_demo_runner(self, events) -> RouteDemoRunner:
        motion_gen = MotionGenerator()
        motion_player = MotionPlayer(events=events)
        return RouteDemoRunner(motion_gen, motion_player)

    def build_live_runner(
        self,
        events,
        dry_run: bool,
        enable_gps: bool = True,
        enable_motion: bool = True,
    ) -> tuple[RouteLiveRunner, PlaybackRunner]:
        gen_pipeline = self._build_generation_pipeline()
        gps, device = self._build_devices(dry_run, enable_gps, enable_motion)
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

    def _build_devices(self, dry_run: bool, enable_gps: bool, enable_motion: bool):
        logger.info(
            "Building devices: dry_run=%s enable_gps=%s enable_motion=%s",
            dry_run,
            enable_gps,
            enable_motion,
        )
        gps: HackrfTransmitter | DryRunGpsTransmitter | NullGpsTransmitter
        device: SerialSpeedBearingDevice | DryRunSpeedBearingDevice | NullSpeedBearingDevice

        if not enable_gps:
            gps = NullGpsTransmitter()
        elif dry_run:
            gps = DryRunGpsTransmitter()
        else:
            gps = HackrfTransmitter()

        if not enable_motion:
            device = NullSpeedBearingDevice()
        elif dry_run:
            device = DryRunSpeedBearingDevice()
        else:
            device = SerialSpeedBearingDevice(port=self._config.serial_port)

        return gps, device
