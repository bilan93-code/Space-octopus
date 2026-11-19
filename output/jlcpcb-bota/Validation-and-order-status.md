# Space Octopus motor drive and Bota interface
## Archived holder-board quote · 18 November 2026

This package applies to commit `79d4fc1` with the SCHURTER fuse holders. The [soldered fuse revision](../../docs/SOLDERED_FUSES.md) uses different drill data and a different assembly BOM.

**Ready for a five-board DFM and price quote. Engineering release for fabrication, assembly and powered operation remains on hold.** The final native tscircuit design and the files in the quote archive share the design fingerprint shown below.

| Check | Final result |
| --- | --- |
| Clean rebuild, TypeScript, 3D export, project suite | All 18 checks passed. Native renderer reported zero errors. |
| Electrical capture | 1,622 checks passed, zero failed. Eight engineering-release items remain open. |
| Native copper | All 138 nets connected. Zero shorts or violations of the project copper-spacing, edge and hole rules. All six phase-current Kelvin pickups passed their isolation test. |
| Independent Gerber copper readback | All 138 source nets recovered. All 736 surface pads, 52 plated component holes and 1,428 vias sampled on their expected layers. Zero opens, shorts or via-net disagreements. |
| Copper edge sensitivity | All nets also connected after moving each Gerber copper edge inward by 0.025 mm. This is a geometric sensitivity test. Actual etching, layer registration and drill registration depend on the fabrication process. |
| Outline and drilling | Four copper layers, 112 mm OD, 28 mm routed center opening and six 4.5 mm mounts on a 104 mm pitch circle. The separate plated and nonplated files contain 1,480 and 8 holes respectively. Minimum drilled edge-to-edge web is 0.20 mm. |
| Stencil | 160 outward-face and 563 motor-face openings. All matched physical component lands. Gate driver U2 has 49 apertures, watchdog U13 has 13 and regulator U21 has 11. |
| Assembly interchange | The BOM and CPL name exactly the same 226 fitted board positions, 71 outward and 155 motor-facing. All coordinates, sides and angles match the native placement export. The 97 BOM lines give quantities per board. Two fuse cartridges per board are listed separately for insertion in the soldered holders. |
| Bota power | 180 simulated load combinations. At a 500 mA downstream 5 V load and 1.6 W at the sensor, J12 stays near 8.99 V and the 12 V rail near 11.90 V. At a 500 mA equivalent startup demand J12 falls to 4.37–5.45 V across limit corners. |
| Mechanical model | Nominal 7 mm end-cap gap gives 2.58 mm minimum modeled motor-side clearance with trimmed leads. Allow 46 mm outward at the capacitor vents. Actual housing, connector latches, fasteners and harness bends need fit confirmation. |

### Changes made during validation

The first independent Gerber readback identified edge-only contacts on the motor PWM signal, the winding-temperature measurement and a phase-W branch. The corrected tscircuit routing reinforces these and other narrow joins, widens the two bypass-capacitor ground regions at C109 and C904, and removes three isolated vias. The watchdog footprint now places its eight perimeter openings and five exposed-pad openings on the motor-facing stencil. Its four heat-transfer holes receive no separate paste. The opposite-side thermal land follows the footprint drawing. The full suite and both Gerber extraction tests ran on the corrected build.

### Send these files for quote

1. Upload the [Gerber and drill archive](Space-Octopus-Bota-JLCPCB-Gerbers-DFM-quote.zip) as the PCB file.
2. For the assembly quote select both sides. Upload the [per-board BOM](JLCPCB-BOM-quote.csv) and [component placement file](JLCPCB-CPL-quote.csv). Set board quantity to five.
3. The [cartridge list](Hand-insert-fuse-cartridges.csv) supplies purchasing quantities for hand insertion. F1 and F2 in the assembly BOM refer to their board-mounted SCHURTER holders.

Request a quote for a 1.6 mm, four-layer board with 2 oz outer copper as specified in the motor plan. Provide the actual layer stack and inner copper weights for approval. Specify filled and capped via-in-pad on both assembly faces. The smallest via is 0.20 mm drilled with a 0.40 mm land and nominal 0.10 mm annular ring. Minimum trace width is 0.15 mm. The design spacing rule is 0.20 mm. Request confirmation of these features together with the selected copper weight, drill tolerance, solder-mask registration, metal cap planarity, routing of the center opening, mixed through-hole assembly and double-sided stencil. Request a bare-board electrical test against the intended netlist and inspect the assembler's library preview for pin 1, diode and capacitor polarity, and bottom-side rotation.

### Release holds

| Before | Evidence still needed |
| --- | --- |
| Buying bare boards | JLCPCB's DFM acceptance for the actual stackup, narrow annuli and filled/capped vias. Confirm the C5 Panasonic film-capacitor case against the allocated body space, the D2 brake-diode and D3–D5 protection-diode pin assignments, and the F1/F2 land and holder ratings. These findings can change a footprint. |
| Buying assembly | Confirm or arrange sourcing for TPS3431SDRBR at U13, Coilcraft MSS1246T-683MLB at L101 and SCHURTER 0031.8002 at F1/F2. The PCB Parts snapshot dated 16 November covers 96 of 99 purchase lines for five boards, including the two separate cartridge types. Live JLCPCB allocation and vendor DFM acceptance were unavailable. The package audit flags 67 board-design items for manufacturer, assembly or system confirmation. |
| Applying motor power | Confirm DC fault interruption and fuse/holder coordination, precharge behavior, braking resistor pulse energy, gate timing and protection, and copper/MOSFET temperatures under actual load. The 13 A RMS operating target, peak phase current, enclosure cooling and regeneration duty require hardware qualification. Verify the FLUX encoder harness and Bota startup current, cable drop and temperature on the prototype. The Bota's current-limited 9 V branch and Jetson EtherCAT path are included. |

The final design uses the bench assumptions in [the integration notes](../../docs/BOTA_PROTOTYPE.md). JLCPCB's live capabilities page and the hosted PCB Parts stock endpoint returned HTTP 403 from this environment. All upload files were checked locally. The dated stock sheet uses the published PCB Parts catalogue at commit `43a335ba6382e9a92afdee1b61031dc7a05803f3`.

### Traceability

Circuit JSON SHA-256 `29e4eb191f0bb3c1be96f8e0f0dd42dc576b6155245c2352691e5876ecb381f8`

[Project checks](../validation-results.json) · [Gerber connectivity](../gerber-connectivity.json) · [Copper reduction test](../gerber-etch-screen.json) · [Stencil readback](../stencil-file-audit.json) · [Fabrication file audit](../fabrication-file-audit.json) · [Power study](../prototype/power/load-study.json) · [Five-board stock](../prototype/five-board-stock.csv) · [Upload file hashes](package-verification.json)
