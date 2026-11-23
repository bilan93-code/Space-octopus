"""Audit the rendered silk against actual mask openings, rather than its plan."""
import json,sys,math,hashlib
from pathlib import Path
from shapely.geometry import Point,LineString,box,Polygon
from shapely.strtree import STRtree
src=Path(sys.argv[1] if len(sys.argv)>1 else 'output/space-octopus.circuit.json');s={};sys.argv=['check-copper.py',str(src),'/tmp/silk-check-unused']
exec(compile(Path('scripts/check-copper.py').read_text().split('# Distinct-net copper')[0],'g','exec'),s)
mask_margins={p.get('pcb_smtpad_id',p.get('pcb_plated_hole_id')):p.get('soldermask_margin',0) for p in s['bytype']['pcb_smtpad']+s['bytype']['pcb_plated_hole']}
openings={l:[a['g'].buffer(mask_margins.get(a['id'],0)) for a in s['items'] if a['layer']==l and a['kind'] in ['pad','via']] for l in ['top','bottom']};trees={l:STRtree(gs) for l,gs in openings.items()};errors=[];texts=[];path_count=0
outline=Polygon([(p['x'],p['y']) for p in s['bytype']['pcb_board'][0]['outline']]).buffer(-.4)
for c in s['bytype']['pcb_cutout']:outline=outline.difference(Point(c['center']['x'],c['center']['y']).buffer(c['radius']+.4))
for e in s['j']:
 if e['type']=='pcb_silkscreen_text':
  l=e.get('layer','top');p=e['anchor_position'];f=e['font_size'];w=max(.8,len(e['text'])*f*.8+.25);h=f+.3;g=box(p['x']-w/2,p['y']-h/2,p['x']+w/2,p['y']+h/2)
  if f<.8-1e-5:errors.append('Small text '+e['text'])
  if not outline.covers(g):errors.append('Text at edge/opening '+e['text'])
  if len(trees[l].query(g,predicate='dwithin',distance=.2-1e-5)):errors.append('Text over mask opening '+e['text'])
  for label,layer,other in texts:
   if layer==l and g.distance(other)<.1:errors.append('Text overlap '+e['text']+'/'+label)
  texts.append((e['text'],l,g))
 elif e['type']=='pcb_silkscreen_path':
  if len(e['route'])<2:continue
  l=e.get('layer','top');g=LineString([(p['x'],p['y']) for p in e['route']]).buffer(e.get('stroke_width',.12)/2);path_count+=1
  if len(trees[l].query(g,predicate='dwithin',distance=.2-1e-5)):errors.append('Artwork over mask opening '+e['pcb_silkscreen_path_id'])
labels = [text for text, layer, area in texts]
if 'F1' in labels or labels.count('F2') != 1:
 errors.append('Power fuse references must identify F2 only')
wire_plan = [row for row in json.loads(Path('data/silkscreen-plan.json').read_text())['texts']
             if row.get('purpose') == 'wire terminal']
by_wire = {s['portlabel'](pid): s['nets'].get(s['portnet'].get(pid)) for pid in s['ports']}
expected_wires = {'J1.1','J1.2','J2.1','J2.2','J2.3','J11.1','J11.2'}
if {row.get('terminal') for row in wire_plan} != expected_wires or len(wire_plan) != len(expected_wires):
 errors.append('Missing or duplicate power wire label')
for row in wire_plan:
 terminal = row['terminal']
 actual_net = by_wire.get(terminal)
 if not actual_net or actual_net != row['net']:
  errors.append(f'{terminal} wiring legend names {row["net"]}, rendered pin has {actual_net}')
 if not any(e['text'] == row['text'] and e['layer'] == row['layer'] and
            math.dist((e['anchor_position']['x'],e['anchor_position']['y']),(row['x'],row['y'])) < .001
            for e in s['bytype']['pcb_silkscreen_text']):
  errors.append(f'{terminal} physical pin legend missing at its planned location')

report={'status':'failed' if errors else 'passed','circuitJsonSha256':hashlib.sha256(src.read_bytes()).hexdigest(),'wireLabels':{r['terminal']:r['text'] for r in wire_plan},'textCount':len(texts),'artworkPaths':path_count,'minimumCheckedMaskClearanceMm':.2,'errors':errors,'limitations':'Text reservations are conservative boxes. Native KiCad DRC separately checks actual stroke-font geometry.'};Path('output/silkscreen-rendered-audit.json').write_text(json.dumps(report,indent=2)+'\n');print('Rendered silkscreen:',report['status'],len(errors),'findings');print('\n'.join(errors[:10]));raise SystemExit(bool(errors))
