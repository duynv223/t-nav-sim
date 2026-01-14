from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sim_core.generator.motion import MotionPlan

KNOTS_PER_MPS = 1.943844492


@dataclass(frozen=True)
class NmeaGeneratorConfig:
    talker: str = "GP"
    altitude_m: float = 0.0
    include_gga: bool = True


class NmeaGenerator:
    def __init__(self, config: NmeaGeneratorConfig | None = None):
        self._config = config or NmeaGeneratorConfig()

    def generate(self, plan: MotionPlan, out_path: str, start_time: datetime | None = None) -> str:
        start_time = start_time or datetime.now(timezone.utc)
        out_file = Path(out_path)
        out_file.parent.mkdir(parents=True, exist_ok=True)

        with out_file.open("w", encoding="ascii") as handle:
            for point in plan.points:
                ts = start_time + timedelta(seconds=point.t)
                handle.write(self._build_rmc(ts, point.lat, point.lon, point.speed_mps, point.bearing_deg))
                handle.write("\n")
                if self._config.include_gga:
                    handle.write(self._build_gga(ts, point.lat, point.lon, self._config.altitude_m))
                    handle.write("\n")

        return str(out_file)

    def generate_fixed(
        self,
        lat: float,
        lon: float,
        duration_s: float,
        dt: float,
        out_path: str,
        start_time: datetime | None = None,
    ) -> str:
        start_time = start_time or datetime.now(timezone.utc)
        out_file = Path(out_path)
        out_file.parent.mkdir(parents=True, exist_ok=True)
        steps = max(1, int(duration_s / max(0.001, dt)))

        with out_file.open("w", encoding="ascii") as handle:
            for i in range(steps):
                ts = start_time + timedelta(seconds=i * dt)
                handle.write(self._build_rmc(ts, lat, lon, 0.0, 0.0))
                handle.write("\n")
                if self._config.include_gga:
                    handle.write(self._build_gga(ts, lat, lon, self._config.altitude_m))
                    handle.write("\n")

        return str(out_file)

    def _build_rmc(
        self, ts: datetime, lat: float, lon: float, speed_mps: float, bearing_deg: float
    ) -> str:
        time_str = _format_time(ts)
        date_str = ts.strftime("%d%m%y")
        lat_str, ns = _format_lat(lat)
        lon_str, ew = _format_lon(lon)
        speed_knots = speed_mps * KNOTS_PER_MPS
        sentence = (
            f"{self._config.talker}RMC,{time_str},A,{lat_str},{ns},{lon_str},{ew},"
            f"{speed_knots:.2f},{bearing_deg:.2f},{date_str},,,A"
        )
        return _wrap_nmea(sentence)

    def _build_gga(self, ts: datetime, lat: float, lon: float, altitude_m: float) -> str:
        time_str = _format_time(ts)
        lat_str, ns = _format_lat(lat)
        lon_str, ew = _format_lon(lon)
        sentence = (
            f"{self._config.talker}GGA,{time_str},{lat_str},{ns},{lon_str},{ew},"
            f"1,08,1.0,{altitude_m:.1f},M,0.0,M,,"
        )
        return _wrap_nmea(sentence)


def _format_lat(lat: float) -> tuple[str, str]:
    hemisphere = "N" if lat >= 0 else "S"
    lat = abs(lat)
    degrees = int(lat)
    minutes = (lat - degrees) * 60.0
    return f"{degrees:02d}{minutes:07.4f}", hemisphere


def _format_lon(lon: float) -> tuple[str, str]:
    hemisphere = "E" if lon >= 0 else "W"
    lon = abs(lon)
    degrees = int(lon)
    minutes = (lon - degrees) * 60.0
    return f"{degrees:03d}{minutes:07.4f}", hemisphere


def _format_time(ts: datetime) -> str:
    centis = int(ts.microsecond / 10000)
    return ts.strftime("%H%M%S") + f".{centis:02d}"


def _wrap_nmea(sentence: str) -> str:
    checksum = _nmea_checksum(sentence)
    return f"${sentence}*{checksum}"


def _nmea_checksum(sentence: str) -> str:
    value = 0
    for ch in sentence:
        value ^= ord(ch)
    return f"{value:02X}"

