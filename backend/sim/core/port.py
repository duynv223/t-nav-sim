from __future__ import annotations

from typing import Callable, Iterable, Protocol

from core.models import MotionSample, Point


class IqGenerator(Protocol):
    def generate(
        self,
        samples: Iterable[MotionSample],
        out_path: str,
        start_time: str | None = None,
        on_progress: Callable[[float, float], None] | None = None,
    ) -> str:
        """Generate IQ stream for a route and return output path."""

    def generate_fixed(
        self,
        point: Point,
        duration_s: float,
        out_path: str,
        start_time: str | None = None,
        on_progress: Callable[[float, float], None] | None = None,
    ) -> str:
        """Generate IQ stream for a fixed position and return output path."""


class GpsTransmitter(Protocol):
    def play(self, iq_path: str) -> None:
        """Play an IQ stream (blocking)."""


class SpeedBearingController(Protocol):
    def prepaire_start_deg(self, bearing_deg: float) -> None:
        """Calibrate current heading to the given bearing."""

    def set_speed_kmh(self, speed_kmh: float) -> None:
        """Set speed output in km/h."""

    def set_bearing_deg(self, bearing_deg: float) -> None:
        """Set absolute bearing in degrees."""

    def stop(self) -> None:
        """Stop motion outputs."""
