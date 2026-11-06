# Motor CAD package: start here

This ZIP contains the study reports, source/reference documents, current model
inputs, winding exports and CAD geometry available for constructing the motor in
CAD. The motor is a three-phase permanent-magnet **inrunner**: the magnet rotor
and shaft rotate inside the stationary stator. The gearbox is a separate module.

## Open these files first

1. `results/motor/cad/SpaceOctopusMotorActive.FCStd` — current motor-only active
   geometry, plus a basic shaft reference. This is the best geometry starting
   point for the present electromagnetic model.
2. `results/motor/cad/SpaceOctopusMotorActive.step` — the same geometry for other
   CAD systems. Individual solids are in `results/motor/cad/components/`.
3. `results/motor/cad/motor_dimensions_mm.csv` — dimensions in millimetres and
   angles in degrees, with each value labelled as a model input or proposal.
4. `configs/motor_candidate.json` and `results/motor/candidate/machine.json` —
   canonical current inputs / native Pyleecan object. Their dimensions are in SI
   units: metres and radians unless otherwise indicated.
5. `results/motor/build_requirements.json` — proposed retention, bond, housing,
   thermal path and bearing envelopes to use while completing the assembly.

The active CAD includes rotor iron, ten magnets, stator iron, twenty-four active
coil-side envelopes and a basic shaft. It does not claim a completed housing,
bearing, retention or end-turn assembly. Objects are separate valid solids and
the neutral STEP export is imported again to verify solid count, volume and units.

## Coordinate system and current dimensions

CAD exports use **millimetres**. The shaft axis is +Z; the active stack runs from
Z=0 to Z=85 mm. The basic 130 mm shaft is centered on that stack for display,
from Z=-22.5 to Z=107.5 mm. That placement does not specify final bearing seats,
shoulders or coupling features. The rotor/stator cross-section is in XY.

| Current electromagnetic geometry | Value |
| --- | --- |
| Stator outside diameter | 96 mm |
| Stator bore | 53 mm |
| Rotor iron outside diameter | 46 mm |
| Bare magnet outside diameter | 52 mm |
| Bare radial magnetic gap | 0.5 mm |
| Active stack | 85 mm |
| Basic shaft | 12 mm diameter, 130 mm length |
| Slots / poles | 12 / 10 |
| Magnet radial thickness | 3 mm |
| Magnet arc | 80% of pole pitch, 28.8 degrees per magnet |

Use the exported shapes for the exact SlotW10 and magnet outlines. Slot parameters
are also in the dimension CSV and configuration; their names are Pyleecan
parameters rather than a standalone drawing-ordinate convention. Native surface
curves are retained in `results/motor/cad/motor_surfaces.json` (metres). FreeCAD
conversion uses circular arcs, not a polygonal approximation of the active parts.

## Winding information

- `winding_linear.png` / `.svg`: native Pyleecan/SWAT-EM winding pattern.
- `winding_slot_layers.png`: native phase/polarity and layer schematic.
- `winding_native_0based.csv`: native signed-turn connection table.
- `winding_sides_and_coordinates_mm.csv`: the same nonzero coil sides with
  explicit zero-based and one-based slot numbers, phase, layer, signed turns and
  XY reference points. Use these coordinates to identify sides in the CAD.
- `winding_definition.json`: connection matrix, series turns, resistance and fill.

The current model is star/Y connected, double layer, coil pitch one slot,
12 turns per coil, four series coils / 48 turns per phase, and two parallel
0.95 mm bare strands in hand. Assumed enamel thickness is 0.025 mm radially.
Positive/negative matrix entries give modeled axial current polarity for a
positive phase current. Radial and tangential layer indices are exported
explicitly; do not substitute a top/bottom-layer convention without checking them.

The exported winding matrix is checked against the analyzed candidate before
export. Coil solids represent active winding envelopes. Individual wire routes,
formed end turns, lead exits and terminal positions are CAD design choices still
to be drawn. The 12 mm half-turn end-length parameter is an **electrical length
allowance**, not a defined 12 mm axial overhang or a finished coil-loop shape.

## Completing the surrounding motor assembly

The latest proposed mechanical envelopes are in `build_requirements.json`:

| Proposed item | CAD input / status |
| --- | --- |
| Motor housing barrel | 8 mm wall around the 96 mm stator gives 112 mm nominal OD; end features remain to be drawn |
| Bearing interface | 12 x 32 x 10 mm nominal; no catalog grade, preload hardware or detailed seats selected |
| Bearing center span | 113 mm in the mechanical screen; placement/shoulders require an assembly layout |
| Magnet bond | 0.05 mm proposed bond thickness; four axial magnet segments in the construction screen |
| Retaining wrap | 0.20 mm proposed thickness; revised hot hoop modulus requirement 100 GPa, not a selected layup |
| End-turn region | Detailed three-dimensional conductor path not provided; use winding pattern and an explicit proposed route |

The current electromagnetic CAD has the original bare 52 mm magnet OD. It does
not already contain the proposed adhesive layer or retaining wrap. Adding a
radial bond can move the magnet envelope; preserve and document that change
rather than overlapping solids or assuming it was simulated. Thermal gap,
elastic deformation and tolerance allowances are not additional solid parts.

Use `results/motor/extensions/report.pdf` for the retention-clearance revision
and the conditions behind these proposals. The earlier 50 GPa wrap screen failed.
The optional 400 N m constant-torque trajectory also exceeds the reserved 42 V
voltage budget. The 220 N m assessment remains conditional on the stated inputs.

## Earlier complete concept assembly

`results/extended/cad/SpaceOctopusConcept.FCStd` and `.step` contain the earlier
58-solid motor/gearbox concept, including a housing, endbell/seat envelopes,
coupling and transmission. Its individual STEP parts are included for reuse.

That assembly is a reference, **not the latest surrounding motor construction**:

- Its active stack is at Z=15..100 mm; the new motor-only export uses Z=0..85 mm.
- Its shaft is 137 mm long; the current Pyleecan basic shaft is 130 mm.
- Its frame uses 108 mm OD and 96.2 mm ID, unlike the later 8 mm wall / 112 mm OD
  housing proposal. Its 0.1 mm stator bond is also an earlier assumption.
- Endbells, bearings/interfaces, coupling and end turns were concept envelopes.
- It does not include the revised retaining-wrap and segmented-bond construction.

Do not mix the earlier baseline 100 mm stator / 15-turn winding with the current
96 mm stator / 12-turn candidate. The configuration, native current model and
new motor-only active CAD above identify the current geometry.

## Reports, source and regeneration

The primary motor report is `results/motor/report.pdf`; the additional verification
report is `results/motor/extensions/report.pdf`. Both also have standalone HTML
and Markdown versions. Earlier actuator/baseline reports and the user-supplied
reference PDFs remain in their original folders, with source code and results.

To regenerate these CAD reference exports in the prepared environment:

    OPENBLAS_NUM_THREADS=1 .venv/bin/python scripts/prepare_motor_cad_package.py
    bash scripts/freecad_python.sh scripts/export_motor_active_cad.py

The complete analysis runner is `python -m actuator.motor_comprehensive` using
`.venv`, after the documented setup. FreeCAD geometry is an external CAD export
chosen for this project; it is not claimed as an official Pyleecan coupling.

Installed runtimes, large native field pickles and raw solver caches are omitted
from the ZIP. Source, inputs, exported geometry, component results, reports and
reproduction instructions are included. `SHA256SUMS.txt` inside the archive lists
checksums for the packaged files. No new electromagnetic or mechanical analysis
is implied by this CAD packaging step.
