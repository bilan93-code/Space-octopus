# Soldered input and brake fuses · 19 November 2026

This revision starts from the 18 November validated tscircuit design, published on 19 November as commit `79d4fc1`. Both Littelfuse 487 parts have factory-attached axial leads. The assembler forms and solders the leads directly into the board. Servicing either fuse requires desoldering.

| Position | Connection | Order code | PCB Parts code | Rating in catalogue |
| --- | --- | --- | --- | --- |
| F1 | DC_IN → VBUS | 0487020.MXEP | C48971222 | 20 A, 420 V DC |
| F2 | VBUS → BRAKE_PLUS | 0487015.MXEP | C7153748 | 15 A, 420 V DC |

The catalogue lists a 21.5 mm long, 5.5 mm diameter body for both fuses. The new courtyard is 41.5 × 7 mm, down from 44 × 15.5 mm per holder. This frees about 57% of the reserved top-side area at each position. Retaining the 37.5 mm lead pitch keeps both parallel input-current paths and the brake copper on the validated lands. The two holder locating holes are removed. The modeled outward height falls from 14.5 to 6.5 mm. Each finished hole is 1.30 mm in diameter. The fit model assumes a 1 mm lead, a 2 mm bend radius and a 1 mm body standoff. Confirm the production lead dimensions, bend clearance, retention and soldering process with the assembler. The 112 mm board diameter is set by the motor mount.

### Electrical qualification

- **F1 input.** The four fitted 820 µF capacitors total 3.28 mF. At 54 V the bank requires about 0.177 C of charge. With ideal constant-current precharge at 5 A this corresponds to about 35 ms and 0.89 A²s. This example assumes an initially discharged bank and excludes downstream load. Measure the actual startup waveform and sustained input current at the highest enclosure temperature. Direct connection to a low-impedance battery gives a different surge.
- **F2 brake.** At the nominal 57.6 V chopping threshold the 4.7 Ω external resistor draws about 12.3 A while on. Dissipating the specified 250 J maximum bench event in that resistor gives a fuse current integral of approximately 53 A²s per event. Six such events per minute correspond to about 2.3 A RMS over the minute. Check individual pulses, repetition, tolerance and hot operation against the fuse time-current and pulse-life curves.
- **DC interruption.** The catalogue lists 300 A at 420 V DC for F1 and gives two interruption figures, 200 A and 300 A, for F2 without the corresponding test conditions. Obtain the manufacturer DC ratings and curves for both exact order codes. Compare them with the prospective fault current at each fuse, including local bus-capacitor discharge into a brake fault. The supply current setting alone cannot establish that value. Catalogue melting integrals of 390 A²s (F1) and 190 A²s (F2) are typical values. Fuse coordination and assembly release remain open.

[Supplier datasheet link for F2](https://jlcpcb.com/api/file/downloadByFileSystemAccessId/8597553185506533376) · [PCB Parts catalogue entries](https://github.com/Averyy/pcbparts-mcp/blob/27c4236f3380f2061dbc9c587df9b7bfb5b02bf2/data/catalog/parts/circuit-protection/3281.jsonl) · [Five-board purchasing snapshot](../output/prototype/five-board-stock-soldered.csv) · [Prototype braking assumptions](BOTA_PROTOTYPE.md)

### Verification and prototype quote

The quote files in this section apply to the axial-fuse revision at commit `21ed605`, which used screw terminals. The [direct-wire revision](DIRECT_WIRE_HARNESS.md) supersedes that quote. All 18 project checks passed on the axial-fuse revision. Independent Gerber readback recovered all 138 nets with zero opens, shorts or via-net disagreements, including after a 0.025 mm copper-edge reduction. Both stencils passed. The revised quote contains 226 placements and 98 assembly BOM lines. F1 and F2 each occupy one fitted position per board.

The 18 November PCB Parts snapshot listed 140 units of F1 and 62 units of F2. Five boards need five of each before assembly allowance. Confirm current stock, lead forming and through-hole assembly when obtaining a quote. Four other exact order codes still require sourcing confirmation in that snapshot. The package is for DFM and pricing review. Hardware qualification and fabrication approval remain open.

[Board preview](../output/board-3d-angle.png) · [Assembly BOM](../output/jlcpcb-bota-soldered/JLCPCB-BOM-quote.csv) · [Placement file](../output/jlcpcb-bota-soldered/JLCPCB-CPL-quote.csv) · [Gerbers and drills](../output/jlcpcb-bota-soldered/Space-Octopus-Bota-JLCPCB-Gerbers-DFM-quote.zip) · [Package verification](../output/jlcpcb-bota-soldered/package-verification.json)
