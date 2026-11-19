"""Evaluate actual Gerber polarity to catch erased nested copper islands."""
import json,re,sys,tempfile,subprocess,hashlib
from pathlib import Path
from shapely.geometry import Point,Polygon

with tempfile.TemporaryDirectory(prefix='octopus-gerber-regions-') as work:
 code="""
import fs from 'node:fs';
import {convertCircuitJsonToGerberFiles} from 'circuit-json-to-gerber';
import {orderGerberPours} from './scripts/gerber-input.mjs';
const ring=(a,b)=>({vertices:[{x:a,y:a},{x:b,y:a},{x:b,y:b},{x:a,y:b}].map(v=>({...v,bulge:0}))});
const board={type:'pcb_board',pcb_board_id:'b',center:{x:0,y:0},width:12,height:12,thickness:1.6,num_layers:4,outline:ring(-6,6).vertices};
const outer={type:'pcb_copper_pour',pcb_copper_pour_id:'o',layer:'top',source_net_id:'GND',shape:'brep',covered_with_solder_mask:true,brep_shape:{outer_ring:ring(-5,5),inner_rings:[ring(-4.99,4.99)]}};
const inner={...outer,pcb_copper_pour_id:'i',brep_shape:{outer_ring:ring(-2,2),inner_rings:[]}};
const j=[board,{type:'source_net',source_net_id:'GND',name:'GND'},inner,outer];
for(const [name,input]of[['original',j],['ordered',orderGerberPours(j)]])fs.writeFileSync(process.argv[2]+'/'+name+'.gbr',convertCircuitJsonToGerberFiles(input)['F_Cu.gbr']);
"""
 subprocess.run(['node','--input-type=module','-',work],input=code,text=True,check=True)
 def copper_at(path,point):
  text=re.sub(r'%([^%]*)%',lambda m:m[1] if m[1] in ['LPD*','LPC*'] else '',path.read_text(),flags=re.S);dark=True;ring=None;state=False
  for token in text.split('*'):
   token=token.strip()
   if token in ['LPD','LPC']:dark=token=='LPD'
   elif token=='G36':ring=[]
   elif token=='G37':
    if Polygon(ring).covers(Point(*point)):state=dark
    ring=None
   elif ring is not None:
    m=re.fullmatch(r'X(-?\d+)Y(-?\d+)D0[12]',token)
    if m:ring.append((int(m[1])/1e6,int(m[2])/1e6))
  return state
 results={name:{'nestedIsland':copper_at(Path(work)/(name+'.gbr'),(0,0)),'clearanceHole':copper_at(Path(work)/(name+'.gbr'),(3,0)),'outerRing':copper_at(Path(work)/(name+'.gbr'),(4.995,0))} for name in ['original','ordered']}
 assert results['ordered']=={'nestedIsland':True,'clearanceHole':False,'outerRing':True},'Nested copper was erased or a clearance hole was filled.'
 assert not results['original']['nestedIsland'],'Review the adapter after an upstream Gerber behavior change.'
 report={'status':'passed','adapterSha256':hashlib.sha256(Path('scripts/gerber-input.mjs').read_bytes()).hexdigest(),'method':'Export nested polygons with a thin containing ring. Evaluate dark/clear Gerber regions at three physical points. Outer-ring ordering must preserve the island and the clearance hole.','results':results}
 Path('output/gerber-ordering-audit.json').write_text(json.dumps(report,indent=2)+'\n');print('Gerber nested-region polarity check passed.')
