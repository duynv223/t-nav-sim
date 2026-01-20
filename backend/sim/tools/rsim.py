from __future__ import annotations

import argparse
import csv
import shlex
import shutil
import sys
from collections.abc import Callable
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from adapters.gps_hackrf import HackrfGpsTransmitter, HackrfTxConfig
from adapters.iq_gps_sdr_sim import GpsSdrSimConfig, GpsSdrSimIqGenerator
from adapters.speed_bearing_serial import SpeedBearingSerialConfig, SerialSpeedBearingController
from core.models import MotionSample, Point, Route, SimpleMotionProfile
from core.reporting import ReporterProtocol, StepInfo, StepUpdate
from core.use_cases.gen import GenRequest, generate_artifacts
from core.use_cases.play import PlayRequest, play_simulation

DEFAULT_EPHEMERIS = ROOT_DIR / "assets" / "brdc0010.22n"
DEFAULT_GPS_SDR_SIM = Path(r"C:\gps-sdr-sim\gps-sdr-sim.exe")


class _ConsoleReporter(ReporterProtocol):
    def on_setup_steps(self, steps: list[StepInfo]) -> None:
        for step in steps:
            print(f"step={step.id} label={step.label} weight={step.weight}")

    def on_update(self, update: StepUpdate) -> None:
        msg = f"status={update.step_id}:{update.status.value} detail={update.detail}"
        if update.local_progress:
            msg += f" progress={update.local_progress}"
        print(msg)


class _NullGpsTransmitter:
    def play(self, iq_path: str) -> None:
        return None


class _NullController:
    def prepaire_start_deg(self, bearing_deg: float) -> None:
        return None

    def set_speed_kmh(self, speed_kmh: float) -> None:
        return None

    def set_bearing_deg(self, bearing_deg: float) -> None:
        return None

    def stop(self) -> None:
        return None

    def __enter__(self) -> "_NullController":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


def _parse_scalar(value: str) -> object:
    value = value.strip()
    if not value:
        return ""
    if " #" in value:
        value = value.split(" #", 1)[0].strip()
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        return value[1:-1]
    lowered = value.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    try:
        if any(ch in value for ch in ".eE"):
            return float(value)
        return int(value)
    except ValueError:
        return value


def _load_yaml_map(path: Path) -> dict:
    root: dict = {}
    stack: list[tuple[int, dict]] = [(0, root)]
    with path.open(encoding="ascii") as handle:
        for raw in handle:
            if not raw.strip() or raw.lstrip().startswith("#"):
                continue
            if "\t" in raw:
                raise ValueError("tabs are not allowed in project.yaml")
            indent = len(raw) - len(raw.lstrip(" "))
            line = raw.strip()
            key, sep, value = line.partition(":")
            if not sep:
                raise ValueError(f"invalid YAML line: {raw.rstrip()}")
            while stack and indent < stack[-1][0]:
                stack.pop()
            if not stack or indent != stack[-1][0]:
                raise ValueError(f"invalid indentation: {raw.rstrip()}")
            current = stack[-1][1]
            value = value.strip()
            if value == "":
                child: dict = {}
                current[key] = child
                stack.append((indent + 2, child))
            else:
                current[key] = _parse_scalar(value)
    return root


def _resolve_path(base_dir: Path, value: object | None, default: Path | None = None) -> Path | None:
    if value is None:
        return default
    if isinstance(value, str) and not value.strip():
        return default
    path = Path(str(value))
    if not path.is_absolute():
        path = base_dir / path
    return path


def _resolve_command(base_dir: Path, value: object | None, default: str) -> str:
    if value is None:
        return default
    if isinstance(value, str) and not value.strip():
        return default
    raw = str(value)
    path = Path(raw)
    if path.is_absolute():
        return str(path)
    if path.parent != Path("."):
        return str(base_dir / path)
    return raw


def _load_route_csv(path: Path) -> Route:
    with path.open(newline="", encoding="ascii") as handle:
        first_line = handle.readline().strip()
        if not first_line:
            raise ValueError("CSV file is empty")
        parts = [part.strip() for part in first_line.split(",")]
        has_header = False
        try:
            for part in parts:
                float(part)
        except ValueError:
            has_header = True

        points = []
        if has_header:
            handle.seek(0)
            reader = csv.DictReader(handle)
            if not reader.fieldnames:
                raise ValueError("CSV file is missing a header row")
            for row in reader:
                lat = row.get("lat") or row.get("latitude")
                lon = row.get("lon") or row.get("longitude")
                alt = row.get("alt_m") or row.get("alt") or row.get("altitude") or "0"
                if lat is None or lon is None:
                    raise ValueError("CSV rows must include lat/lon fields")
                points.append(Point(float(lat), float(lon), float(alt)))
        else:
            values = [float(part) for part in parts]
            if len(values) < 2:
                raise ValueError("CSV rows must include lat,lon[,alt]")
            alt = values[2] if len(values) > 2 else 0.0
            points.append(Point(values[0], values[1], alt))
            reader = csv.reader(handle)
            for row in reader:
                if not row:
                    continue
                values = [float(part.strip()) for part in row]
                if len(values) < 2:
                    raise ValueError("CSV rows must include lat,lon[,alt]")
                alt = values[2] if len(values) > 2 else 0.0
                points.append(Point(values[0], values[1], alt))
    return Route(points)


def _load_motion_samples_csv(path: Path) -> list[MotionSample]:
    with path.open(newline="", encoding="ascii") as handle:
        first_line = handle.readline().strip()
        if not first_line:
            raise ValueError("motion samples CSV is empty")
        parts = [part.strip() for part in first_line.split(",")]
        has_header = False
        try:
            for part in parts:
                float(part)
        except ValueError:
            has_header = True

        samples = []
        if has_header:
            handle.seek(0)
            reader = csv.DictReader(handle)
            if not reader.fieldnames:
                raise ValueError("motion samples CSV is missing a header row")
            for row in reader:
                t_s = row.get("t_s") or row.get("t")
                lat = row.get("lat") or row.get("latitude")
                lon = row.get("lon") or row.get("longitude")
                alt = row.get("alt_m") or row.get("alt") or row.get("altitude") or "0"
                speed = row.get("speed_mps") or row.get("speed")
                bearing = row.get("bearing_deg") or row.get("bearing")
                if t_s is None or lat is None or lon is None or speed is None or bearing is None:
                    raise ValueError("motion samples CSV is missing required fields")
                samples.append(
                    MotionSample(
                        t_s=float(t_s),
                        lat=float(lat),
                        lon=float(lon),
                        alt_m=float(alt),
                        speed_mps=float(speed),
                        bearing_deg=float(bearing),
                    )
                )
        else:
            values = [float(part) for part in parts]
            if len(values) < 5:
                raise ValueError("motion samples CSV rows must include t,lat,lon,speed,bearing")
            alt = values[3] if len(values) > 5 else 0.0
            samples.append(
                MotionSample(
                    t_s=values[0],
                    lat=values[1],
                    lon=values[2],
                    alt_m=alt,
                    speed_mps=values[-2],
                    bearing_deg=values[-1],
                )
            )
            reader = csv.reader(handle)
            for row in reader:
                if not row:
                    continue
                values = [float(part.strip()) for part in row]
                if len(values) < 5:
                    raise ValueError("motion samples CSV rows must include t,lat,lon,speed,bearing")
                alt = values[3] if len(values) > 5 else 0.0
                samples.append(
                    MotionSample(
                        t_s=values[0],
                        lat=values[1],
                        lon=values[2],
                        alt_m=alt,
                        speed_mps=values[-2],
                        bearing_deg=values[-1],
                    )
                )
    return samples


def _load_profile(data: dict) -> SimpleMotionProfile:
    profile_type = str(data.get("type", data.get("kind", "simple"))).lower()
    if profile_type not in {"simple", "simplemotionprofile"}:
        raise ValueError(f"unsupported profile type: {profile_type}")

    missing = [key for key in ("cruise_speed_kmh", "accel_mps2", "decel_mps2") if key not in data]
    if missing:
        raise ValueError(f"motion_profile missing required fields: {', '.join(missing)}")

    return SimpleMotionProfile(
        cruise_speed_kmh=float(data["cruise_speed_kmh"]),
        accel_mps2=float(data["accel_mps2"]),
        decel_mps2=float(data["decel_mps2"]),
        turn_slowdown_factor_per_deg=float(data.get("turn_slowdown_factor_per_deg", 0.0)),
        min_turn_speed_kmh=float(data.get("min_turn_speed_kmh", 0.0)),
        start_hold_s=float(data.get("start_hold_s", 0.0)),
        turn_rate_deg_s=float(data.get("turn_rate_deg_s", 0.0)),
        start_speed_kmh=float(data.get("start_speed_kmh", 0.0)),
        start_speed_s=float(data.get("start_speed_s", 0.0)),
    )


def _load_iq_config(project: dict, base_dir: Path) -> GpsSdrSimConfig:
    gps_sdr_sim_path = shutil.which("gps-sdr-sim")
    if gps_sdr_sim_path:
        gps_sdr_sim_default = gps_sdr_sim_path
    elif DEFAULT_GPS_SDR_SIM.exists():
        gps_sdr_sim_default = str(DEFAULT_GPS_SDR_SIM)
    else:
        gps_sdr_sim_default = "gps-sdr-sim"

    cfg = project.get("iq_generator", {})
    ephemeris = _resolve_path(base_dir, cfg.get("ephemeris_path"), DEFAULT_EPHEMERIS)
    print(ephemeris, DEFAULT_EPHEMERIS)
    gps_sdr_sim = _resolve_command(base_dir, cfg.get("gps_sdr_sim_path"), gps_sdr_sim_default)
    iq_bits = int(cfg.get("iq_bits", 8))
    iq_rate = int(cfg.get("iq_sample_rate_hz", 2_600_000))
    extra_args = cfg.get("extra_args", "")
    if isinstance(extra_args, str):
        extra_args_list = shlex.split(extra_args) if extra_args else []
    else:
        extra_args_list = [str(arg) for arg in extra_args]

    if ephemeris is None:
        raise ValueError("iq_generator.ephemeris_path is required")
    if gps_sdr_sim is None:
        raise ValueError("iq_generator.gps_sdr_sim_path is required")

    return GpsSdrSimConfig(
        gps_sdr_sim_path=str(gps_sdr_sim),
        ephemeris_path=str(ephemeris),
        output_sample_rate_hz=iq_rate,
        iq_bits=iq_bits,
        extra_args=extra_args_list,
    )


def _load_playback_config(
    project: dict,
    base_dir: Path,
) -> tuple[HackrfTxConfig | None, SpeedBearingSerialConfig | None]:
    playback = project.get("playback")
    if not isinstance(playback, dict):
        raise ValueError("playback section is required for play")

    gps_cfg = playback.get("gps_transmitter", {})
    gps_enabled = bool(gps_cfg.get("enabled", True))
    gps_config = None
    if gps_enabled:
        gps_kind = str(gps_cfg.get("kind", "hackrf")).lower()
        if gps_kind != "hackrf":
            raise ValueError(f"unsupported gps_transmitter kind: {gps_kind}")

        extra_args = gps_cfg.get("extra_args", "")
        if isinstance(extra_args, str):
            extra_args_list = shlex.split(extra_args) if extra_args else []
        else:
            extra_args_list = [str(arg) for arg in extra_args]

        gps_config = HackrfTxConfig(
            hackrf_transfer_path=_resolve_command(
                base_dir,
                gps_cfg.get("hackrf_transfer_path"),
                "hackrf_transfer",
            ),
            center_freq_hz=int(gps_cfg.get("center_freq_hz", 1_575_420_000)),
            sample_rate_hz=int(gps_cfg.get("sample_rate_hz", 2_600_000)),
            txvga_gain=int(gps_cfg.get("txvga_gain", 0)),
            amp_enabled=bool(gps_cfg.get("amp_enabled", False)),
            extra_args=extra_args_list,
        )

    ctrl_cfg = playback.get("controller", {})
    ctrl_enabled = bool(ctrl_cfg.get("enabled", True))
    ctrl_config = None
    if ctrl_enabled:
        ctrl_kind = str(ctrl_cfg.get("kind", "serial")).lower()
        if ctrl_kind != "serial":
            raise ValueError(f"unsupported controller kind: {ctrl_kind}")
        port = ctrl_cfg.get("port")
        if not port:
            raise ValueError("controller.port is required for play")

        ctrl_config = SpeedBearingSerialConfig(port=str(port))
    return gps_config, ctrl_config


def _sim_paths(project: dict, base_dir: Path) -> tuple[Path, Path, Path]:
    sim = project.get("sim_data_path", {})
    motion = sim.get("motion", "out/motion_samples.csv")
    route_iq = sim.get("route_iq", "out/route.iq")
    motion_path = _resolve_path(base_dir, motion)
    route_path = _resolve_path(base_dir, route_iq)
    if motion_path is None or route_path is None:
        raise ValueError("sim_data_path.motion/route_iq must be set")
    return motion_path, route_path


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Route simulation CLI using project.yaml.")
    sub = parser.add_subparsers(dest="command", required=True)

    gen = sub.add_parser("gen", help="Generate motion samples and IQ streams.")
    gen.add_argument("project", help="Path to project.yaml.")

    play = sub.add_parser("play", help="Play IQ streams and motion signals.")
    play.add_argument("project", help="Path to project.yaml.")

    return parser.parse_args(argv)


def _run_gen(project_path: Path) -> int:
    project = _load_yaml_map(project_path)
    base_dir = project_path.parent

    route_path = _resolve_path(base_dir, project.get("route"))
    if route_path is None:
        raise ValueError("route is required")
    route = _load_route_csv(route_path)

    profile_data = project.get("motion_profile")
    if not isinstance(profile_data, dict):
        raise ValueError("motion_profile section is required")
    profile = _load_profile(profile_data)

    dt_s = float(project.get("dt_s", 0.1))
    if abs(dt_s - 0.1) > 1e-6:
        raise ValueError("dt_s must be 0.1 to meet gps-sdr-sim 10Hz requirement")

    start_time = project.get("start_time")

    motion_path, route_path = _sim_paths(project, base_dir)
    iq_config = _load_iq_config(project, base_dir)
    iq_generator = GpsSdrSimIqGenerator(iq_config)

    request = GenRequest(
        route=route,
        profile=profile,
        dt_s=dt_s,
        start_time=str(start_time) if start_time else None,
        iq_route_path=str(route_path),
        samples_path=str(motion_path),
    )

    generate_artifacts(request, iq_generator=iq_generator, reporter=_ConsoleReporter())
    print(f"motion_samples={motion_path}")
    print(f"route_iq={route_path}")
    return 0


def _run_play(project_path: Path) -> int:
    project = _load_yaml_map(project_path)
    base_dir = project_path.parent

    motion_path, route_path = _sim_paths(project, base_dir)
    samples = _load_motion_samples_csv(motion_path)

    gps_config, ctrl_config = _load_playback_config(project, base_dir)
    if gps_config:
        gps_transmitter = HackrfGpsTransmitter(gps_config)
    else:
        gps_transmitter = _NullGpsTransmitter()

    request = PlayRequest(
        samples=samples,
        iq_route_path=str(route_path),
    )

    controller_ctx = (
        SerialSpeedBearingController(ctrl_config)
        if ctrl_config
        else _NullController()
    )
    with controller_ctx as controller:
        play_simulation(
            request,
            gps_transmitter=gps_transmitter,
            controller=controller,
            reporter=_ConsoleReporter(),
            on_motion=_motion_logger(),
        )
    return 0


def main(argv: list[str]) -> int:
    args = _parse_args(argv)
    project_path = Path(args.project)
    if not project_path.exists():
        raise FileNotFoundError(project_path)
    if args.command == "gen":
        return _run_gen(project_path)
    if args.command == "play":
        return _run_play(project_path)
    raise ValueError(f"unsupported command: {args.command}")


def _motion_logger() -> Callable[[MotionSample], None]:
    last_t = {"value": None}

    def _log(sample: MotionSample) -> None:
        if last_t["value"] is None or sample.t_s - last_t["value"] >= 0.1:
            last_t["value"] = sample.t_s
            print(
                "motion "
                f"t_s={sample.t_s:.1f} lat={sample.lat:.6f} lon={sample.lon:.6f} "
                f"alt_m={sample.alt_m:.1f} speed_mps={sample.speed_mps:.2f} "
                f"bearing_deg={sample.bearing_deg:.1f}"
            )

    return _log


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
