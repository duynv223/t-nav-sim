from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from core.ports import GpsTransmitter, SpeedBearingDevice

logger = logging.getLogger(__name__)


class DryRunGpsTransmitter(GpsTransmitter):
    def __init__(self, sample_rate_hz: int = 2600000, bytes_per_sample: int = 2):
        self._sample_rate_hz = sample_rate_hz
        self._bytes_per_sample = max(1, bytes_per_sample)

    async def play_iq(self, iq_path: str) -> None:
        duration_s = self._estimate_duration(iq_path)
        logger.info("DryRun GPS play: %s (%.2fs)", iq_path, duration_s)
        if duration_s > 0:
            await asyncio.sleep(duration_s)

    async def stop(self) -> None:
        return

    def _estimate_duration(self, iq_path: str) -> float:
        try:
            size = Path(iq_path).stat().st_size
        except OSError:
            return 0.0
        denom = float(self._sample_rate_hz * self._bytes_per_sample)
        if denom <= 0:
            return 0.0
        return size / denom


class DryRunSpeedBearingDevice(SpeedBearingDevice):
    def __init__(self):
        self._speed_kmh = 0.0
        self._bearing_deg = 0.0

    async def set_speed_kmh(self, kmh: float) -> None:
        self._speed_kmh = kmh

    async def set_bearing_deg(self, deg: float) -> None:
        self._bearing_deg = deg

    async def stop(self) -> None:
        self._speed_kmh = 0.0
