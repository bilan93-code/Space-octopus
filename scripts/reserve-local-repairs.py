"""Reserve one checked escape per disconnected terminal island before routing.

Earlier ordinary tracks may be displaced locally; fixed power, thermal and
Kelvin copper remain protected by the finishing router's escape predicate.
"""
import os,json,sys,collections
from pathlib import Path

src=Path(sys.argv[1]);out=Path(sys.argv[2]);selected=set(sys.argv[3:]);s={}
os.environ['ROUTING_LOCAL_REPAIR']='1';os.environ['ROUTING_FREEZE_EQUAL_RANK']='1';os.environ['ROUTING_GROUND_ESCAPES']='1';os.environ['ROUTING_WORK']=str(out.parent/'batch-local-work')
sys.argv=['finish-routing.py',str(src)]
exec(compile(Path('scripts/finish-routing.py').read_text().split('\nfinished=max(')[0],'routing_geometry','exec'),s)
reports=[];sequence=0
for net,name in sorted(s['nets'].items(),key=lambda kv:(s['route_rank'](kv[0]),kv[1])):
 if selected and name not in selected:continue
 groups,terminals=s['polygons'](net)
 if len(groups)<=1:continue
 target=max(groups,key=lambda r:(len(terminals[r]),len(groups[r]),sum(g.area for g in groups[r].values())))
 roots=list(groups)
 for root in roots:
  if root==target:continue
  result,reason=s['terminal_escape'](net,{target:groups[target],root:groups[root]},terminals)
  if result is None:reports.append({'net':name,'terminals':[s['scope']['portlabel'](p['pcb_port_id']) for p in terminals[root]],'added':False,'reason':reason});print(json.dumps(reports[-1]),flush=True);continue
  route,newitems,newbarrels,ripped=result
  removed=[a for a in s['items'] if a['id'].rsplit(':',1)[0] in ripped]
  removed_vias={(a['net'],a['g'].wkb) for a in removed if a['kind']=='via'}
  s['items'][:]=[a for a in s['items'] if a['id'].rsplit(':',1)[0] not in ripped]
  s['barrels'][:]=[(n,ls,g) for n,ls,g in s['barrels'] if(n,g.wkb) not in removed_vias]
  s['j'][:]=[a for a in s['j'] if a['type'] not in ['pcb_trace','pcb_via'] or a.get('pcb_trace_id',a.get('pcb_via_id')) not in ripped]
  identity='seed_batch_repair_'+name+'_'+str(sequence);sequence+=1
  for k,(g,ls,kind) in enumerate(newitems):s['add'](g,net,ls,f'{identity}:{k}',kind)
  s['barrels'].extend(newbarrels);s['j'].append({'type':'pcb_trace','pcb_trace_id':identity,'connection_name':net,'route':route})
  reports.append({'net':name,'terminals':[s['scope']['portlabel'](p['pcb_port_id']) for p in terminals[root]],'added':True,'via':[route[-1]['x'],route[-1]['y']],'displaced':sorted(ripped),'displacedNets':sorted({s['nets'].get(a['net'],a['net']) for a in removed})});print(json.dumps(reports[-1]),flush=True)
result=[a for a in s['j'] if a['type']!='pcb_copper_pour'];ids=[a['pcb_trace_id'] for a in result if a['type']=='pcb_trace'];assert len(ids)==len(set(ids))
out.write_text(json.dumps(result));out.with_suffix('.repairs.json').write_text(json.dumps({'source':str(src),'added':sequence,'repairs':reports},indent=2)+'\n');print('Reserved',sequence,'local repair escapes.',flush=True)
