from __future__ import annotations

import sys
from pathlib import Path

from pydantic import BaseModel, Field, validator


REPO_DIR = Path(__file__).resolve().parents[2]
DSIM_SRC_DIR = REPO_DIR / "dsim" / "src"

if DSIM_SRC_DIR.exists() and str(DSIM_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(DSIM_SRC_DIR))


class IqGeneratorSettings(BaseModel):
    iq_bits: int = 8
    iq_sample_rate_hz: int = 2_600_000

    @validator("iq_bits")
    def _check_iq_bits(cls, value: int) -> int:
        if value not in {1, 8, 16}:
            raise ValueError("iq_bits must be 1, 8, or 16")
        return value

    @validator("iq_sample_rate_hz")
    def _check_iq_sample_rate(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("iq_sample_rate_hz must be > 0")
        return value


class GpsTransmitterSettings(BaseModel):
    center_freq_hz: int = 1_575_420_000
    sample_rate_hz: int = 2_600_000
    txvga_gain: int = 40
    amp_enabled: bool = True

    @validator("txvga_gain")
    def _check_txvga_gain(cls, value: int) -> int:
        if not 0 <= value <= 47:
            raise ValueError("txvga_gain must be between 0 and 47")
        return value


class ControllerSettings(BaseModel):
    port: str = "COM4"


class AppSettings(BaseModel):
    iq_generator: IqGeneratorSettings = Field(default_factory=IqGeneratorSettings)
    gps_transmitter: GpsTransmitterSettings = Field(default_factory=GpsTransmitterSettings)
    controller: ControllerSettings = Field(default_factory=ControllerSettings)
