# Space Octopus actuator PCB — tscircuit stage

The 23 November 2026 revision builds on the direct-wire actuator PCB at `4579c77` from 19 November. The future battery PCB supplies a fused 48 V feed to J1. The actuator connects J1 pin 1 directly to VBUS and retains a local soldered surface-mount brake fuse, F2. J11 connects to a separate PCB carrying the 4.7 Ω ±5%, 300 W braking resistor.

[Power and brake connections](docs/POWER_AND_BRAKE.md) · [Wire assignments and harness requirements](docs/DIRECT_WIRE_HARNESS.md) · [Connected schematic](output/Space_Octopus_Connected_Schematic.pdf) · [Five-board sourcing snapshot](output/prototype/five-board-stock-upstream-fuse-smd-brake.csv)

[JLCPCB DFM handoff](output/jlcpcb-bota-upstream-fuse-smd-brake/Space-Octopus-JLCPCB-DFM-handoff.zip) · [JLCPCB component placement list (CSV)](output/jlcpcb-bota-upstream-fuse-smd-brake/JLCPCB-CPL-quote.csv) · [Top 3D view of F2](output/Space-Octopus-20261123-SMD-brake-top.png) · [Copper-path verification](output/power-backbone-audit.json)

The JLCPCB bundle is for a DFM and price quote. Final F2 selection, including its land pattern and DC fault interruption, and the separate resistor assembly's pulse and thermal ratings require verification before release.

## Drawings and verification

| Document | Files |
| --- | --- |
| Electrical schematics | [Connected drawing](output/Space_Octopus_Connected_Schematic.pdf) · [Nine-sheet PDF](output/Space_Octopus_RevA_Schematics.pdf) · [Pin assignments](output/pin-assignments/) |
| Mechanical interface | [Dimensioned PCB outline](output/Motor112_PCB_Interface.pdf) · [Motor mounting drawing](output/Motor112_Mounting_Concept.pdf) |
| Board layout | [Top](output/pcb-placement.png) · [Bottom](output/pcb-bottom.png) · [3D model](output/space-octopus.glb) |
| Fabrication and assembly | [JLCPCB quote package, BOM, placement file and notes](output/jlcpcb-bota-upstream-fuse-smd-brake/) |
| Engineering evidence | [Status and qualification items](docs/TSCIRCUIT_STATUS.md) · [18 design checks](output/validation-results.json) · [Gerber connectivity](output/gerber-connectivity.json) · [Braking assumptions](docs/BOTA_PROTOTYPE.md) · [Design references](docs/) |

## Rebuild the design

Current builds replay the checked-in tscircuit layout in `data/routed-traces.json`. The earlier `seed-routing.py`, `route-revised-power.py` and `route-power-backbone.py` scripts refer to the historical two-fuse board.

Rebuild the current layout with `npm ci` and `npm run build`. Run `npm run simulate:bota` for the sensor supply study. The GLB export runs with `npm run export:3d`.

After a clean `npm test`, use the Python dependencies in `requirements-cam.txt` and run `npm run export:jlc-quote` to reproduce the manufacturing-file checks.

