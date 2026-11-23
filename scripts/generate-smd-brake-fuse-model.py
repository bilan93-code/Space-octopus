"""Generate the 0463015.ER nominal body for fit review in the tscircuit assembly."""
from pathlib import Path

import cadquery as cq

# PCB Parts catalogue dimensions. No vendor solid or maximum tolerances supplied.
body = cq.Workplane("XY").box(10.1, 3.12, 3.12, centered=(True, True, False))
assembly = cq.Assembly(name="Littelfuse_0463015_ER_nominal_envelope")
assembly.add(body, name="nominal_body", color=cq.Color(0.82, 0.80, 0.75))
target = Path("assets/3d/generated__Littelfuse_463_Nano2_SMD.step")
assembly.save(str(target), exportType="STEP")
