from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Sequence

from core.models import MotionSample, Point
from core.port import IqGenerator


@dataclass(frozen=True)
class GpsSdrSimConfig:
    ephemeris_path: str
    gps_sdr_sim_path: str = "gps-sdr-sim"
    output_sample_rate_hz: int = 2_600_000
    iq_bits: int = 8
    extra_args: Sequence[str] = ()


class GpsSdrSimIqGenerator(IqGenerator):
    def __init__(self, config: GpsSdrSimConfig) -> None:
        self._config = config

    def generate(
        self,
        samples: Iterable[MotionSample],
        out_path: str,
        start_time: str | None = None,
        on_progress: Callable[[float, float], None] | None = None,
    ) -> str:
        samples_list = list(samples)
        if not samples_list:
            raise ValueError("samples must not be empty")

        trajectory_path = self._trajectory_path(out_path)
        _write_lla_trajectory(samples_list, trajectory_path)
        cmd = self._base_cmd(out_path, start_time)
        cmd.extend(["-x", str(trajectory_path)])
        cmd.extend(self._config.extra_args)
        duration_s = max(0.0, samples_list[-1].t_s - samples_list[0].t_s)
        _run(cmd, duration_s, on_progress)

        trajectory_path.unlink(missing_ok=True)

        return str(out_path)

    def generate_fixed(
        self,
        point: Point,
        duration_s: float,
        out_path: str,
        start_time: str | None = None,
        on_progress: Callable[[float, float], None] | None = None,
    ) -> str:
        if duration_s <= 0:
            raise ValueError("duration_s must be > 0")

        cmd = self._base_cmd(out_path, start_time)
        cmd.extend(["-l", f"{point.lat},{point.lon},{point.alt_m}"])
        cmd.extend(["-d", str(int(round(duration_s)))])
        cmd.extend(self._config.extra_args)
        _run(cmd, duration_s, on_progress)
        return str(out_path)

    def _base_cmd(self, out_path: str, start_time: str | None) -> list[str]:
        _ensure_file(self._config.gps_sdr_sim_path)
        _ensure_file(self._config.ephemeris_path)
        if self._config.iq_bits not in {1, 8, 16}:
            raise ValueError("iq_bits must be 1, 8, or 16 for gps-sdr-sim")
        out_path = str(out_path)
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)

        cmd = [
            self._config.gps_sdr_sim_path,
            "-e",
            self._config.ephemeris_path,
            "-o",
            out_path,
            "-s",
            str(self._config.output_sample_rate_hz),
            "-b",
            str(self._config.iq_bits),
        ]
        if start_time:
            cmd.extend(["-t", start_time, "-T", start_time])
        return cmd

    def _trajectory_path(self, out_path: str) -> Path:
        out = Path(out_path)
        if out.suffix:
            return out.with_suffix(out.suffix + ".traj")
        return out.with_suffix(".traj")


def _ensure_file(path: str) -> None:
    if not Path(path).exists():
        raise FileNotFoundError(path)


def _run(
    cmd: list[str],
    expected_duration_s: float,
    on_progress: Callable[[float, float], None] | None,
) -> None:
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    start = time.monotonic()
    if on_progress and expected_duration_s > 0:
        on_progress(0.0, expected_duration_s)
        while proc.poll() is None:
            elapsed = time.monotonic() - start
            on_progress(min(elapsed, expected_duration_s), expected_duration_s)
            time.sleep(1.0)
    stdout, stderr = proc.communicate()
    if on_progress and expected_duration_s > 0:
        on_progress(expected_duration_s, expected_duration_s)
    if proc.returncode != 0:
        raise RuntimeError(
            "gps-sdr-sim failed\n"
            f"cmd: {' '.join(cmd)}\n"
            f"stdout: {stdout}\n"
            f"stderr: {stderr}"
        )


def _write_lla_trajectory(samples: list[MotionSample], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="ascii", newline="") as handle:
        for sample in sorted(samples, key=lambda s: s.t_s):
            handle.write(
                f"{sample.t_s:.3f},{sample.lat:.8f},{sample.lon:.8f},{sample.alt_m:.3f}\n"
            )
