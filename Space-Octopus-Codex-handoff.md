# Space Octopus actuator PCB handoff
**Historical baseline at commit `79d4fc1`.** The [soldered fuse revision](docs/SOLDERED_FUSES.md) supersedes the fuse selection and quote files below.

Updated 19 November 2026. Resume from the tscircuit revision validated on 18 November. The target is a quote for five assembled prototypes. JLCPCB DFM acceptance, purchasing and powered operation are pending.

## Board and architecture

- The original brief was `docs/Space_Octopus_Motor_PCB_Plan_RevA.pdf`. We adapted it using `docs/Motor_Gmsh_Elmer_Design_Study.pdf`. The board is a 112 mm diameter, four-layer annulus with a 28 mm center opening and six mounting holes on a 104 mm bolt circle. It mounts behind the motor. Tall parts and connectors face outward.
- J1 takes nominal 48 V motor power. The design assumes a 54 V maximum normal supply. A current-limited bench supply is the prototype plan. The battery, supply model and final cooling hardware are undecided. The Jetson has its own regulated power branch sized for the specific carrier.
- The STM32 controls the inverter and reads the FLUX encoder and phase currents. The Jetson commands the drive over CAN and reads the Bota BTS-T300-CAT over EtherCAT. J12 supplies the sensor with current-limited 9 V from the board's 12 V rail. The design fits on one PCB.
- The Bota load study covered 180 simulated cases. It predicts about 8.99 V at the sensor's rated 1.6 W with 0.5 A on the downstream 5 V rail. Sensor startup current, cable drop and hot operation still need measurements.
- F1 is the 20 A input fuse. F2 is the 15 A braking branch fuse. The present BOM uses SCHURTER 0031.8002 holders and separate cartridges. During regenerative braking, Q7 switches an external 4.7 Ω resistor at J11 when the DC bus reaches about 57.6 V.

## Most recent discussion

The user is considering two smaller soldered fuses on the actuator board. Another option discussed was an input fuse on each actuator's power-distribution branch. Both are proposals. The validated layout still uses both cartridge holders. If the user wants to pursue soldered parts, compare actual 100 V DC-or-higher ratings, DC interrupt capacity at the prospective fault current, temperature derating, F1 charging inrush, F2 braking-pulse curves, footprint and five-board availability. The user also asked whether a battery is needed. A current-limited 48 V bench supply can power the prototype. A mobile robot pack must be checked at its fully charged voltage.

## Validation and ordering

All 18 project checks passed on the corrected revision. Independent readback of all four Gerber copper layers recovered 138 nets with zero opens or shorts. Stencil checks passed on both faces. BOM and placement data match 226 positions per board. The PCB Parts catalogue snapshot from 16 November covered 96 of 99 purchase lines for five boards. Three exact order codes still need sourcing confirmation: U13 TPS3431SDRBR, L101 MSS1246T-683MLB and F1/F2 holders 0031.8002. Live JLCPCB stock was unavailable.

Before fabrication, confirm JLCPCB's four-layer stackup, 2 oz outer copper, 0.20 mm drills on 0.40 mm via lands and filled/capped via-in-pad capability. Verify the C5 case, D2–D5 pin assignments and fuse/holder coordination. The report lists remaining fit, heat, gate-drive, fault, braking and power-up checks.

## Where to resume

- Read `output/jlcpcb-bota/Validation-and-order-status.md` for the release decision and `docs/BOTA_PROTOTYPE.md` for power and wiring.
- The editable entry points are `index.tsx`, `src/SpaceOctopus.tsx` and `data/`. The validated JLCPCB quote files are under `output/jlcpcb-bota/`. The stock sheet is `output/prototype/five-board-stock.csv`.
- Verify that the SHA-256 of `output/space-octopus.circuit.json` matches `29e4eb191f0bb3c1be96f8e0f0dd42dc576b6155245c2352691e5876ecb381f8`. The main source files were untracked in the original workspace. Use the supplied project snapshot if the new task's checkout lacks this revision.
- The user wants work in tscircuit and individual links for deliverables. KiCad work requires a separate request. Use PCB Parts for JLCPCB sourcing and identify the date of any stock snapshot. The current request authorizes a handoff. Resume design changes when the user chooses the next task.
