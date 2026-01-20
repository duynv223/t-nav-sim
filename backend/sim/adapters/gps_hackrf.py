from __future__ import annotations

import errno
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from core.port import GpsTransmitter


@dataclass(frozen=True)
class HackrfTxConfig:
    hackrf_transfer_path: str = "hackrf_transfer"
    center_freq_hz: int = 1_575_420_000
    sample_rate_hz: int = 2_600_000
    txvga_gain: int = 47
    amp_enabled: bool = True
    extra_args: Sequence[str] = ()


class HackrfGpsTransmitter(GpsTransmitter):
    def __init__(self, config: HackrfTxConfig) -> None:
        self._config = config

    def play(self, iq_path: str) -> None:
        if not Path(iq_path).exists():
            raise FileNotFoundError(iq_path)
        cmd = self._build_cmd(iq_path)
        _run(cmd)

    def _build_cmd(self, iq_path: str) -> list[str]:
        cmd = [
            self._config.hackrf_transfer_path,
            "-t",
            iq_path,
            "-f",
            str(self._config.center_freq_hz),
            "-s",
            str(self._config.sample_rate_hz),
            "-x",
            str(self._config.txvga_gain),
            "-a",
            "1" if self._config.amp_enabled else "0",
        ]
        if self._config.extra_args:
            cmd.extend(self._config.extra_args)
        return cmd


def _run(cmd: list[str]) -> None:
    print(f"Running command: {' '.join(cmd)}")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
    except FileNotFoundError as exc:
        print(f"Command not found: {cmd[0]}")
        raise FileNotFoundError(f"hackrf_transfer not found: {cmd[0]}") from exc
    if result.returncode != 0:
        if "hackrf_open() failed" in result.stderr:
            raise OSError(errno.ENODEV, "HackRF device not available.")
        raise RuntimeError(
            "hackrf_transfer failed\n"
            f"cmd: {' '.join(cmd)}\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )
