from __future__ import annotations

import asyncio
import logging
import shlex
from pathlib import Path
from typing import Iterable

logger = logging.getLogger(__name__)


class IqGenerator:
    def __init__(self, command: str = "gps-sdr-sim", extra_args: Iterable[str] | None = None):
        self._command = command
        self._extra_args = list(extra_args) if extra_args else []

    async def generate(
        self,
        nmea_path: str,
        out_path: str,
        sample_rate_hz: int = 2600000,
        duration_s: float | None = None,
    ) -> str:
        out_file = Path(out_path)
        out_file.parent.mkdir(parents=True, exist_ok=True)
        cmd = shlex.split(self._command) + [
            "-e",
            str(nmea_path),
            "-o",
            str(out_file),
            "-s",
            str(sample_rate_hz),
        ]
        if duration_s is not None:
            cmd.extend(["-d", f"{duration_s:.2f}"])
        cmd.extend(self._extra_args)
        logger.info("Generating IQ: %s", " ".join(cmd))
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            err = stderr.decode("utf-8", errors="replace").strip()
            raise RuntimeError(f"IQ generation failed: {err}")
        if stdout:
            logger.debug(stdout.decode("utf-8", errors="replace").strip())
        return str(out_file)
