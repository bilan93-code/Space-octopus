# Current tscircuit review status

137/137 electrical nets are physically connected; 0 remain split into islands. The independent geometry audit found 0 shorts, 0 copper-clearance findings, 0 edge findings and 0 hole/hardware findings.

The draft has 10046 trace objects, 1451 vias and 230 GND-fill regions (top: 97, inner1: 33, bottom: 100), with 21 VBUS-fill regions on inner2. Pours are counted by their source net and layer. See [the remaining islands](../output/unrouted-net-islands.csv), [native diagnostics](../output/render-diagnostics.json), [the copper audit](../output/copper-audit.json) and [validation results](../output/validation-results.json). See validation results for the native DRC and independent connectivity checks.

The [power-backbone checker](../scripts/check-power-backbone.py) requires separate wide GND and VBUS backbones using pads, plated barrels and tracks at least 2 mm wide, with **all copper fills excluded**. It also tests both VBUS routes from J1.1 to the positive terminal of C1 and the F2 transfer through the inner2 rail. Results below come from [the saved audit](../output/power-backbone-audit.json); missing tests or missing all-fill exclusion evidence remain unverified.

| Distinct geometric test | Recorded result |
|---|---|
| Wide GND backbone, all fills excluded | verified |
| Wide VBUS backbone, all fills excluded | verified |
| J1.1 to C1.1 on inner2, 4.5 mm launch into ≥3.0 mm copper | verified |
| J1.1 to C1.1 on bottom, ≥2.4 mm copper | verified |
| F2 input via array and F2 output to J11.1 | verified |

**Engineering qualification remains open.** The layout includes parallel VBUS paths with a 4.5 mm inner2 launch feeding a 3 mm rail and a 2.4 mm bottom rail, wide phase/brake copper and parallel through-via arrays. Local converter/bypass cells and dedicated shunt pickups have independent checks. Current capacity, switching behavior, differential timing, thermal design, provisional packages and motor axial fit remain release gates. Filled and capped via-in-pad manufacture is required.

J1.1 connects directly to VBUS. Input protection and precharge belong on the upstream battery PCB. F2 is the proposed surface-mount fuse for the 4.7 Ω ±5%, 300 W resistor on the separate braking PCB at J11. Its land pattern, DC breaking capacity and pulse performance require confirmation.

The board has 222 populated component positions. J1, J2 and J11 are bare plated wire terminals. The [3D model report](../output/3d-status.json) identifies parts shown with representative bodies, including F2. D2 models the required 2 mm lead trim. DNP devices and bare PCB features have no body model. The editable design for this publication is the tscircuit project.
