"""Package the editable project and generated review files with checksums."""
import hashlib,json,zipfile,sys
from pathlib import Path

root=Path(__file__).resolve().parent.parent
tscircuit_only='--tscircuit-only' in sys.argv
target=root.parent/('Space-octopus-tscircuit-Complete.zip' if tscircuit_only else 'Space-octopus-tscircuit-Review.zip')
audit=json.loads((root/('output/tscircuit-completion-audit.json' if tscircuit_only else 'output/delivery-audit.json')).read_text())
assert audit['status']=='passed','Run the delivery audit before packaging.'
assert audit['circuitJsonSha256']==hashlib.sha256((root/'output/space-octopus.circuit.json').read_bytes()).hexdigest(),'Delivery audit is stale.'
folders=['src','data','footprints','assets','licenses','docs','scripts','output','.github']+([] if tscircuit_only else ['kicad'])
files=[root/n for n in ['README.md','.gitignore','package.json','package-lock.json','tsconfig.json','index.tsx','requirements-copper.txt','requirements-mechanical.txt']]
for folder in folders:
 files.extend(p for p in (root/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc')
files=sorted(set(files))
files=[p for p in files if p!=root/'output/deliverable-manifest.json']
if tscircuit_only:
 excluded=['output/kicad/','output/motor-mount-preview/']
 excluded_files={'output/Space_Octopus_RevA_Assembly.step','output/delivery-audit.json','output/tscircuit-manifest.json'}
 files=[p for p in files if str(p.relative_to(root)) not in excluded_files and not any(str(p.relative_to(root)).startswith(prefix) for prefix in excluded)]
status=json.loads((root/'output/engineering-status.json').read_text())
delivery={'stage':status['stage'],'fabricationReady':False,'fullyConnectedNets':status['fullyConnectedNets'],'nets':status['nets'],'files':[{'path':str(p.relative_to(root)),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in files]}
delivery_path=root/('output/tscircuit-manifest.json' if tscircuit_only else 'output/deliverable-manifest.json');delivery_path.write_text(json.dumps(delivery,indent=2)+'\n');files.append(delivery_path)
manifest={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
 for p in files:archive.write(p,'Space-octopus/'+str(p.relative_to(root)))
 archive.writestr('Space-octopus/MANIFEST.sha256',''.join(f'{digest}  {name}\n' for name,digest in manifest.items()))
with zipfile.ZipFile(target) as archive:
 for name,digest in manifest.items():
  assert hashlib.sha256(archive.read('Space-octopus/'+name)).hexdigest()==digest,name
 assert archive.testzip() is None
print(json.dumps({'archive':str(target),'files':len(files),'bytes':target.stat().st_size,'checksumsVerified':True}))
