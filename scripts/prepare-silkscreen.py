"""Place readable references and clip artwork away from mask openings."""
import json,sys,math,csv
from pathlib import Path
from shapely.geometry import Point,LineString,box,shape
from shapely.ops import unary_union
from shapely import prepare
from shapely.strtree import STRtree
src=Path(sys.argv[1] if len(sys.argv)>1 else 'output/space-octopus.circuit.json');s={'__name__':'silk_geometry'};sys.argv=['check-copper.py',str(src),'/tmp/silk-unused.json']
exec(compile(Path('scripts/check-copper.py').read_text().split('# Distinct-net copper')[0],'geometry','exec'),s)
j=s['j'];placement=json.loads(Path('data/placement.json').read_text());parts=sum([json.loads(Path('data/'+n+'.json').read_text()) for n in ['input-supplies-mcu-driver-inverter','sensing-fault-interfaces-brake','mechanical']],[])
by={p['ref']:p for p in parts};board=Point(0,0).buffer(55.4,quad_segs=256).difference(Point(0,0).buffer(14.6,quad_segs=128))
for h in s['bytype']['pcb_hole']:board=board.difference(Point(h['x'],h['y']).buffer(h['hole_diameter']/2+.4))
mask_margins={p.get('pcb_smtpad_id',p.get('pcb_plated_hole_id')):p.get('soldermask_margin',0) for p in s['bytype']['pcb_smtpad']+s['bytype']['pcb_plated_hole']}
open_shapes={l:[a['g'].buffer(mask_margins.get(a['id'],0)) for a in s['items'] if a['layer']==l and a['kind'] in ['pad','via']] for l in ['top','bottom']}
openings={l:unary_union(gs).buffer(.25) for l,gs in open_shapes.items()}
open_trees={l:STRtree(v) for l,v in open_shapes.items()}
bodies={l:unary_union([shape(v['assemblyEnvelopes'][l]) for ref,v in placement.items() if l in v['assemblyEnvelopes'] and by[ref]['kind'] not in ['testpoint','fiducial']]).buffer(.12) for l in ['top','bottom']}
occupied={l:[] for l in openings};texts=[];manifest=[]
prepare(board)
for l in openings:prepare(openings[l]);prepare(bodies[l])
for text,x,y in [('SPACE OCTOPUS',17,48),('48V / MOUNT',-16,48)]:
 font=.8;width=len(text)*font*.8+.25;height=font+.3;g=box(x-width/2,y-height/2,x+width/2,y+height/2)
 if board.covers(g) and not g.intersects(openings['top']) and not g.intersects(bodies['top']):occupied['top'].append(g);texts.append({'text':text,'x':x,'y':y,'fontSize':font,'layer':'top','purpose':'identity'})
# Mark each exposed harness termination at the pad rather than relying on
# connector numbering after the plastic blocks have been removed.
wire_names={'DC_IN':'DC+','GND':'GND','PH_U':'U','PH_V':'V','PH_W':'W',
            'BRAKE_PLUS':'BR+','BRAKE_DRAIN':'BR_SW'}
for pad in s['bytype']['pcb_plated_hole']:
 pid=pad.get('pcb_port_id')
 if not pid:continue
 ref,pin=s['portlabel'](pid).split('.')
 if ref not in by or not by[ref]['footprint'].startswith('Wire/DirectSolder_'):continue
 net=by[ref]['pins'][pin];label=wire_names[net];layer=placement[ref]['layer']
 font=.8;width=max(.8,len(label)*font*.8+.25);height=font+.3
 # All three banks run vertically. Keep each legend on its terminal's row.
 px,py=pad['x'],pad['y']
 for gap in [.55,.8,1.05,1.3,1.55,1.8,2.3]:
  done=False
  for side in [1,-1]:
   x=px+side*(2.3+gap+width/2)
   g=box(x-width/2,py-height/2,x+width/2,py+height/2)
   if not board.covers(g) or g.intersects(openings[layer]) or g.intersects(bodies[layer]) or any(g.distance(o)<.25 for o in occupied[layer]):continue
   occupied[layer].append(g)
   texts.append({'text':label,'x':round(x,5),'y':py,'fontSize':font,'layer':layer,
                 'purpose':'wire terminal','terminal':f'{ref}.{pin}','net':net})
   done=True;break
  if done:break
 else:raise RuntimeError(f"No clear silkscreen location for wire terminal {ref}.{pin} {net}")
for ref,p in sorted(by.items(),key=lambda x:(0 if x[1]['kind'] in ['connector','chip'] else 1,-len(x[0]),x[0])):
 if p['kind'] in ['hole','fiducial']:continue
 v=placement[ref];l=v['layer'];own=shape(v['assemblyEnvelopes'][l]);cx,cy=v['bodyCenter'];font=.8;width=max(.8,len(ref)*font*.8+.25);height=font+.3
 candidates=[]
 bounds=own.bounds
 for d in [.7,1.2,1.7,2.2,2.7,3.2,3.7,4.2]:
  for x,y in [(cx,bounds[3]+d),(cx,bounds[1]-d),(bounds[0]-width/2-d,cy),(bounds[2]+width/2+d,cy)]:candidates.append((math.hypot(x-cx,y-cy),x,y))
 placed=False
 for _,x,y in sorted(candidates):
  g=box(x-width/2,y-height/2,x+width/2,y+height/2)
  if not board.covers(g) or g.intersects(openings[l]) or g.intersects(bodies[l]) or any(g.distance(o)<.25 for o in occupied[l]):continue
  occupied[l].append(g);texts.append({'text':ref,'x':x,'y':y,'fontSize':font,'layer':l});manifest.append([ref,l,'silkscreen',round(x,3),round(y,3)]);placed=True;break
 if not placed:manifest.append([ref,l,'fabrication drawing / BOM','',''])
# Preserve source footprint artwork, including polarity cues, with mask clearance.
paths=[]
clip_cache={};label_geometry={l:unary_union(occupied[l]) for l in openings}
print('Placed references; clipping footprint artwork.',flush=True)
for e in j:
 if e['type'] not in ['pcb_silkscreen_path','pcb_silkscreen_circle']:continue
 l=e.get('layer','top')
 if l not in openings:continue
 stroke=max(.12,e.get('stroke_width',.12))
 if e['type']=='pcb_silkscreen_path':coords=[(p['x'],p['y']) for p in e['route']]
 else:
  c=e['center'];coords=[(c['x']+e['radius']*math.cos(k*math.pi/64),c['y']+e['radius']*math.sin(k*math.pi/64)) for k in range(129)]
 if len(coords)<2:continue
 key=(l,stroke)
 if key not in clip_cache:clip_cache[key]=(board.buffer(-stroke/2),label_geometry[l].buffer(.18+stroke/2))
 boundary,labels=clip_cache[key];rawline=LineString(coords)
 nearby=open_trees[l].query(rawline,predicate='dwithin',distance=.25+stroke/2)
 blocked=unary_union([open_shapes[l][int(k)].buffer(.25+stroke/2) for k in nearby])
 line=rawline.intersection(boundary).difference(blocked).difference(labels)
 segments=[line] if line.geom_type=='LineString' else [g for g in getattr(line,'geoms',[]) if g.geom_type=='LineString']
 for g in segments:
  if g.length<.25:continue
  paths.append({'layer':l,'strokeWidth':stroke,'route':[{'x':x,'y':y} for x,y in g.coords]})
Path('data/silkscreen-plan.json').write_text(json.dumps({'enabled':True,'texts':texts,'paths':paths},indent=2)+'\n')
with Path('output/reference-locations.csv').open('w') as f:w=csv.writer(f);w.writerow(['Reference','Face','Location','X mm','Y mm']);w.writerows(manifest)
reference_count=sum(not t.get('purpose') for t in texts)
Path('output/silkscreen-audit.json').write_text(json.dumps({'status':'passed','referencesOnSilk':reference_count,'referencesOnFabOnly':len(manifest)-reference_count,'identityLabels':sum(t.get('purpose')=='identity' for t in texts),'wireTerminalLabels':sum(t.get('purpose')=='wire terminal' for t in texts),'clippedArtworkSegments':len(paths),'fontSizeMm':.8,'maskClearanceMm':.25,'note':'References that do not fit remain in assembly drawings, BOM and KiCad fabrication layer. Stock polarity artwork is clipped around mask openings.'},indent=2)+'\n')
print('Silkscreen:',reference_count,'references;',len(manifest)-reference_count,'on fabrication layer;',len(paths),'clipped artwork paths.')
