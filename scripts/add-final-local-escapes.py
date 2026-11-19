"""Add constrained local escapes where fixed reference tracks fence in a pad."""
import json,sys
from pathlib import Path
from shapely.geometry import Point,LineString,Polygon,box
from shapely.ops import unary_union

src=Path(sys.argv[1]);out=Path(sys.argv[2]);s={}
sys.argv=['check-copper.py',str(src),'/tmp/local-escape-unused.json']
exec(compile(Path('scripts/check-copper.py').read_text().split('# Distinct-net copper')[0],'g','exec'),s)
j=s['j'];trace_ids={n:a['source_trace_id'] for a in s['bytype']['source_trace'] for n in a.get('connected_source_net_ids',[])}
guard=[]
for b in json.loads(Path('data/kelvin-routing.json').read_text())['branches']:
    guard.extend(b[k] for k in ['sourceVia','pickupGroundVia','positiveSourceVia','positivePickupVia'])
protected=set()
for t in s['bytype']['pcb_trace']:
    if t['pcb_trace_id'].startswith(('seed_','kelvin_','plane_stitch_')) or any(v.get('width',0)>=.6 for v in t['route']):protected.add(t['pcb_trace_id'])
    if any(v['route_type']=='via' and any(Point(v['x'],v['y']).distance(Point(*p))<1e-5 for p in guard) for v in t['route']):protected.add(t['pcb_trace_id'])
for a in s['items']:
    if a['kind']=='via' and a['g'].bounds[2]-a['g'].bounds[0]>=.59:protected.add(a['id'].rsplit(':',1)[0])
outline=Polygon([(v['x'],v['y']) for v in s['bytype']['pcb_board'][0]['outline']]).buffer(-.5)
blocked=[Point(v['x'],v['y']).buffer(v['hole_diameter']/2+.5,quad_segs=128) for v in s['bytype']['pcb_hole']]
blocked.extend(Point(v['center']['x'],v['center']['y']).buffer(v['radius']+.5,quad_segs=128) for v in s['bytype']['pcb_cutout'] if v['shape']=='circle')
refs={v['pcb_component_id']:s['sources'].get(v.get('source_component_id'),'') for v in s['bytype']['pcb_component']}
blocked.extend(box(v['x']-4.75,v['y']-4.75,v['x']+4.75,v['y']+4.75).buffer(.2) for v in s['bytype']['pcb_hole'] if refs.get(v.get('pcb_component_id'),'').startswith('H'))
blocked=unary_union(blocked)
retired={t['pcb_trace_id'] for t in s['bytype']['pcb_trace'] if s['nets'].get(t.get('connection_name'))=='HSE_CLK' and t['pcb_trace_id'].startswith('seed_') and any(v['route_type']=='via' and abs(v['x']-28.675)<1e-5 and abs(v['y']-1.75)<1e-5 for v in t['route'])}
assert len(retired)<=1,'Unexpected duplicate clock escape barrels.'
new=[];bad=set(retired)
for label,point in [
    ('C512.1',(-21.1,-8.875)),('R501.1',(-11.475,-10.8)),
    ('R306.1',(-16.175,-22.8)),('U1.5',(29,1.75)),
    ('R303.1',(-15.8,-17.075)),('R510.1',(-42.5,19.825)),
    ('R311.1',(-39,28.325)),('U17.6',(-28.1375,-12.22)),
    ('U1.45',(18,2.25)),('U6.4',(37.275,-2.8525)),
    ('U2.30',(-25.95,2.25)),('R302.1',(-30.4,-5.275)),
    ('R306.2',(-17.425,-21.7)),('J6.2',(22.95,-25.325)),
    ('U1.53',(20.25,4.175)),('U1.19',(24.75,-4.175)),
    ('R201.2',(51.825,-11)),
    ('U20.1',(29.1425,-11.125)),('U18.6',(26.725,-21.3825)),
    ('U1.20',[(24.25,-4.575),(24.15,-4.475),(24.15,-3.875)]),
    ('D4.1',[(35.12,-16.025),(37.65,-16.025),(40.52,-16.8625)]),
]:
    identity='seed_local_escape_'+label.replace('.','_')
    if any(a.get('pcb_trace_id')==identity for a in j):continue
    p=next(p for k,p in s['ports'].items() if s['portlabel'](k)==label)
    n=s['portnet'][p['pcb_port_id']];face=p['layers'][0]
    points=point if isinstance(point[0],(tuple,list)) else [point];x,y=points[-1]
    via=Point(x,y).buffer(.2,quad_segs=32)
    wire=LineString([(p['x'],p['y']),*points]).buffer(.075,quad_segs=32)
    assert outline.covers(via) and outline.covers(wire) and via.intersection(blocked).area<1e-8 and wire.intersection(blocked).area<1e-8, 'Local escape crosses a mechanical boundary.'
    for a in s['items']:
        if a['net']==n or a['kind']=='pour':continue
        if via.distance(a['g'])>=.2-1e-5 and (a['layer']!=face or wire.distance(a['g'])>=.2-1e-5):continue
        ident=a['id'].rsplit(':',1)[0]
        if a['kind']=='pad' or ident in protected:raise RuntimeError('Local escape blocks protected copper '+ident)
        bad.add(ident)
    new.append({'type':'pcb_trace','pcb_trace_id':identity,'connection_name':n,'source_trace_id':trace_ids[n],'route':[
        {'route_type':'wire','x':p['x'],'y':p['y'],'layer':face,'width':.15},
        *[{'route_type':'wire','x':px,'y':py,'layer':face,'width':.15} for px,py in points],
        {'route_type':'via','x':x,'y':y,'from_layer':face,'to_layer':'inner2','layers':s['layers'],'via_diameter':.4,'via_hole_diameter':.2},
        {'route_type':'wire','x':x,'y':y,'layer':'inner2','width':.15}]})
out.write_text(json.dumps([a for a in j if a['type']!='pcb_copper_pour' and a.get('pcb_trace_id',a.get('pcb_via_id')) not in bad]+new))
print('Local escapes:',[a['pcb_trace_id'] for a in new],'; retired clock escape:',sorted(retired),'; displaced ordinary tracks:',sorted(bad-retired))
