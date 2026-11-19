"""Complete the local tscircuit review stage; never invoke KiCad.

Usage: python scripts/finish-tscircuit-stage.py <complete routed Circuit JSON>
"""
import json,shutil,subprocess,sys,time,hashlib
from pathlib import Path
from urllib.request import urlopen

root=Path(__file__).resolve().parent.parent
checked='--resume-checked' in sys.argv
resume='--resume-exports' in sys.argv or checked
raw=Path(sys.argv[1]).resolve() if not resume else root/'output/space-octopus.circuit.json';work=root/'routing-work/motor-mount-revision/finalization'
work.mkdir(parents=True,exist_ok=True)
def run(*args):
 print('Running:',*args,flush=True)
 subprocess.run(list(args),cwd=root,check=True)
if checked:
 validation=json.loads((root/'output/validation-results.json').read_text())
 digest=hashlib.sha256(raw.read_bytes()).hexdigest()
 assert validation['allPassed'] and len(validation['checks'])==17 and validation['circuitJsonSha256']==digest,'Validation checkpoint is stale.'
 assert json.loads((root/'output/3d-status.json').read_text())['sourceCircuitSha256']==digest,'3D checkpoint is stale.'
 assert not any('error' in e['type'] for e in json.loads(raw.read_text())),'Native diagnostics are unresolved.'
 print('Resuming reports from the unchanged circuit and all 17 passing checks.',flush=True)
else:
 run('npm','run','typecheck')
 if not resume:
  run(sys.executable,'scripts/prune-routing-stubs.py',str(raw),'--require-complete')
  candidate=root/'routing-work/motor-mount-revision/pruned/candidate.circuit.json'
  for name in ['data/routed-traces.json','output/space-octopus.circuit.json']:
   p=root/name;shutil.copyfile(p,work/(p.name+'.before'))
  capture=root/'routing-work/motor-mount-revision/final-source-capture.circuit.json'
  assert capture.exists(),'Missing latest native tscircuit source capture.'
  shutil.copyfile(capture,root/'output/space-octopus.circuit.json')
  run('node_modules/.bin/tsx','scripts/save-routing.ts',str(candidate),'tscircuit custom routing — outward-facing circular motor revision')
  run('node_modules/.bin/tsx','scripts/build.tsx','--json-only')
 else:
  current=json.loads(raw.read_text())
  print('Resuming exports; the next full native build and strict checks must pass.',flush=True)
 run(sys.executable,'scripts/refresh-silkscreen.py')
 run('npm','run','build')
 run('npm','run','export:3d')
 run('node','scripts/run-checks.mjs')
shutil.copyfile(root/'routing-work/motor-mount-revision/pruned/status.json',root/'output/routing-cleanup-audit.json')
# This incidental file came from the old checker that reran full DRC inside
# every Kelvin test. The Kelvin and independent copper reports now stand alone.
(root/'output/kelvin-audit.copper.json').unlink(missing_ok=True)
run('node','scripts/create-status.mjs','--tscircuit-only')
run('node','scripts/create-review.mjs')
run('node','scripts/export-review.mjs')
run(sys.executable,'scripts/check-fabrication.py')
run('node','scripts/export-documents.cjs')
run(sys.executable,'scripts/measure-signal-paths.py')
try:
 with urlopen('http://127.0.0.1:3021/',timeout=3) as response:assert response.status==200
except Exception:
 serverlog=(work/'preview-server.log').open('ab')
 subprocess.Popen([sys.executable,'-m','http.server','3021','--bind','0.0.0.0','--directory',str(root/'output')],cwd=root,stdout=serverlog,stderr=serverlog,start_new_session=True)
 for _ in range(30):
  try:
   with urlopen('http://127.0.0.1:3021/',timeout=1) as response:
    if response.status==200:break
  except Exception:time.sleep(.2)
 else:raise RuntimeError('Review server did not start.')
run('node','scripts/check-preview.cjs')
run('node','scripts/check-delivery.mjs','--tscircuit-only')
run('node','scripts/create-tscircuit-completion.mjs')
run(sys.executable,'scripts/package-review.py','--tscircuit-only')
print('Tscircuit review stage complete. Further KiCad work requires user approval.',flush=True)
