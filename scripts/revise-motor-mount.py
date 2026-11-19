"""Develop the motor-facing clearance revision without changing the baseline.
Use --apply only after the candidate's exact face envelopes pass inspection.
"""
import json,sys,math
from pathlib import Path

apply='--apply' in sys.argv
baseline=Path('routing-work/motor-mount-revision/baseline')
previous=json.loads((baseline/'data/placement.json').read_text())
# Reuse the established body/lead transforms and spatial placement predicate.
sys.argv=['place-components.py','--dry-run']
scope={'__name__':'mount_placement'}
exec(compile(Path('scripts/place-components.py').read_text().split('\nfixed={}')[0],'placement-geometry','exec'),scope)
parts=scope['parts'];by=scope['by'];cat=scope['cat'];put=scope['try_put'];placed=scope['placed']
phoenix='TerminalBlock_Phoenix/TerminalBlock_Phoenix_MKDS-3-{}-5.08_1x0{}_P5.08mm_Horizontal'
changes={'J1':phoenix.format(2,2),'J2':phoenix.format(3,3),'J11':phoenix.format(2,2),'J10':'Connector_JST/JST_GH_SM06B-GHS-TB_1x06-1MP_P1.25mm_Horizontal'}
for ref,n in [('J3',2),('J8',3),('J5',4),('J6',4)]:changes[ref]=f'Connector_JST/JST_GH_BM0{n}B-GHS-TBT_1x0{n}-1MP_P1.25mm_Vertical'
for ref,footprint in changes.items():by[ref]['footprint']=footprint
anchors={}
for ref in ['H1','H2','H3','H4','H5','H6','F1','F2','Q1','Q2','Q3','Q4','Q5','Q6','RSH1','RSH2','RSH3','C3','C4','L101','U1','U2','U3','U4','U5','U6','U7','U8','U19']:
 p=previous[ref];anchors[ref]=(*p['bodyCenter'],p['rotation'],p['layer'])
anchors.update({
 'C1':(-35,12.1,90,'top'),'C2':(-35,-12.1,90,'top'),
 'C5':(-19.3,-17.3,270,'top'),'Q7':(-31.5,-24.5,0,'bottom'),
 'J1':(-48.5,0,90,'top'),'J2':(30.5,-31.5,90,'top'),'J11':(-30.5,-34.8,90,'top'),
 'J10':(-30.8,37.2,90,'top'),'J4':(-25.22,29.2,90,'top'),
 'J3':(-27.5,0,0,'top'),
 'J5':(-24,23.9,0,'top'),'J6':(19,-24,90,'top'),
 'J7':(48.7,-17,0,'top'),'J8':(49.5,9,90,'top'),
 'J9':(-15,14,90,'top'),
 'U17':(-24,-14,0,'bottom'),
 'C307':(-25.5,-2.6,270,'bottom'),'C407':(-26.6,-6.2,90,'bottom'),
 'C905':(-20.7,-24.5,0,'bottom'),
})
for ref,pose in anchors.items():
 if not put(ref,*pose[:3],layer=pose[3],fixed=True):
  recovered=False
  if ref.startswith('J') or ref in ['C307','C407','C905']:
   offsets=sorted((dx*dx+dy*dy,dx/10,dy/10) for dx in range(-40,41) for dy in range(-40,41))
   for _,dx,dy in offsets:
    for rot in dict.fromkeys([pose[2],(pose[2]+180)%360,(pose[2]+90)%360,(pose[2]+270)%360]):
     if put(ref,pose[0]+dx,pose[1]+dy,rot,layer=pose[3],fixed=True):recovered=True;break
    if recovered:break
  if recovered:continue
  from shapely.affinity import translate
  from shapely.geometry import Point
  shapes={l:translate(s,pose[0],pose[1]) for l,s in scope['local_shapes'](ref,pose[3],pose[2]).items()}
  reasons=[]
  for l,s in shapes.items():
   if by[ref]['kind']!='hole' and not scope['usable_test'].covers(s):reasons.append('edge/opening')
   for r,v in placed.items():
    for ll,geom in v['assemblyEnvelopes'].items():
     if ll!=l:continue
     from shapely.geometry import shape
     d=s.distance(shape(geom))
     if d<scope['gap']-1e-6:reasons.append(f'{r} {l} gap {d:.3f}')
  raise RuntimeError(f'Anchor {ref} {pose} does not fit: {reasons}')

# Maintain converter, MCU, ADC and reference cells whenever space permits.
functional={'C101','C102','C103','C104','C105','C106','C107','R101','R102','R103','R104','L102','C108','C109','R105','R106','C110','C111','C112','C113','C201','C202','C203','C204','C205','C206','C207','C301','C302','C303','C304','C305','C306','C501','C502','C503','C504','C511','C512','FB201'}
preferred={'C904':(-21,-12,'bottom'),'R906':(-23,-17,'bottom'),'R907':(-25.2,-17,'bottom'),'R908':(-21,-20.7,'bottom')}
def area(p):
 b=cat[p['footprint']]['box'];return (b[2]-b[0])*(b[3]-b[1])
def priority(p):return (0 if p['ref'] in functional else 1 if p['ref'] in preferred else 2 if p['kind'] in ['chip','inductor'] else 3,-area(p),p['ref'])
moved=[]
for p in sorted(parts,key=priority):
 ref=p['ref']
 if ref in placed:continue
 old=previous[ref];x,y=old['bodyCenter'];face=old['layer'];rot=old['rotation']
 if ref in preferred:x,y,face=preferred[ref]
 if put(ref,x,y,rot,layer=face,fixed=ref in functional):continue
 found=False
 # Prefer a nearby shift over changing a functional part's mounting face.
 for rmax in [4,10,120]:
  offsets=sorted((dx*dx+dy*dy,dx/2,dy/2) for dx in range(-int(rmax*2),int(rmax*2)+1) for dy in range(-int(rmax*2),int(rmax*2)+1) if dx*dx+dy*dy<=(rmax*2)**2)
  for side in [face,'bottom' if face=='top' else 'top']:
   for _,dx,dy in offsets:
    for rotation in dict.fromkeys([rot,(rot+180)%360,(rot+90)%360,(rot+270)%360]):
     if put(ref,x+dx,y+dy,rotation,layer=side):found=True;break
    if found:break
   if found:break
  if found:break
 if not found:raise RuntimeError('No legal placement for '+ref)

for ref,v in placed.items():
 old=previous[ref]
 if v['layer']!=old['layer'] or v['rotation']!=old['rotation'] or math.dist(v['bodyCenter'],old['bodyCenter'])>1e-5 or ref in changes:
  moved.append({'ref':ref,'oldFace':old['layer'],'newFace':v['layer'],'oldCenter':old['bodyCenter'],'newCenter':v['bodyCenter'],'rotation':v['rotation'],'footprintChanged':ref in changes})
out=Path('routing-work/motor-mount-revision');out.mkdir(parents=True,exist_ok=True)
(out/'candidate-placement.json').write_text(json.dumps(placed,indent=2)+'\n')
(out/'placement-changes.json').write_text(json.dumps(moved,indent=2)+'\n')
print('Placed',len(placed),'items;',len(moved),'moved or changed. All connectors and tall capacitors face outward.')
for item in moved:print(item['ref'],item['newFace'],item['newCenter'])
if apply:
 Path('data/placement.json').write_text(json.dumps(placed,indent=2)+'\n')
 for name in ['input-supplies-mcu-driver-inverter','sensing-fault-interfaces-brake','mechanical']:
  path=Path('data')/(name+'.json');items=json.loads(path.read_text())
  for p in items:
   if p['ref'] not in changes:continue
   p['footprint']=changes[p['ref']];p['provisional']=True
   if p['ref'].startswith('J') and p['ref'] not in ['J1','J2','J11']:
    n={'J3':2,'J8':3,'J5':4,'J6':4,'J10':6}[p['ref']];p['mpn']='SM06B-GHS-TB' if p['ref']=='J10' else f'BM0{n}B-GHS-TBT';p['provisionalReason']='JST GH connector candidate selected for the outward-facing interface. Confirm mating harness, current budget and manufacturer drawing. Land pattern follows the installed KiCad library.'
   else:p['mpn']='MKDS 3/'+str(3 if p['ref']=='J2' else 2)+'-5.08';p['provisionalReason']='Compact Phoenix Contact MKDS 3 terminal candidate. Confirm exact ordering code, >=100 Vdc/current ratings, wire size and manufacturer drawing before fabrication. Land pattern follows the installed KiCad library.'
  path.write_text(json.dumps(items,indent=2)+'\n')
