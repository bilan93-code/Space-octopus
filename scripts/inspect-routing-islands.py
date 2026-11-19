"""Fast terminal-island diagnostic; use check-copper.py for full clearance audit."""
import json,sys
from pathlib import Path

path=sys.argv[1];selected=set(sys.argv[2:]);s={}
code=Path('scripts/check-copper.py').read_text()
sys.argv=['check-copper.py',path,'/tmp/island-diagnostic-unused.json']
exec(compile(code.split('# Distinct-net copper')[0],'copper_geometry','exec'),s)
if selected:s['nets']={k:v for k,v in s['nets'].items() if v in selected}
connect='connectivity=[];netGraphs={}'+code.split('connectivity=[];netGraphs={}')[1].split('unconnected=[n for n in connectivity')[0]
exec(compile(connect,'copper_connectivity','exec'),s)
result=[n for n in s['connectivity'] if not n['connected']]
print(json.dumps({'source':path,'connected':len(s['connectivity'])-len(result),'nets':len(s['connectivity']),'unconnected':result},indent=2))
