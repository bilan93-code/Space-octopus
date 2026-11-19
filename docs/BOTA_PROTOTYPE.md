# Actuator prototype integration

The circular 112 mm motor PCB supplies 9 V to the Bota BTS-T300-CAT. A dedicated Jetson Ethernet interface running an EtherCAT master reads torque. The sensor mounts at the gearbox output. Its 300 N·m measurement range covers the assumed 220 N·m continuous operating point. Peak operating torque and flange fit still need confirmation.

## Harness

| Connection | Function |
| --- | --- |
| J12 pin 1 → Bota pin 5 (red) | Current-limited 9 V supply. Use the JST SH mating housing and suitable contacts. Verify pin 1 at the assembled breakout. |
| J12 pin 2 → Bota pin 6 (white/red) | Sensor power return. |
| Bota cable pairs 1/2 and 3/4 → Jetson Ethernet via Bota-compatible breakout | EtherCAT data. Follow the supplier's pair and shield assignments. Insulate unused USB wires 7 and 8. |
| J5 or J6 → robot CAN interface | Setpoints and drive status. Both ports share one CAN bus. Terminate the two physical bus ends. |
| J4 → FLUX encoder | Board and harness pin numbers match. Pins 1/2 supply power, 7/8 carry clock, 9/10 carry data and 11 carries the shield. Pins 3–6 are unused. Secure the unkeyed connector. |
| J9 → service tool | 3.3 V UART. |
| J11 → external brake resistor | Mount the pulse-rated element on its specified heatsink. |

## Sensor supply

U21 is the adjustable LT3065EDD in its 10-pin DFN. R107 and R108 set 9 V. R109 sets a nominal 273 mA limit. C114 and C115 provide local input and output bypass, C116 filters the current-limit pin and C117 sets reference bypass and soft start. Pin 11 is a soldered ground and heat-transfer pad. Specify filled and capped via-in-pad manufacture. Verify at least 3.3 µF effective output capacitance after DC bias and tolerance.

Bota lists “6–24 V (Max 13 V), 1.6 W.” Use 13 V as the upper design limit at the sensor. The regulated output screens at 8.65–9.36 V using the LT3065 reference limits, 1% divider resistors and a 60 nA bias allowance. Transient overshoot requires a measurement. The branch shares the 12 V converter with the encoder, gate drivers and downstream 5 V converter. The load-study report records the assumed simultaneous loads, regulator current ceilings, startup sweep and thermal limitations. Approximately 0.53 W is dissipated in the pass element at 12 V input and a nominal sensor load. Hot joint conditions, current-limit cycling, regulator ground current and cable loss need hardware measurements.

At 500 mA on the downstream 5 V rail, the supply sweep used a 200 mA encoder allowance, 100 mA for gate and brake circuits, 25 mA for regulator ground current and 80% efficiency for the 5 V converter. The 180 cases span six downstream loads from 250 mA to 1 A, ten sensor demands from 178 mA to 500 mA and three assumed regulator current limits from 243 to 303 mA. Each case applies a 2 ms sensor load step to a running supply. The sensor model draws less current when its voltage falls. Actual startup and repeated brownout behavior depend on its electronics.

| Sensor demand at 9 V | Lowest shared rail across three modeled limits at 500 mA on 5 V | Sensor voltage range at J12 |
| --- | --- | --- |
| 178 mA | 11.90 V | 8.99 V |
| 250 mA | 11.89 V | 8.75–8.98 V |
| 350 mA | 11.88 V | 6.25–7.79 V |
| 400 mA | 11.88 V | 5.47–6.82 V |
| 500 mA | 11.88 V | 4.37–5.45 V |

The design budget leaves about 156 mA on the 12 V rail at the rated sensor power and 31 mA at the modeled upper current limit. Measure at the sensor end of its cable and capture the 12 V rail during first power-up. A measured startup current below the rating of the connector alone does not establish that the supply can start the sensor.

[Power study with assumptions](../output/prototype/power/load-study.json) · [All 180 load steps](../output/prototype/power/load-sweep.csv) · [LT3065 regulator datasheet](evidence/lt3065.pdf) · [LM5164 supply datasheet](evidence/lm5164.pdf)

## Control and packaging

The STM32 reads the FLUX motor encoder and phase currents and controls the inverter. The Jetson reads output torque over EtherCAT and can send commands over CAN. Establish a fault response for stale data and measure end-to-end timing before closing an outer torque loop. The Bota datasheet gives a maximum sampling rate of 3,800 Hz and a 0–55 °C operating range.

Fit the motor drive to insulated standoffs with tall parts and plug-in connectors facing outward. Reserve 46 mm above each bulk capacitor for the body, seating allowance and vent. Reserve Ø115 × 12.25 mm for the Bota sensor until its flange drawing is confirmed. Verify the actual motor-side component and fastener clearance on the assembled joint.

## Braking assumption for the first bench prototype

Use a horizontal test fixture, 10 rpm maximum output speed, up to 220 N·m braking torque and a linear stop in one second. This models about 115 J per stop (torque × average angular speed × time). Specify 250 J per event and at most six such events per minute, or 25 W time-average dissipation. A 4.7 Ω element at 57.6 V draws 12.3 A and dissipates 706 W while switched on. Specify a heatsink-mounted resistor rated at least 200 W under the actual enclosure cooling, with a supplier pulse curve covering the full event at ≥0.8 kW and the complete repeating profile including initial temperature. Check the brake-switch voltage and resistor tolerance at the actual maximum bus voltage. A hanging load or faster joint changes the energy budget. Measure real inertia, bus rise and resistor temperature before extending this envelope.

[Soldered fuse selection and qualification](SOLDERED_FUSES.md)

## Ordering and release

Order the Bota sensor, mating harness, Ethernet breakout and external brake resistor separately from JLCPCB assembly. The PCB Parts stock sheet covers installed motor-drive components, including the two soldered axial fuses. Qty for five is the engineering minimum. JLCPCB determines loading allowance and through-hole assembly support.

Verify F1/F2 inrush, braking pulses, hot derating and DC interruption, D2/D3–D5 pin assignments, the C5 case, FLUX startup demand on F3, the 48 V source and actual thermal load before assembly release. Qualify the gate-driver vias and stencil with the assembler. Independent copper connectivity, electrical function, thermal qualification and stock each need their own passing result.

[Bota datasheet supplied with the project](evidence/Bota_BTS_Torque_Sensor_Family.pdf) · [SOEM](https://github.com/OpenEtherCATsociety/SOEM)
