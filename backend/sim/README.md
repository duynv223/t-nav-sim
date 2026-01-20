# Route Sim

GPS route simulation: generate motion samples + IQ stream (gps-sdr-sim), then play GPS IQ with speed/bearing control over serial.

## Quick usage
```bash
python .\tools\rsim.py gen .\tools\data\sample-project\project.yaml
python .\tools\rsim.py play .\tools\data\sample-project\project.yaml
```

## Project file
`project.yaml` defines:
- `route`: CSV lat/lon[/alt].
- `motion_profile`: speed/accel/decel settings.
- `sim_data_path`: output paths (motion, route_iq).
- `iq_generator`: gps-sdr-sim settings.
- `playback`: HackRF + serial controller settings.

Sample: `tools/data/sample-project/project.yaml`.
