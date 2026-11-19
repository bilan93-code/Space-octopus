"""Replan from original footprint artwork, restoring the plan if rendering fails."""
import json,subprocess,sys
from pathlib import Path
plan=Path('data/silkscreen-plan.json');original=plan.read_bytes()
target=Path('routing-work/motor-mount-revision/original-artwork.circuit.json')
target.parent.mkdir(parents=True,exist_ok=True)
try:
 data=json.loads(original);data['enabled']=False;plan.write_text(json.dumps(data))
 # Artwork capture needs current footprints and mask openings, not another
 # full route replay. Preserve the actual routed vias as mask obstacles.
 routed=json.loads(Path('output/space-octopus.circuit.json').read_text())
 subprocess.run(['node_modules/.bin/tsx','scripts/build.tsx','--capture-only','--json-only','--json-output='+str(target)],check=True)
 capture=json.loads(target.read_text())
 def pads(items):
  return sorted((p['type'],round(p['x'],7),round(p['y'],7),p.get('layer',''),tuple(p.get('layers',[]))) for p in items if p['type'] in ['pcb_smtpad','pcb_plated_hole'])
 assert pads(capture)==pads(routed),'Artwork capture changed physical pad positions.'
 for v in routed:
  if v['type']=='pcb_via':capture.append({k:value for k,value in v.items() if k!='pcb_port_ids'})
 target.write_text(json.dumps(capture))
finally:
 plan.write_bytes(original)
subprocess.run([sys.executable,'scripts/prepare-silkscreen.py',str(target)],check=True)
