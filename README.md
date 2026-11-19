# Space Octopus actuator PCB — tscircuit stage

The 18 November Bota prototype adds a 9 V, current-limited sensor output at J12 and updates the motor interfaces. The Jetson reads the BTS-T300-CAT over EtherCAT. The current design has 138 nets. All 18 tscircuit project checks and the independent Gerber and stencil checks pass on the corrected build. The board is ready for a JLCPCB DFM quote. Fabrication and assembly release remain on hold.

[Integration and supply assumptions](docs/BOTA_PROTOTYPE.md) · [Connected schematic](output/Space_Octopus_Connected_Schematic.pdf) · [Five-board parts and dated stock](output/prototype/five-board-stock.csv) · [180 load cases](output/prototype/power/load-sweep.csv)

Rebuild the current layout with `npm ci` and `npm run build`. Run `npm run simulate:bota` for the sensor supply study. The GLB export runs with `npm run export:3d`.

[Current validation and quote files](output/jlcpcb-bota/Validation-and-order-status.md). After a clean `npm test`, use the Python dependencies in `requirements-cam.txt` and run `npm run export:jlc-quote` to reproduce the manufacturing-file checks.

