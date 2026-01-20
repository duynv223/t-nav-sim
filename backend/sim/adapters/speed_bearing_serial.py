from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

from core.port import SpeedBearingController

try:
    import serial
except ImportError as exc:  # pragma: no cover
    serial = None
    _IMPORT_ERROR = exc
else:
    _IMPORT_ERROR = None


@dataclass(frozen=True)
class SpeedBearingSerialConfig:
    port: str
    command_rate_hz: float = 1.0


class SerialSpeedBearingController(SpeedBearingController):
    def __init__(self, config: SpeedBearingSerialConfig) -> None:
        if serial is None:  # pragma: no cover
            raise ImportError("pyserial is required") from _IMPORT_ERROR
        self._config = config
        if config.command_rate_hz < 0.0:
            raise ValueError("command_rate_hz must be >= 0")
        self._min_interval_s = 1.0 / config.command_rate_hz if config.command_rate_hz > 0.0 else 0.0
        self._last_speed_send = 0.0
        self._last_bearing_send = 0.0
        self._serial = serial.Serial(
            port=config.port,
            baudrate=115200,
            timeout=1.0,
            write_timeout=1.0,
        )

    def close(self) -> None:
        if self._serial:
            self._serial.close()

    def prepaire_start_deg(self, bearing_deg: float) -> None:
        self._send(f"angle_calib {bearing_deg:.2f}")

    def set_speed_kmh(self, speed_kmh: float) -> None:
        if not self._throttle("speed"):
            return
        self._send(f"speed_set {speed_kmh:.3f}")

    def set_bearing_deg(self, bearing_deg: float) -> None:
        if not self._throttle("bearing"):
            return
        # print('set bearing:', bearing_deg)
        self._send(f"angle_set {bearing_deg:.2f}")

    def stop(self) -> None:
        self._send("speed_stop")
        self._send("angle_stop")

    def _send(self, command: str) -> None:
        payload = (command + "\n").encode("ascii")
        self._serial.write(payload)
        self._serial.flush()

    def _throttle(self, kind: str) -> bool:
        if self._min_interval_s <= 0.0:
            return True
        now = time.monotonic()
        last = self._last_speed_send if kind == "speed" else self._last_bearing_send
        if (now - last) < self._min_interval_s:
            return False
        if kind == "speed":
            self._last_speed_send = now
        else:
            self._last_bearing_send = now
        return True

    def __enter__(self) -> "SerialSpeedBearingController":
        return self

    def __exit__(self, exc_type, exc, tb) -> Optional[bool]:
        self.close()
        return None
