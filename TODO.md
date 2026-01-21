## TODO

- [x] **Current Motion**
  - Update parameter labels to be clearer
  - Apply fixed parameter formatting *(t: .1, lat/lon: .7, speed: .1, bearing: .1)*

- [ ] When switching to the **Simulation** tab, exit **Edit Mode**

- [ ] During **Run**
  - Disable **Build**
  - Disable editing **Run parameters**

- [ ] Show running progress as **current/total**  
  Example: `Running (12/70)`

- [ ] Support detailed **Build progress** *(parse `gps-sdr-sim` logs)*

- [ ] Only show **heading marker** in **Simulation** state  
  - Remove marker when exiting Simulation

- [ ] **Bug fix:** Stop Run → Re-run shows **"no device"**  
  Possible cause: `hackrf_transfer` not fully stopped when stopping Run

- [ ] Add placehodler for Advance motion profile

- [x] Update frontend for tab name and icon

Next Features:
- [ ] Add **GPS Monitor** section to **Simulation** *(using u-blox)*

- [ ] Add Speed Bearing Control Dashboard

- [ ] Support import nmeagen coordinate points (csv)

- [ ] Support advance speed profile

- [ ] Support run from selected segment