from __future__ import annotations

import asyncio

from sim_core.ports import SpeedBearingDevice

try:
    import serial  # type: ignore
except ImportError:  # pragma: no cover
    serial = None


class SerialSpeedBearingDevice(SpeedBearingDevice):
    def __init__(
        self,
        port: str,
        baudrate: int = 115200,
        timeout_s: float = 1.0,
        newline: str = "\n",
    ):
        if serial is None:
            raise RuntimeError("pyserial is required for SerialSpeedBearingDevice")
        self._serial = serial.Serial(port=port, baudrate=baudrate, timeout=timeout_s)
        self._newline = newline
        self._lock = asyncio.Lock()

    async def set_speed_kmh(self, kmh: float) -> None:
        await self._send(f"speed_set {kmh:.2f}")

    async def set_bearing_deg(self, deg: float) -> None:
        await self._send(f"angle_set {deg:.2f}")

    async def stop(self) -> None:
        await self._send("speed_stop")
        await self._send("angle_stop")

    async def close(self) -> None:
        await asyncio.to_thread(self._serial.close)

    async def _send(self, command: str) -> None:
        data = (command + self._newline).encode("ascii")
        async with self._lock:
            await asyncio.to_thread(self._serial.write, data)
            await asyncio.to_thread(self._serial.flush)
