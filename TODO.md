## TODO
- [ ] Bug fix: Stop Run → Re-run shows "no device"  
  Possible cause: hackrf_transfer not fully stopped when stopping Run
- [x] Current Motion  
  - Update parameter labels to be clearer  
  - Apply fixed parameter formatting (t: .1, lat/lon: .7, speed: .1, bearing: .1)
- [ ] When switching to the Simulation tab, exit Edit Mode
- [ ] During Run: disable build, disable editing Run parameters
- [ ] Show running progress as current/total, ex: `Running (12/70)`
- [ ] Support detailed Build progress (parse `gps-sdr-sim` logs)
- [ ] Only show heading marker in Simulation running
- [x] Add placeholder for advanced motion profile
- [x] Update frontend for tab name and icon

Next Features:
- [ ] Feature: GPS monitor (using u-blox)
- [ ] Feature: undo/redo
- [ ] Implement: route edit context menu
- [ ] Feature: speed Bearing Control Dashboard
- [ ] Feature: import nmeagen coordinate points (csv)
- [ ] Feature: advance speed profile
- [ ] Feature: run from selected segment