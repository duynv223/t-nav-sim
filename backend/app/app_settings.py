from __future__ import annotations

from pydantic import BaseModel, Field, root_validator, validator


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


class ControllerSettings(BaseModel):
    port: str = "COM4"


class AppSettings(BaseModel):
    iq_generator: IqGeneratorSettings = Field(default_factory=IqGeneratorSettings)
    gps_transmitter: GpsTransmitterSettings = Field(default_factory=GpsTransmitterSettings)
    controller: ControllerSettings = Field(default_factory=ControllerSettings)

    @root_validator(pre=True)
    def _normalize(cls, values: dict) -> dict:
        if not isinstance(values, dict):
            return values
        if "gps" in values and not any(
            key in values for key in ("iq_generator", "gps_transmitter", "controller")
        ):
            gps = values.get("gps") or {}
            return {
                "iq_generator": gps.get("iq_generator"),
                "gps_transmitter": gps.get("gps_transmitter"),
                "controller": gps.get("controller"),
            }
        return values
