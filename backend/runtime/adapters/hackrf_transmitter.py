from __future__ import annotations

import asyncio
import logging
import shlex

from sim_core.ports import GpsTransmitter

logger = logging.getLogger(__name__)


class HackrfTransmitter(GpsTransmitter):
    def __init__(
        self,
        command: str = "hackrf_transfer",
        freq_hz: int = 1575420000,
        sample_rate_hz: int = 2600000,
        txvga: int = 20,
        amp: bool = False,
    ):
        self._command = command
        self._freq_hz = freq_hz
        self._sample_rate_hz = sample_rate_hz
        self._txvga = txvga
        self._amp = amp
        self._proc: asyncio.subprocess.Process | None = None

    async def play_iq(self, iq_path: str) -> None:
        if self._proc is not None and self._proc.returncode is None:
            raise RuntimeError("HackRF playback already running")
        cmd = shlex.split(self._command) + [
            "-t",
            str(iq_path),
            "-f",
            str(self._freq_hz),
            "-s",
            str(self._sample_rate_hz),
            "-x",
            str(self._txvga),
        ]
        if self._amp:
            cmd.extend(["-a", "1"])
        logger.info("HackRF play: %s", " ".join(cmd))
        self._proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await self._proc.communicate()
        if self._proc.returncode != 0:
            err = stderr.decode("utf-8", errors="replace").strip()
            raise RuntimeError(f"HackRF playback failed: {err}")
        if stdout:
            logger.debug(stdout.decode("utf-8", errors="replace").strip())
        self._proc = None

    async def stop(self) -> None:
        if self._proc is None or self._proc.returncode is not None:
            return
        self._proc.terminate()
        try:
            await asyncio.wait_for(self._proc.wait(), timeout=2.0)
        except asyncio.TimeoutError:
            self._proc.kill()
            await self._proc.wait()
        self._proc = None
