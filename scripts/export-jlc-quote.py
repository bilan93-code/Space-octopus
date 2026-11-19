"""Package a verified tscircuit JLCPCB DFM quote and assembly matching files."""
from collections import Counter, defaultdict
import csv
import hashlib
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

out=Path('output')
def read(path):
    return json.loads(path.read_bytes())
def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
def csv_rows(path):
    with path.open(newline='') as stream:
        return list(csv.DictReader(stream))
def write_csv(name, fields, rows):
    with (dest/name).open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

circuit=out/'space-octopus.circuit.json'
signature=digest(circuit)
suite=read(out/'validation-results.json')
assert suite['circuitJsonSha256']==signature and suite['allPassed']
assert not read(out/'render-diagnostics.json')
for name,field in [('copper-audit.json','circuitJsonSha256'),('fabrication-export-status.json','circuitJsonSha256'),('power-backbone-audit.json','circuitJsonSha256'),('kelvin-audit.json','circuitJsonSha256'),('prototype/power/load-study.json','circuitSha256'),('stencil-file-audit.json','circuitSha256')]:
    assert read(out/name)[field]==signature,(name,'stale')
assert read(out/'fabrication-file-audit.json')['status']=='passed'
assert read(out/'stencil-file-audit.json')['passed']
assert read(out/'copper-audit.json')['status']=='passed'
assert read(out/'power-backbone-audit.json')['status']=='passed'
assert read(out/'kelvin-audit.json')['status']=='passed'
folder=out/'review-fabrication'
for name,edge in [('gerber-connectivity.json',0),('gerber-etch-screen.json',.025)]:
    check=read(out/name)
    assert check['sourceSha256']==signature and check['edgeLossMm']==edge and check['passed'],name
    assert all(digest(folder/(n+'.gbr'))==v for n,v in check['copperFilesSha256'].items())
fitted={}
for file in ['input-supplies-mcu-driver-inverter','sensing-fault-interfaces-brake','mechanical']:
    for row in read(Path('data')/(file+'.json')):
        if not row['dnp'] and row['kind'] not in {'hole','fiducial','testpoint'} and row['ref']!='JP701':
            fitted[row['ref']]=row
legacy_fuses = all(fitted[ref].get('holder') for ref in ('F1','F2'))
stock_file = 'five-board-stock.csv' if legacy_fuses else 'five-board-stock-soldered.csv'
dest = out / ('jlcpcb-bota' if legacy_fuses else 'jlcpcb-bota-soldered')
stock=csv_rows(out/'prototype'/stock_file)
records=read(circuit)
rendered_parts={row['name']:row for row in records if row['type']=='source_component'}
for ref in ('F1','F2'):
    assert rendered_parts[ref].get('manufacturer_part_number') == fitted[ref]['mpn'], (ref, 'stale rendered fuse')
    assert rendered_parts[ref].get('display_name') == fitted[ref]['value'], (ref, 'stale rendered fuse value')
groups=defaultdict(list)
extras=[]
for ref,part in fitted.items():
    holder=part.get('holder')
    mpn=holder['mpn'] if holder else part['mpn']
    match=[r for r in stock if r['Selected MPN']==mpn and r['Installation']==('through-hole fuse holder' if holder else 'board component')]
    assert len(match)==1,(ref,mpn,stock_file)
    row=match[0]
    assert (ref+' holder' if holder else ref) in (row['References'] if holder else row['References'].split())
    if not holder and part.get('lcsc'):
        assert row['LCSC'] == part['lcsc'], (ref, 'stale catalogue code')
    manufacturer=row['Manufacturer'] or (holder['manufacturer'] if holder else {'U13':'Texas Instruments','L101':'Coilcraft'}.get(ref,''))
    groups[part['footprint'],mpn,row['LCSC'],manufacturer].append(ref)
    if holder:
        cart=next(r for r in stock if r['Selected MPN']==part['mpn'] and r['Installation']=='hand-insert cartridge')
        extras.append({'Holder':ref,'Cartridge MPN':part['mpn'],'LCSC Part #':cart['LCSC'],'Quantity per board':1,'Minimum for five boards':5})
bom=[]
for (fp,mpn,lcsc,mfr),refs in groups.items():
    comments={mpn if fitted[ref].get('holder') else fitted[ref]['value'] for ref in refs}
    detail=next(iter(comments)) if len(comments)==1 else mpn
    bom.append({'Designator':','.join(refs),'Footprint':fp.split('/')[-1],'Quantity':len(refs),'Comment':detail,'Manufacturer':mfr,'Manufacturer Part Number':mpn,'LCSC Part #':lcsc})
source={r['source_component_id']:r['name'] for r in records if r['type']=='source_component'}
placements={source[r['source_component_id']]:r for r in records if r['type']=='pcb_component' and r.get('source_component_id') in source}
cpl=csv_rows(out/'pick-and-place-review.csv')
assert Counter(r['Designator'] for r in cpl)==Counter(fitted.keys())
for row in cpl:
    part=placements[row['Designator']]
    assert max(abs(float(row[f'Mid {axis.upper()}'])-part['center'][axis]) for axis in ('x','y'))<=.000501
    assert part['layer']==row['Layer'] and part['layer'] in ('top','bottom')
    assert abs((float(row['Rotation'])-part['rotation']+180)%360-180)<.001
    row['Layer']=part['layer'].title()
    row['Rotation']=f"{float(row['Rotation'])%360:g}"
dest.mkdir(exist_ok=True)
write_csv('JLCPCB-BOM-quote.csv',list(bom[0]),bom)
write_csv('JLCPCB-CPL-quote.csv',list(cpl[0]),cpl)
if extras:
    write_csv('Hand-insert-fuse-cartridges.csv',list(extras[0]),extras)
fab=['F_Cu','In1_Cu','In2_Cu','B_Cu','F_Mask','B_Mask','F_Paste','B_Paste','F_SilkScreen','B_SilkScreen','Edge_Cuts']
files=[f+'.gbr' for f in fab]+['drill-L1-L4.drl','drill_npth.drl']
archive=dest/'Space-Octopus-Bota-JLCPCB-Gerbers-DFM-quote.zip'
source_hashes={e['file']:e['sha256'] for e in read(out/'fabrication-export-status.json')['files']}
with ZipFile(archive,'w',compression=ZIP_DEFLATED,compresslevel=6) as bundle:
    for name in files:
        assert digest(folder/name)==source_hashes[name]
        bundle.write(folder/name,name)
with ZipFile(archive) as bundle:
    assert bundle.testzip() is None and bundle.namelist()==files
    assert all(hashlib.sha256(bundle.read(name)).hexdigest()==source_hashes[name] for name in files)
brefs=[ref for row in csv_rows(dest/'JLCPCB-BOM-quote.csv') for ref in row['Designator'].split(',')]
assert Counter(brefs)==Counter(fitted.keys())==Counter(r['Designator'] for r in csv_rows(dest/'JLCPCB-CPL-quote.csv'))
assert sum(r['Quantity'] for r in bom)==len(cpl)
package_files=[archive,dest/'JLCPCB-BOM-quote.csv',dest/'JLCPCB-CPL-quote.csv']
if extras:
    package_files.append(dest/'Hand-insert-fuse-cartridges.csv')
result={
    'purpose': 'DFM and price quote only',
    'approvedForManufacture': False,
    'sourceSha256': signature,
    'gerberMembers': files,
    'bomLines': len(bom),
    'cplPlacements': len(cpl),
    'sides': dict(Counter(r['Layer'] for r in cpl)),
    'additionalCartridgesPerBoard': len(extras),
    'missingExactCatalogueListings': [r['Selected MPN'] for r in stock if r['Result'] in ('MPN/code mismatch', 'no unique exact listing')],
    'stockSnapshotUTC': stock[0]['Catalogue timestamp UTC'],
    'checks': len(suite['checks']),
    'sha256': {p.name:digest(p) for p in package_files},
}
(dest/'package-verification.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
