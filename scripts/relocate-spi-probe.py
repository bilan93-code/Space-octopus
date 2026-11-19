"""Move the SPI probe to an accessible, checked outward-facing location."""
import json,sys
from pathlib import Path
from shapely.geometry import Point,LineString,box,shape

src=Path(sys.argv[1]);out=Path(sys.argv[2]);s={};sys.argv=['x',str(src)]
exec(compile(Path('scripts/check-copper.py').read_text().split('# Distinct-net copper')[0],'g','exec'),s)
placement_path=Path('data/placement.json');placement=json.loads(placement_path.read_text());x,y=20.25,5.5;ref='TP8';body=box(x-1.5,y-1.5,x+1.5,y+1.5)
assert not any(r!=ref and 'top' in p['assemblyEnvelopes'] and body.distance(shape(p['assemblyEnvelopes']['top']))<.4-1e-5 for r,p in placement.items()),'Probe courtyard does not fit.'
pid=next(pid for pid in s['ports'] if s['portlabel'](pid)=='TP8.1');port=s['ports'][pid];net=s['portnet'][pid];component=port['pcb_component_id'];oldpad=next(a for a in s['items'] if a.get('port')==pid);radius=(oldpad['g'].bounds[2]-oldpad['g'].bounds[0])/2
probe=Point(x,y).buffer(radius,quad_segs=32);wire=LineString([(20.25,4.175),(x,y)]).buffer(.075,quad_segs=32)
assert any(a['net']==net and a['kind']=='via' and a['g'].centroid.distance(Point(20.25,4.175))<1e-5 for a in s['items']),'Required existing signal via is absent.'
protected={a['pcb_trace_id'] for a in s['bytype']['pcb_trace'] if a['pcb_trace_id'].startswith(('seed_','kelvin_','plane_stitch_')) or any(v.get('width',0)>=.6 for v in a['route'])}
bad=set()
for a in s['items']:
 if a['layer']!='top' or a['net']==net or a['kind']=='pour':continue
 if min(probe.distance(a['g']),wire.distance(a['g']))>=.2-1e-5:continue
 identity=a['id'].rsplit(':',1)[0]
 assert a['kind']!='pad' and identity not in protected and not(a['kind']=='via' and a['g'].bounds[2]-a['g'].bounds[0]>=.59),'Probe obstructs fixed copper '+identity
 assert identity.startswith('finish_'),'Unexpected obstructed copper '+identity
 bad.add(identity)
j=[a for a in s['j'] if a['type']!='pcb_copper_pour' and a.get('pcb_trace_id',a.get('pcb_via_id')) not in bad]
for a in j:
 if a['type']=='pcb_port' and a['pcb_port_id']==pid:a.update(x=x,y=y,layers=['top'])
 elif a['type']=='pcb_smtpad' and a.get('pcb_port_id')==pid:a.update(x=x,y=y,layer='top')
 elif a['type']=='pcb_component' and a['pcb_component_id']==component:a.update(center={'x':x,'y':y},layer='top',ccw_rotation=0)
j.append({'type':'pcb_trace','pcb_trace_id':'seed_probe_TP8_top','connection_name':net,'route':[{'route_type':'wire','x':px,'y':py,'layer':'top','width':.15} for px,py in [(20.25,4.175),(x,y)]]})
old=placement[ref];new={**old,'x':x,'y':y,'bodyCenter':[x,y],'rotation':0,'layer':'top','occupiesLayers':['top'],'courtyard':list(body.bounds),'assemblyEnvelopes':{'top':body.__geo_interface__}}
report={'ref':ref,'old':old,'new':new,'displaced':sorted(bad),'reason':'Accessible outward-facing SPI test point connected to the existing MCU signal via. Only ordinary interfering signal tracks require rerouting.'}
out.with_suffix('.placement-change.json').write_text(json.dumps(report,indent=2)+'\n');placement[ref]=new
out.write_text(json.dumps(j));placement_path.write_text(json.dumps(placement,indent=2)+'\n')
revision_path=Path('data/motor-mount-revision.json');revision=json.loads(revision_path.read_text());revision.setdefault('routingRefinements',[]).append(report);revision_path.write_text(json.dumps(revision,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k not in ['old','new']},indent=2))
