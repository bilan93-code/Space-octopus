# Direct-solder power harness · 19 November 2026

J1, J2 and J11 are numbered plated holes. Insert the stripped wires from the outward face of the 112 mm board and solder them during harness assembly. The three positions have no connector body or mating plug. The rest of the harness interfaces retain their existing assignments.

| PCB reference | Pad 1 | Pad 2 | Pad 3 |
| --- | --- | --- | --- |
| J1 · 48 V DC input | DC+ · supply positive, upstream of F1 | Supply return (GND) | |
| J2 · motor phases | U | V | W |
| J11 · external brake resistor | BR+ · brake feed, downstream of F2 | BR_SW · switched by Q7 | |

Connect the external 4.7 Ω resistor across the two J11 wires. J11 pad 2 carries the switched brake node and must remain isolated from chassis and supply return.

## Fit and support

The layout uses 1.80 mm nominal finished holes, 2.60 mm copper lands and 5.08 mm pitch. This gives a nominal 0.40 mm radial annulus. The larger holes retain the pin centers and outer copper boundaries from the screw-terminal layout. The two soldered fuses from commit `21ed605` remain in the power paths.

Use one conductor per hole. Select wire size from actual current, allowable voltage drop, bundling, insulation temperature limit and installed heat rejection. Check the supplier's maximum stripped bundle diameter and the board supplier's minimum finished hole against a harness sample. Keep every strand, inspect solder fill on both faces, and verify trimmed ends, insulation and bend radius against the rear motor clearance.

Support each bundle at a chassis hardpoint near its board exit, with a short compliant length between the support and the pad. Keep the wires clear of the shaft, capacitor vents and sharp edges. Establish the clamp location with the actual motor housing and harness. Verify the attachment and inspect the solder joints after representative vibration and thermal cycling. The bare-board 3D model shows the lands. Wire bends and chassis clamps depend on the enclosure. [NASA cable and harness workmanship guidance](https://standards.nasa.gov/standard/nasa/nasa-std-87394)

## Vacuum use

Removing the three terminal blocks eliminates their plastic housings and screw clamps. Qualify the exact wire insulation, sleeving, clamp liner, any staking material and the cleaning process against mission contamination and outgassing requirements. Check power-path temperatures in the installed thermal-vacuum configuration, where there is no convective cooling. The four vented Rubycon ZLJ bulk capacitors also need pressure and service-life evidence for the intended environment. Vacuum and flight qualification remain open. [NASA outgassing database](https://outgassing.nasa.gov/) · [Installed capacitor family datasheet](evidence/rubycon-ZLJ.pdf)

## Prototype files

All 18 project checks passed. Independent readback verified all 138 nets, including a 0.025 mm copper-edge reduction. Both stencils passed. The assembly BOM and placement file cover 223 fitted components. The seven holes are fabricated with the PCB and wired during harness installation.

[3D board view](../output/board-3d-angle.png) · [Connected schematic](../output/Space_Octopus_Connected_Schematic.pdf) · [Gerbers and drills](../output/jlcpcb-bota-wire-terminations/Space-Octopus-Bota-JLCPCB-Gerbers-DFM-quote.zip) · [Assembly BOM](../output/jlcpcb-bota-wire-terminations/JLCPCB-BOM-quote.csv) · [Placement file](../output/jlcpcb-bota-wire-terminations/JLCPCB-CPL-quote.csv) · [Package verification](../output/jlcpcb-bota-wire-terminations/package-verification.json)
