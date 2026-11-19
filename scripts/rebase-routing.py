"""Keep compatible finished logic when functional cells move in tscircuit."""
import json,sys,subprocess
from pathlib import Path
baseline=Path(sys.argv[1] if len(sys.argv)>1 else 'routing-work/revision/before-functional-layout.circuit.json');fresh=Path(sys.argv[2] if len(sys.argv)>2 else 'routing-work/revision/complete-seed.circuit.json');out=Path('routing-work/revision/rebased.circuit.json')
a=json.loads(baseline.read_text());b=json.loads(fresh.read_text());logic=[x for x in a if x['type']=='pcb_trace' and x['pcb_trace_id'].startswith('finish_')];j=b+logic;out.write_text(json.dumps(j))
subprocess.run([sys.executable,'scripts/check-copper.py',str(out),'routing-work/revision/rebase-audit.json'],stdout=subprocess.DEVNULL,check=False)
audit=json.loads(Path('routing-work/revision/rebase-audit.json').read_text());bad=set()
for x in audit['clearances']:
 for k in ['a','b']:
  if x[k].startswith('finish_'):bad.add(x[k].rsplit(':',1)[0])
for x in audit['edges']+audit['holes']:
 if x['id'].startswith('finish_'):bad.add(x['id'].rsplit(':',1)[0])
j=[x for x in j if x.get('pcb_trace_id') not in bad];out.write_text(json.dumps(j));print('Preserved',len(logic)-len(bad),'logic routes;',len(bad),'routes need rerouting around revised functional cells.')
