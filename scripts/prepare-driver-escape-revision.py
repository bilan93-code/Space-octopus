"""Carry reviewed copper onto the final driver bypass placement and add escapes."""
import json, sys
from pathlib import Path
from shapely.geometry import Point, LineString

root = Path('routing-work/motor-mount-revision')
fresh = json.loads((root/'adc-layout-fresh.circuit.json').read_text())
old = json.loads((root/'grid-coarse/working.circuit.json').read_text())
net_names = {a['source_net_id']: a['name'] for a in old if a['type']=='source_net'}
net_ids = {a['name']: a['source_net_id'] for a in fresh if a['type']=='source_net'}
trace_ids = {n:a['source_trace_id'] for a in fresh if a['type']=='source_trace' for n in a.get('connected_source_net_ids',[])}
fresh = [a for a in fresh if a['type'] not in ['pcb_trace','pcb_via','pcb_copper_pour','cad_component'] and not a['type'].endswith(('_error','_warning'))]
traces = []
for a in old:
    if a['type']!='pcb_trace': continue
    name = net_names[a['connection_name']]
    a = {**a,'connection_name':net_ids[name],'source_trace_id':trace_ids[net_ids[name]]}
    # The former bypass pad is no longer a valid ground via landing.
    if any(v['route_type']=='via' and abs(v['x']+25.5)<.01 and abs(v['y']+1.775)<.01 for v in a['route']):continue
    traces.append(a)
path = root/'driver-escaped.circuit.json'
path.write_text(json.dumps(fresh+traces))
s={'__name__':'driver_geometry'}
sys.argv=['check-copper.py',str(path),'/tmp/driver-escape-unused.json']
exec(compile(Path('scripts/check-copper.py').read_text().split('# Distinct-net copper')[0],'geometry','exec'),s)
new=[]
for name,points in [
    ('IW_RAW',[(-22.95,-2.25),(-24.75,-2.4)]),
    ('IV_RAW',[(-22.95,-1.75),(-25.9,-1.75)]),
    ('IU_RAW',[(-22.95,-1.25),(-25.65,-1.25),(-26,-.9)]),
]:
    x,y=points[-1]
    new.append({'type':'pcb_trace','pcb_trace_id':'seed_adc_escape_'+name,
        'connection_name':net_ids[name],'source_trace_id':trace_ids[net_ids[name]],
        'route':[{'route_type':'wire','x':x,'y':y,'layer':'bottom','width':.15} for x,y in points]+
        [{'route_type':'via','x':x,'y':y,'from_layer':'bottom','to_layer':'inner1','layers':s['layers'],'via_diameter':.4,'via_hole_diameter':.2},
         {'route_type':'wire','x':x,'y':y,'layer':'inner1','width':.15}]})
reinforced=json.loads((root/'input-reinforced.circuit.json').read_text())
power=next(a for a in reinforced if a['type']=='pcb_trace' and any(v.get('width')==4.5 for v in a['route']))
name=net_names[power['connection_name']]
new.append({**power,'pcb_trace_id':'seed_input_parallel_inner2','connection_name':net_ids[name],'source_trace_id':trace_ids[net_ids[name]]})
guard_points=[]
for b in json.loads(Path('data/kelvin-routing.json').read_text())['branches']:
    guard_points.extend(b[k] for k in ['sourceVia','pickupGroundVia','positiveSourceVia','positivePickupVia'])
protected=set()
for t in traces:
    if t['pcb_trace_id'].startswith('kelvin_') or any(v.get('width',0)>=.6 for v in t['route']):protected.add(t['pcb_trace_id'])
    if any(v['route_type']=='via' and any(Point(v['x'],v['y']).distance(Point(*p))<1e-5 for p in guard_points) for v in t['route']):protected.add(t['pcb_trace_id'])
bad=set()
def displace(g,ls,n):
    for a in s['items']:
        if a['net']==n or a['layer'] not in ls or g.distance(a['g'])>=.2-1e-5:continue
        ident=a['id'].rsplit(':',1)[0]
        if a['kind']=='pad' or ident in protected:raise RuntimeError('Protected copper blocks revision: '+str((ident,a['kind'],s['nets'].get(a['net']),a['g'].bounds)))
        bad.add(ident)
for t in new:
    for i,v in enumerate(t['route']):
        if v['route_type']=='via':displace(Point(v['x'],v['y']).buffer(v['via_diameter']/2,quad_segs=32),s['layers'],t['connection_name'])
        elif i:
            a=t['route'][i-1]
            displace(LineString([(a['x'],a['y']),(v['x'],v['y'])]).buffer(v['width']/2,quad_segs=32),[v['layer']],t['connection_name'])
# Clear ordinary traces under the moved bypass pads as well.
for a in s['items']:
    if a['kind']=='pad' and s['portlabel'](a.get('port')).startswith('C307.'):
        displace(a['g'],[a['layer']],a['net'])
result=fresh+[t for t in traces if t['pcb_trace_id'] not in bad]+new
ids=[a['pcb_trace_id'] for a in result if a['type']=='pcb_trace']
assert len(ids)==len(set(ids))
path.write_text(json.dumps(result))
(root/'driver-escape-preparation.json').write_text(json.dumps({'displaced':sorted(bad),'added':[a['pcb_trace_id'] for a in new]},indent=2)+'\n')
print('Prepared',path,'displaced',len(bad),'ordinary copper items.')
