"""Verify drill-to-drill web, including holes on the same electrical net."""
import json,sys,math
from pathlib import Path
from shapely.geometry import Point,LineString
from shapely.affinity import rotate
from shapely.strtree import STRtree
src=Path(sys.argv[1] if len(sys.argv)>1 else 'output/space-octopus.circuit.json');out=Path(sys.argv[2] if len(sys.argv)>2 else 'output/drill-audit.json');j=json.loads(src.read_text());holes=[];seen={};conflicts=[]
def add(x,y,diameter,identity,shape=None):
 key=(round(x,6),round(y,6),round(diameter,6))
 if key in seen:return
 seen[key]=identity;holes.append({'g':shape if shape is not None else Point(x,y).buffer(diameter/2,quad_segs=32),'id':identity})
for a in j:
 if a['type']=='pcb_trace':
  for k,v in enumerate(a['route']):
   if v['route_type']=='via':add(v['x'],v['y'],v.get('via_hole_diameter',v.get('hole_diameter',.3)),a['pcb_trace_id']+':via'+str(k))
 elif a['type'] in ['pcb_via','pcb_hole','pcb_plated_hole']:
  identity=a.get('pcb_via_id',a.get('pcb_hole_id',a.get('pcb_plated_hole_id')))
  if 'hole_diameter' in a:add(a['x'],a['y'],a['hole_diameter'],identity)
  elif 'hole_width' in a:
   w,h=a['hole_width'],a['hole_height'];r=min(w,h)/2;g=LineString([(a['x']-max(0,w/2-r),a['y']-max(0,h/2-r)),(a['x']+max(0,w/2-r),a['y']+max(0,h/2-r))]).buffer(r,quad_segs=32);g=rotate(g,a.get('ccw_rotation',0),origin=(a['x'],a['y']));add(a['x'],a['y'],min(w,h),identity,g)
tree=STRtree([x['g'] for x in holes]);minimum=.2
for k,a in enumerate(holes):
 for index in tree.query(a['g'],predicate='dwithin',distance=minimum):
  index=int(index)
  if index<=k:continue
  b=holes[index];d=a['g'].distance(b['g'])
  if d<minimum-1e-5:conflicts.append({'a':a['id'],'b':b['id'],'edgeGapMm':round(d,6)})
report={'status':'failed' if conflicts else 'passed','source':str(src),'physicalDrills':len(holes),'minimumDrillEdgeGapMm':minimum,'violationCount':len(conflicts),'violations':conflicts,'notes':'Exact duplicate drill definitions are counted once. The routed central cutout is checked by the copper and assembly audits.'};out.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2));raise SystemExit(bool(conflicts))
