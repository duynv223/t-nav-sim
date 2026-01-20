from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = BASE_DIR.parent
DSIM_SRC_DIR = REPO_DIR / "dsim" / "src"

if DSIM_SRC_DIR.exists() and str(DSIM_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(DSIM_SRC_DIR))


@dataclass(frozen=True)
class Settings:
    session_root: Path
    gps_sdr_sim_path: str
    ephemeris_path: str
    iq_bits: int
    iq_sample_rate_hz: int
    enable_iq: bool
    app_settings_path: Path


def _env_path(name: str, default: Path) -> Path:
    raw = os.environ.get(name)
    if raw:
        return Path(raw)
    return default


def _env_flag(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() not in {"0", "false", "no", "off"}


def load_settings() -> Settings:
    session_root = _env_path("SIM_SESSION_ROOT", REPO_DIR / "var" / "sessions")
    gps_sdr_sim_path = os.environ.get("SIM_GPS_SDR_SIM_PATH", "gps-sdr-sim")
    ephemeris_path = _env_path("SIM_EPHEMERIS_PATH", _default_ephemeris_path())
    iq_bits = int(os.environ.get("SIM_IQ_BITS", "8"))
    iq_sample_rate_hz = int(os.environ.get("SIM_IQ_SAMPLE_RATE_HZ", "2600000"))
    enable_iq = _env_flag("SIM_ENABLE_IQ", True)
    app_settings_path = _env_path("SIM_SETTINGS_PATH", REPO_DIR / "settings.yaml")

    session_root.mkdir(parents=True, exist_ok=True)

    return Settings(
        session_root=session_root,
        gps_sdr_sim_path=gps_sdr_sim_path,
        ephemeris_path=str(ephemeris_path),
        iq_bits=iq_bits,
        iq_sample_rate_hz=iq_sample_rate_hz,
        enable_iq=enable_iq,
        app_settings_path=app_settings_path,
    )


def _default_ephemeris_path() -> Path:
    try:
        import dsim
    except ImportError:
        return BASE_DIR / "assets" / "brdc0010.22n"
    assets_dir = Path(dsim.__file__).resolve().parent / "assets"
    return assets_dir / "brdc0010.22n"
