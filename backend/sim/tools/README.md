# Route Sim

CLI tools for generating GPS IQ streams and playing route simulations with motion control.

## Quick usage

Generate motion + IQ from a project file:
```bash
python .\tools\rsim.py gen .\tools\data\sample-project\project.yaml
```

Play fixed/route IQ and motion signals:
```bash
python .\tools\rsim.py play .\tools\data\sample-project\project.yaml
```

Project file example:
`tools/data/sample-project/project.yaml` (edit paths and ports before running).
