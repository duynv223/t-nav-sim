from __future__ import annotations

import argparse
import tkinter as tk
from tkinter import ttk
from typing import Optional


class SimulatorTransport:
    def __init__(self, port: str, baud: int, dry_run: bool):
        self.dry_run = dry_run
        self.serial = None
        if not dry_run:
            try:
                import serial  # type: ignore
            except ImportError as exc:
                raise RuntimeError("pyserial required: pip install pyserial") from exc
            self.serial = serial.Serial(port, baud, timeout=0.3)

    def send(self, cmd: str) -> str:
        line = f"{cmd}\n"
        if self.dry_run:
            return f"DRYRUN: {cmd}"
        assert self.serial is not None
        self.serial.reset_input_buffer()
        self.serial.write(line.encode("ascii"))
        try:
            resp = self.serial.readline().decode("ascii", errors="replace").strip()
        except Exception:
            resp = ""
        return resp or "OK?"

    def close(self) -> None:
        if self.serial:
            self.serial.close()


class ControlApp:
    def __init__(self, root: tk.Tk, transport: SimulatorTransport):
        self.root = root
        self.transport = transport
        root.title("STM32 Angle & Speed Control")
        root.geometry("720x440")

        self.angle_set_var = tk.StringVar(value="0")
        self.angle_move_var = tk.StringVar(value="0")
        self.angle_speed_var = tk.StringVar(value="20")
        self.angle_calib_var = tk.StringVar(value="0")
        self.speed_kmh_var = tk.StringVar(value="0")

        self.log = tk.Text(root, height=12, font=("Consolas", 10))

        self._build_ui()

    def _build_ui(self) -> None:
        pad = {"padx": 6, "pady": 4}
        row = 0

        ttk.Label(self.root, text="Angle (0°=North, CW positive)").grid(column=0, row=row, sticky="w", **pad)
        ttk.Button(self.root, text="Ping", command=lambda: self._send("ping")).grid(column=1, row=row, **pad)
        row += 1

        ttk.Button(self.root, text="Home", command=lambda: self._send("angle_home")).grid(column=0, row=row, **pad)
        ttk.Label(self.root, text="Set °").grid(column=1, row=row, sticky="e")
        ttk.Entry(self.root, textvariable=self.angle_set_var, width=8).grid(column=2, row=row, **pad)
        ttk.Button(self.root, text="Send", command=self._angle_set).grid(column=3, row=row, **pad)
        row += 1

        ttk.Label(self.root, text="Move Δ°").grid(column=1, row=row, sticky="e")
        ttk.Entry(self.root, textvariable=self.angle_move_var, width=8).grid(column=2, row=row, **pad)
        ttk.Button(self.root, text="Move", command=self._angle_move).grid(column=3, row=row, **pad)
        row += 1

        ttk.Label(self.root, text="Speed deg/s").grid(column=1, row=row, sticky="e")
        ttk.Entry(self.root, textvariable=self.angle_speed_var, width=8).grid(column=2, row=row, **pad)
        ttk.Button(self.root, text="Set Speed", command=self._angle_speed).grid(column=3, row=row, **pad)
        ttk.Button(self.root, text="Stop Angle", command=lambda: self._send("angle_stop")).grid(column=4, row=row, **pad)
        row += 1

        ttk.Label(self.root, text="Calib ° (set current to heading)").grid(column=1, row=row, sticky="e")
        ttk.Entry(self.root, textvariable=self.angle_calib_var, width=8).grid(column=2, row=row, **pad)
        ttk.Button(self.root, text="Calibrate", command=self._angle_calib).grid(column=3, row=row, **pad)
        ttk.Button(self.root, text="Angle Status", command=lambda: self._send("angle_status")).grid(column=4, row=row, **pad)
        row += 1

        ttk.Separator(self.root, orient="horizontal").grid(column=0, row=row, columnspan=6, sticky="ew", pady=6)
        row += 1

        ttk.Label(self.root, text="Speed (km/h)").grid(column=0, row=row, sticky="w", **pad)
        ttk.Entry(self.root, textvariable=self.speed_kmh_var, width=8).grid(column=1, row=row, **pad)
        ttk.Button(self.root, text="Set Speed", command=self._speed_set).grid(column=2, row=row, **pad)
        ttk.Button(self.root, text="Speed Status", command=lambda: self._send("speed_get")).grid(column=3, row=row, **pad)
        ttk.Button(self.root, text="Stop Speed", command=lambda: self._send("speed_stop")).grid(column=4, row=row, **pad)
        row += 1

        ttk.Separator(self.root, orient="horizontal").grid(column=0, row=row, columnspan=6, sticky="ew", pady=6)
        row += 1

        self.log.grid(column=0, row=row, columnspan=6, padx=6, pady=6, sticky="nsew")
        self.root.grid_rowconfigure(row, weight=1)
        self.root.grid_columnconfigure(5, weight=1)

    def _send(self, cmd: str) -> None:
        resp = self.transport.send(cmd)
        self.log.insert(tk.END, f">>> {cmd}\n")
        if resp:
            self.log.insert(tk.END, f"<<< {resp}\n")
        self.log.see(tk.END)

    def _angle_set(self) -> None:
        val = self._parse_float(self.angle_set_var.get(), "angle_set")
        if val is not None:
            self._send(f"angle_set {val:.2f}")

    def _angle_move(self) -> None:
        val = self._parse_float(self.angle_move_var.get(), "angle_move")
        if val is not None:
            self._send(f"angle_move {val:.2f}")

    def _angle_speed(self) -> None:
        val = self._parse_float(self.angle_speed_var.get(), "angle_speed")
        if val is not None:
            self._send(f"angle_speed {val:.2f}")

    def _angle_calib(self) -> None:
        val = self._parse_float(self.angle_calib_var.get(), "angle_calib")
        if val is not None:
            self._send(f"angle_calib {val:.2f}")

    def _speed_set(self) -> None:
        val = self._parse_float(self.speed_kmh_var.get(), "speed_set")
        if val is not None:
            self._send(f"speed_set {val:.2f}")

    def _parse_float(self, txt: str, field: str) -> Optional[float]:
        try:
            return float(txt)
        except ValueError:
            self.log.insert(tk.END, f"!!! invalid number for {field}: {txt}\n")
            self.log.see(tk.END)
            return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Tkinter control app for STM32F4 angle & speed simulator.")
    parser.add_argument("--port", default="COM5", help="Serial port for STM32.")
    parser.add_argument("--baud", type=int, default=115200, help="Baud rate.")
    parser.add_argument("--dry-run", action="store_true", help="Do not open serial; just log commands.")
    args = parser.parse_args()

    transport = SimulatorTransport(args.port, args.baud, args.dry_run)
    root = tk.Tk()
    app = ControlApp(root, transport)
    try:
        root.mainloop()
    finally:
        transport.close()


if __name__ == "__main__":
    main()
