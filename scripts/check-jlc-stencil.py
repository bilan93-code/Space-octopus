"""Read the stencil flashes from both Gerbers and check them against physical lands."""
from collections import Counter, defaultdict
from hashlib import sha256
import json
import math
from pathlib import Path
import re

from shapely.affinity import rotate
from shapely.geometry import Point, box
from shapely.ops import unary_union

out = Path('output')
circuit_path = out/'space-octopus.circuit.json'
records = json.loads(circuit_path.read_bytes())
source = {p['source_component_id']:p['name'] for p in records if p['type']=='source_component'}
components = {p['pcb_component_id']:p for p in records if p['type']=='pcb_component' and p.get('source_component_id') in source}
errors = []

def flash_shape(x,y,w,h=None,angle=0,radius=0):
    if h is None:
        return Point(x,y).buffer(w/2,quad_segs=48)
    shape = box(x-w/2+radius,y-h/2+radius,x+w/2-radius,y+h/2-radius)
    if radius:
        shape = shape.buffer(radius,quad_segs=24)
    return rotate(shape,angle,origin=(x,y))

def shape_from_record(p):
    if p['shape']=='circle':
        return flash_shape(p['x'],p['y'],2*p['radius'])
    if p['shape'] not in ('rect','rotated_rect'):
        raise ValueError(p)
    return flash_shape(p['x'],p['y'],p['width'],p['height'],p.get('ccw_rotation',p.get('rect_ccw_rotation',0)),p.get('corner_radius',0))

def read_flashes(path):
    text = path.read_text()
    assert '%MOMM*%' in text and '%FSLAX46Y46*%' in text
    apertures = {name:(typ,[float(n) for n in size.split('X')]) for name,typ,size in re.findall(r'%ADD(\d+)([A-Z]+),([.\dX-]+)\*%',text)}
    active = None
    rotation = 0
    flashes = []
    for line in text.splitlines():
        if line=='%LPC*%' or re.search(r'D0[12]\*$',line):
            raise ValueError(f'Unexpected non-flash operation in {path}: {line}')
        if m:=re.fullmatch(r'D(\d+)\*',line):
            active=m[1]
        elif m:=re.fullmatch(r'%LR([\d.+-]+)\*%',line):
            rotation=float(m[1])
        elif m:=re.fullmatch(r'X(-?\d+)Y(-?\d+)D03\*',line):
            x,y=[int(v)/1e6 for v in m.groups()]
            shape,sizes=apertures[active]
            if shape not in ('R','C'):
                raise ValueError(f'Unsupported flashed aperture {shape}')
            flashes.append((x,y,flash_shape(x,y,*sizes,angle=rotation)))
    return flashes

lands=defaultdict(list)
for p in records:
    if p['type']=='pcb_smtpad':
        lands[p['pcb_component_id'],p['layer']].append(shape_from_record(p))
for key in lands:
    lands[key]=unary_union(lands[key])
rows = []
chip_counts = Counter()
for face,file in [('top','F_Paste'),('bottom','B_Paste')]:
    flashes=read_flashes(out/'review-fabrication'/(file+'.gbr'))
    candidates=defaultdict(list)
    for x,y,shape in flashes:
        candidates[round(x,4),round(y,4)].append(shape)
    for p in records:
        if p['type']!='pcb_solder_paste' or p['layer']!=face:
            continue
        component=components[p['pcb_component_id']]
        name=source[component['source_component_id']]
        expected=shape_from_record(p)
        key=round(p['x'],4),round(p['y'],4)
        options=candidates.get(key,[])
        match=next((i for i,g in enumerate(options) if expected.symmetric_difference(g).area<.00005),None)
        if match is None:
            errors.append(f'{name} {face} missing/mismatched aperture at {key}')
            continue
        actual=options.pop(match)
        if component['layer']!=face:
            errors.append(f'{name} paste on opposite board face at {key}')
        land=lands.get((p['pcb_component_id'],face))
        if land is None or actual.intersection(land).area/actual.area < .97:
            errors.append(f'{name} aperture extends outside its solder land on {face} at {key}')
        chip_counts[name,face]+=1
    extra=sum(map(len,candidates.values()))
    if extra:
        errors.append(f'{file} has {extra} extra apertures')
    rows.append({'face':face,'gerberFlashes':len(flashes)})
for name,expected in [('U2',49),('U13',13),('U21',11)]:
    if chip_counts[name,'bottom']!=expected or chip_counts[name,'top']:
        errors.append(f'{name} package aperture count or face is incorrect')
report={'passed':not errors,'circuitSha256':sha256(circuit_path.read_bytes()).hexdigest(),
        'faces':rows,'packageApertures':{n:chip_counts[n,'bottom'] for n in ['U2','U13','U21']},
        'errors':errors,'method':'Read metric RS-274X flashes, including LR rotation, and compare count, shape, dimensions, placement, side and overlap with native electrical lands.'}
(out/'stencil-file-audit.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
raise SystemExit(bool(errors))
