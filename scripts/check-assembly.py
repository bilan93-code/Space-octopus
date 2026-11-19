"""Verify placed assembly envelopes on each face, including lead protrusions."""
import json,math
from pathlib import Path
from shapely.geometry import shape,Point
p=json.loads(Path('data/placement.json').read_text());g=json.loads(Path('data/board-geometry.json').read_text());errors=[]
outer=Point(0,0).buffer(g['outerDiameterMm']/2-g['edgeMarginMm'],quad_segs=256).buffer(1e-6)
inner=Point(0,0).buffer(g['centralOpeningDiameterMm']/2+g['edgeMarginMm'],quad_segs=128)
s={ref:{l:shape(v) for l,v in a['assemblyEnvelopes'].items()} for ref,a in p.items()}
for ref,a in s.items():
 if ref.startswith('H'):continue
 for l,v in a.items():
  if not outer.covers(v) or inner.intersection(v).area>1e-8:errors.append(f'{ref} {l}: board/opening margin')
refs=list(s)
for i,r in enumerate(refs):
 for t in refs[i+1:]:
  for l in s[r].keys()&s[t].keys():
   d=s[r][l].distance(s[t][l])
   if d<g['courtyardGapMm']-1e-5:errors.append(f'{r}/{t} {l}: assembly gap {d}')
report={'status':'failed' if errors else 'passed','parts':len(p),'errors':errors,'model':'Mounting-face body envelopes plus opposite-face trimmed-lead/solder envelopes. Axial motor clearance unverified.'}
Path('output/assembly-audit.json').write_text(json.dumps(report,indent=2)+'\n');print(report);raise SystemExit(bool(errors))
