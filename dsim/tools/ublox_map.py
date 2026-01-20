from __future__ import annotations

import sys
import argparse
import json
import threading
import time
import webbrowser
from datetime import datetime, timezone
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

try:
    import serial
except ImportError as exc:  # pragma: no cover
    serial = None
    _IMPORT_ERROR = exc
else:
    _IMPORT_ERROR = None


HTML_TEMPLATE = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <title>u-blox M7 Map</title>
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <link
      rel="stylesheet"
      href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
      integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY="
      crossorigin=""
    />
    <style>
      html, body, #map { height: 100%; margin: 0; }
      .status {
        position: absolute;
        top: 12px;
        left: 12px;
        z-index: 1000;
        background: rgba(255, 255, 255, 0.9);
        border-radius: 6px;
        padding: 8px 10px;
        font: 14px/1.4 Arial, sans-serif;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
      }
      .status strong { display: block; }
    </style>
  </head>
  <body>
    <div id="map"></div>
    <div class="status">
      <strong id="status">Waiting for fix...</strong>
      <div id="detail"></div>
    </div>
    <script
      src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"
      integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo="
      crossorigin=""
    ></script>
    <script>
      const map = L.map("map").setView([0, 0], 2);
      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19,
        attribution: "&copy; OpenStreetMap contributors"
      }).addTo(map);

      const statusEl = document.getElementById("status");
      const detailEl = document.getElementById("detail");
      let marker = null;

      async function refresh() {
        try {
          const res = await fetch("position.json?ts=" + Date.now());
          const data = await res.json();
          if (data.status === "ok") {
            const lat = data.lat;
            const lon = data.lon;
            if (!marker) {
              marker = L.marker([lat, lon]).addTo(map);
              map.setView([lat, lon], 16);
            } else {
              marker.setLatLng([lat, lon]);
            }
            statusEl.textContent = "GPS fix";
            detailEl.textContent = `${lat.toFixed(6)}, ${lon.toFixed(6)} | alt ${data.alt_m.toFixed(1)}m | ${data.source}`;
          } else {
            statusEl.textContent = data.status || "Waiting for fix...";
            detailEl.textContent = data.detail || "";
          }
        } catch (err) {
          statusEl.textContent = "Waiting for fix...";
          detailEl.textContent = "";
        }
      }

      refresh();
      setInterval(refresh, 1000);
    </script>
  </body>
</html>
"""


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Show live u-blox M7 position on a map.")
    parser.add_argument("--port", required=True, help="Serial port (e.g. COM3 or /dev/ttyUSB0).")
    parser.add_argument("--baud", type=int, default=9600, help="Serial baud rate.")
    parser.add_argument("--host", default="127.0.0.1", help="HTTP host to bind.")
    parser.add_argument("--http-port", type=int, default=8000, help="HTTP port for the map server.")
    parser.add_argument("--output-dir", default="out/ublox_map", help="Folder for map assets.")
    parser.add_argument("--open", action="store_true", help="Open browser automatically.")
    return parser.parse_args(argv)


def _parse_lat_lon(value: str, hemi: str) -> float | None:
    if not value or not hemi:
        return None
    hemi = hemi.upper()
    if hemi not in {"N", "S", "E", "W"}:
        return None
    deg_len = 2 if hemi in {"N", "S"} else 3
    if len(value) < deg_len:
        return None
    try:
        deg = int(value[:deg_len])
        minutes = float(value[deg_len:])
    except ValueError:
        return None
    dec = deg + minutes / 60.0
    if hemi in {"S", "W"}:
        dec = -dec
    return dec


def _parse_nmea(line: str) -> dict | None:
    if "*" in line:
        line = line.split("*", 1)[0]
    fields = line.split(",")
    if not fields:
        return None
    sentence = fields[0].upper()

    if sentence.endswith("GGA"):
        if len(fields) < 10:
            return None
        lat = _parse_lat_lon(fields[2], fields[3])
        lon = _parse_lat_lon(fields[4], fields[5])
        fix_quality = fields[6]
        if lat is None or lon is None or fix_quality == "0":
            return None
        try:
            alt = float(fields[9]) if fields[9] else 0.0
        except ValueError:
            alt = 0.0
        return {"lat": lat, "lon": lon, "alt_m": alt, "source": "GGA"}

    if sentence.endswith("RMC"):
        if len(fields) < 10:
            return None
        status = fields[2].upper() if fields[2] else "V"
        if status != "A":
            return None
        lat = _parse_lat_lon(fields[3], fields[4])
        lon = _parse_lat_lon(fields[5], fields[6])
        if lat is None or lon is None:
            return None
        return {"lat": lat, "lon": lon, "alt_m": 0.0, "source": "RMC"}

    return None


def _write_position(path: Path, payload: dict) -> None:
    tmp_path = path.with_suffix(".tmp")
    with tmp_path.open("w", encoding="ascii") as handle:
        json.dump(payload, handle)
    tmp_path.replace(path)


def _start_http(directory: Path, host: str, port: int) -> ThreadingHTTPServer:
    handler = partial(SimpleHTTPRequestHandler, directory=str(directory))
    server = ThreadingHTTPServer((host, port), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def main(argv: list[str] | None = None) -> int:
    if serial is None:  # pragma: no cover
        raise ImportError("pyserial is required") from _IMPORT_ERROR

    args = _parse_args(sys.argv[1:] if argv is None else argv)
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    html_path = out_dir / "index.html"
    pos_path = out_dir / "position.json"
    html_path.write_text(HTML_TEMPLATE, encoding="ascii")
    _write_position(pos_path, {"status": "waiting", "detail": "waiting for GPS fix"})

    server = _start_http(out_dir, args.host, args.http_port)
    url = f"http://{args.host}:{args.http_port}/index.html"
    print(f"map_url={url}")
    if args.open:
        webbrowser.open(url)

    stop_event = threading.Event()

    def _reader() -> None:
        with serial.Serial(port=args.port, baudrate=args.baud, timeout=1) as ser:
            while not stop_event.is_set():
                raw = ser.readline()
                if not raw:
                    continue
                try:
                    line = raw.decode("ascii", errors="ignore").strip()
                except UnicodeDecodeError:
                    continue
                if not line.startswith("$"):
                    continue
                fix = _parse_nmea(line)
                if not fix:
                    continue
                payload = {
                    "status": "ok",
                    "lat": fix["lat"],
                    "lon": fix["lon"],
                    "alt_m": fix["alt_m"],
                    "source": fix["source"],
                    "time_utc": _iso_now(),
                }
                _write_position(pos_path, payload)
                print(f"lat={fix['lat']:.6f} lon={fix['lon']:.6f} alt_m={fix['alt_m']:.1f}")

    thread = threading.Thread(target=_reader, daemon=True)
    thread.start()
    try:
        while thread.is_alive():
            time.sleep(0.5)
    except KeyboardInterrupt:
        stop_event.set()
    finally:
        server.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
