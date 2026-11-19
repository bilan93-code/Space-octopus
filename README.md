# Space Octopus actuator PCB — tscircuit stage

The 19 November 2026 revision replaces the DC input, motor phase and braking resistor screw terminals with seven direct-solder wire lands. It builds on the soldered-fuse design at commit `21ed605`. The harness and its chassis supports require qualification for the intended vacuum and vibration environment.

[Wire assignments and harness requirements](docs/DIRECT_WIRE_HARNESS.md) · [Fuse selection](docs/SOLDERED_FUSES.md) · [Connected schematic](output/Space_Octopus_Connected_Schematic.pdf) · [Five-board parts and dated stock](output/prototype/five-board-stock-wire-terminations.csv)

Rebuild the current layout with `npm ci` and `npm run build`. Run `npm run simulate:bota` for the sensor supply study. The GLB export runs with `npm run export:3d`.

After a clean `npm test`, use the Python dependencies in `requirements-cam.txt` and run `npm run export:jlc-quote` to reproduce the manufacturing-file checks.

