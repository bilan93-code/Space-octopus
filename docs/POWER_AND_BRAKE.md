# Actuator power and brake connections · 23 November 2026

| Assembly | Connection | Part |
| --- | --- | --- |
| Future battery PCB | Battery positive → F1 → actuator harness → J1 pin 1 | Input feed fuse. Select when designing the battery PCB. |
| Actuator PCB | J1 pin 1 → VBUS. J1 pin 2 → GND. | Direct-solder power input. |
| Actuator PCB | VBUS → F2 → J11 pin 1 (BRAKE_PLUS). J11 pin 2 (BRAKE_DRAIN) → Q7 → GND when enabled. | Proposed 15 A surface-mount fuse. |
| Separate braking-resistor PCB | Connect the resistor between the two J11 wires. | 4.7 Ω ±5%, 300 W. Exact resistor and mounting remain open. |

The actuator depends on external protection for its input lead. Size upstream F1 for the harness, sustained current, startup/precharge and available battery fault current. Measure inrush into the four 820 µF bus capacitors. A fault in the brake branch can draw energy from both the supply and these local capacitors.

## Brake fuse and resistor

The actuator layout uses the Littelfuse 463 series as a candidate for F2. The proposed order code is **0463015.ER**, listed as **C720194**. The candidate footprint has two 3.20 × 4.00 mm lands on 9.10 mm centers. The proposed paste openings are 2.24 × 2.80 mm. Before fabrication, confirm the manufacturer's land pattern and terminal geometry and have the assembler review paste coverage and soldering. Before specifying the part for assembly, verify the DC interrupt rating against prospective fault current and check the time-current curve, thermal derating and repetitive pulse life in the installed conditions. [Candidate datasheet](https://jlcpcb.com/api/file/downloadByFileSystemAccessId/8588916700930576384)

At the nominal 57.6 V turn-on threshold, the resistor range of 4.465–4.935 Ω gives 11.67–12.90 A and 672–743 W while Q7 is on. At nominal resistance these are 12.26 A and 706 W. The 300 W rating applies under the selected resistor's specified mounting and cooling conditions. Check the pulse curve at the actual peak bus voltage and starting temperature, and provide a conductive path to the heatsink on the separate assembly.

The bench envelope assumes 250 J per stop and six stops per minute, giving 25 W average. If all 250 J are dissipated in the resistor, the current-squared integral through F2 is 50.7–56.0 A²s per stop. Verify pulse repetition and heat accumulation against the selected parts. [Prototype assumptions](BOTA_PROTOTYPE.md)
