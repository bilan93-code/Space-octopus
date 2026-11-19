"""Generate a conservative Rubycon ZLJ maximum envelope, not a vendor CAD model."""
import hashlib
import json
from pathlib import Path
import cadquery as cq

spec = json.loads(Path('data/bulk-watchdog-selection.json').read_text())['bulk']
d = spec['maximum_can_diameter_mm']
h = spec['maximum_can_length_mm']
seat = spec['assembly_seating_allowance_mm']
pitch = spec['lead_pitch_mm']
# End the sleeve below the metal lid so coincident top faces do not flicker in 3D.
body = cq.Workplane('XY').center(pitch/2, 0).circle(d/2).extrude(h-.12).translate((0,0,seat))
top = cq.Workplane('XY').center(pitch/2, 0).circle(d/2-.25).extrude(.12).translate((0,0,seat+h-.12))
lead_shapes = [cq.Workplane('XY').center(x,0).circle(.4).extrude(seat+3.6) .translate((0,0,-3.6)) for x in [0,pitch]]
assembly = cq.Assembly(name='Rubycon_ZLJ_100V_820uF_MaximumEnvelope')
assembly.add(body,name='Maximum_can_envelope',color=cq.Color(.10,.16,.24))
assembly.add(top,name='Top_surface',color=cq.Color(.75,.76,.76))
for i,lead in enumerate(lead_shapes):
    assembly.add(lead,name=f'Trimmed_lead_{i+1}',color=cq.Color(.65,.67,.68))
target = Path('assets/3d/generated__Rubycon_ZLJ_D18_40_MaxEnvelope.step')
assembly.save(str(target),exportType='STEP')
report = {'model':str(target),'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),
          'manufacturer_model':False,'can_max_diameter_mm':d,'can_max_length_mm':h,
          'seating_allowance_mm':seat,'outward_projection_mm':h+seat,
          'lead_pitch_mm':pitch,'lead_diameter_mm':.8,'lead_projection_below_board_mm':2,
          'required_outward_clearance_including_vent_mm':h+seat+spec['reserved_vent_space_mm'],
          'source':'Rubycon ZLJ manufacturer series PDF, dimensions p81 and 100V/820uF/18x40 row p83; archived public copy.',
          'limitations':'Envelope for mechanical clearance; polarity marking and pressure vent are not vendor geometry. Physically trim leads to <=2mm below the PCB.'}
Path('assets/3d/bulk-cap-envelope-provenance.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
