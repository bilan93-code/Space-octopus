# Space Octopus actuator PCB — tscircuit stage

The 19 November 2026 revision of the 112 mm motor-drive PCB fits a directly soldered 20 A input fuse at F1 and a directly soldered 15 A braking fuse at F2. It uses the Bota prototype from commit `79d4fc1` as its baseline. Fuse coordination, assembler fit and manufacturing release remain open.

[Soldered fuse selection and layout](docs/SOLDERED_FUSES.md) · [Integration assumptions](docs/BOTA_PROTOTYPE.md) · [Connected schematic](output/Space_Octopus_Connected_Schematic.pdf) · [Five-board parts and dated stock](output/prototype/five-board-stock-soldered.csv)

Rebuild the current layout with `npm ci` and `npm run build`. Run `npm run simulate:bota` for the sensor supply study. The GLB export runs with `npm run export:3d`.

After a clean `npm test`, use the Python dependencies in `requirements-cam.txt` and run `npm run export:jlc-quote` to reproduce the manufacturing-file checks.

