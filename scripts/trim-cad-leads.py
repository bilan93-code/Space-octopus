"""Create the assembly-specific D2 model; the actual leads must be trimmed too."""
import json,hashlib
from pathlib import Path
import cadquery as cq
source=Path('assets/3d/Package_TO_SOT_THT.3dshapes__TO-220-2_Vertical.step')
out=Path('assets/3d/generated__TO-220-2_Vertical_LeadTrim2mm.step')
original=cq.importers.importStep(str(source))
limit=cq.Workplane('XY').box(80,80,100,centered=(True,True,False)).translate((0,0,-3.6))
trimmed=original.intersect(limit)
assembly=cq.Assembly(name='TO220_2_LeadTrim2mm')
assembly.add(trimmed,name='Trimmed_stock_package',color=cq.Color(.27,.30,.31))
assembly.save(str(out),exportType='STEP')
bounds=trimmed.val().BoundingBox()
report={'source':str(source),'sourceSha256':hashlib.sha256(source.read_bytes()).hexdigest(),'derivative':str(out),'derivativeSha256':hashlib.sha256(out.read_bytes()).hexdigest(),'operation':'Intersect the stock package with local Z >= -3.6 mm: 1.6 mm PCB plus 2 mm lead projection. Package body and land pattern unchanged.','cadqueryVersion':cq.__version__,'minimumLocalZMm':bounds.zmin,'maximumLocalZMm':bounds.zmax,'assemblyRequirement':'Physically trim D2 leads to <=2 mm below the motor-facing PCB surface; representative display color.'}
Path('assets/3d/lead-trim-provenance.json').write_text(json.dumps(report,indent=2)+'\n')
print('D2 stock lead model trimmed to the explicit 2 mm assembly limit.')
