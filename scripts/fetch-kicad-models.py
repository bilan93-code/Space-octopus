"""Vendor the STEP models already referenced by the source KiCad footprints."""
import json,re,subprocess,hashlib,concurrent.futures
from pathlib import Path
root=Path(__file__).resolve().parents[1];out=root/'kicad/libraries/SpaceOctopus.3dshapes';out.mkdir(parents=True,exist_ok=True)
parts=sum([json.loads((root/'data'/f'{n}.json').read_text()) for n in ['input-supplies-mcu-driver-inverter','sensing-fault-interfaces-brake','mechanical']],[])
jobs={}
for c in parts:
 lib,name=c['footprint'].split('/');path=root/'footprints/kicad'/f'{lib}__{name}.kicad_mod'
 s=path.read_text()
 for m in re.finditer(r'\(model\s+"\$\{KICAD\d+_3DMODEL_DIR\}/([^"\n]+)"',s):
  relative=m.group(1);jobs[relative]=out/relative.replace('/','__')
def fetch(item):
 rel,p=item;url='https://gitlab.com/kicad/libraries/kicad-packages3D/-/raw/master/'+rel
 result={'path':str(p.relative_to(root/'kicad')),'source':url}
 if not p.exists():
  r=subprocess.run(['curl','-fLsS','--max-time','40','--retry','1',url,'-o',str(p)],capture_output=True,text=True)
  if r.returncode:
   p.unlink(missing_ok=True);return {**result,'status':'missing','reason':r.stderr.strip()[-200:]}
 raw=p.read_bytes();return {**result,'status':'downloaded','bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(fetch,jobs.items()))
(root/'kicad/reports/model-provenance.json').write_text(json.dumps(results,indent=2)+'\n')
print('Official footprint-referenced models:',sum(r['status']=='downloaded' for r in results),'available;',sum(r['status']=='missing' for r in results),'missing')
for r in results:
 if r['status']=='missing':print(r['path'],r['reason'])
