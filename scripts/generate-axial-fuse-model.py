"""Build the project review envelope for the two soldered Littelfuse 487 fuses."""
from pathlib import Path
from math import sqrt
import cadquery as cq
# Catalogue dimensions are 21.5 × Ø5.5 mm. Lead diameter, bend radius and
# standoff are provisional project assumptions to confirm on actual parts.
# Shape frame uses the center of pin 1 as origin, with the PCB top at Z=0.
pitch = 37.5
diameter = 5.5
length = 21.5
standoff = 1.0
lead_diameter = 1.0
bend_radius = 2.0
trim = 1.6 + 2.0  # 1.6 mm board and 2 mm maximum projection
axis_height = standoff + diameter / 2
body_start = (pitch - length) / 2
body = cq.Solid.makeCylinder(diameter / 2,length,cq.Vector(body_start,0,axis_height),cq.Vector(1,0,0))
r = bend_radius
path = (cq.Workplane("XZ").moveTo(0, -trim).lineTo(0, axis_height-r)
        .threePointArc((r-r/sqrt(2), axis_height-r+r/sqrt(2)), (r, axis_height))
        .lineTo(body_start, axis_height).wire())
lead = cq.Workplane("XY",origin=(0,0,-trim)).circle(lead_diameter/2).sweep(path).val()
assembly = cq.Assembly(name='LF_487_formed_axial_review_envelope')
assembly.add(body, name='fuse_body', color=cq.Color(.80,.79,.75))
assembly.add(lead, name='formed_lead_1', color=cq.Color(.65,.67,.68))
assembly.add(lead.mirror('YZ',(pitch/2,0,0)), name='formed_lead_2', color=cq.Color(.65,.67,.68))
assembly.save(str(Path('assets/3d/generated__Littelfuse_487_Axial_P37.50mm.step')))
bounds=assembly.toCompound().BoundingBox()
print('Envelope height above PCB (mm):', round(bounds.zmax, 3))
