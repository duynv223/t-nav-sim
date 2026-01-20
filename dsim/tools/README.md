# Dsim

CLI tools for generating GPS IQ streams and playing route simulations with motion control.

Install once:
```bash
python -m pip install -e .
```

## Quick usage

Generate motion + IQ from a project file:
```bash
python .\tools\rsim.py gen .\tools\sample-project\project.yaml
```

Play fixed/route IQ and motion signals:
```bash
python .\tools\rsim.py play .\tools\sample-project\project.yaml
```

Project file example:
`tools/sample-project/project.yaml` (edit paths and ports before running).
