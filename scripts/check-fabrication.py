"""Check exported drills, contours, layers, fiducials and assembly rows."""
import csv,hashlib,json,math,re
from pathlib import Path
from assembly_parts import is_fitted

root=Path(__file__).resolve().parents[1];out=root/'output';folder=out/'review-fabrication'
j=json.loads((out/'space-octopus.circuit.json').read_text());errors=[]
def require(condition,message):
 if not condition:errors.append(message)
def drills(path):
 tools={};tool=None;points=[]
 for line in path.read_text().splitlines():
  match=re.fullmatch(r'T(\d+)C([\d.]+)',line)
  if match:tools[match[1]]=float(match[2]);continue
  match=re.fullmatch(r'T(\d+)',line)
  if match:tool=match[1];continue
  match=re.fullmatch(r'X(-?[\d.]+)Y(-?[\d.]+)',line)
  if match:points.append((float(match[1]),float(match[2]),tools[tool]))
 return points
def polygon_contains(point,vertices):
 inside=False
 for a,b in zip(vertices,vertices[1:]+vertices[:1]):
  if (a[1]>point[1])!=(b[1]>point[1]) and point[0]<(b[0]-a[0])*(point[1]-a[1])/(b[1]-a[1])+a[0]:inside=not inside
 return inside
def path_distance(point,vertices):
 if len(vertices)==1:return math.dist(point,vertices[0])
 distances=[]
 for a,b in zip(vertices,vertices[1:]+vertices[:1]):
  dx,dy=b[0]-a[0],b[1]-a[1];length=dx*dx+dy*dy
  t=max(0,min(1,((point[0]-a[0])*dx+(point[1]-a[1])*dy)/length)) if length else 0
  distances.append(math.hypot(point[0]-a[0]-t*dx,point[1]-a[1]-t*dy))
 return min(distances,default=math.inf)
def aperture_outline(aperture):
 # The locked exporter uses these standard apertures and rounded-pad macros.
 shape,p=aperture
 if shape=='C' and len(p)==1:return [(0,0)],p[0]/2
 if shape=='R' and len(p)==2:
  x,y=p[0]/2,p[1]/2;return [(-x,-y),(x,-y),(x,y),(-x,y)],0
 if shape=='O' and len(p)==2:
  d=abs(p[0]-p[1])/2
  return ([(-d,0),(d,0)] if p[0]>=p[1] else [(0,-d),(0,d)]),min(p)/2
 if shape=='ROUNDRECT' and len(p)==9:return list(zip(p[1::2],p[2::2])),p[0]
 if shape in ['HORZPILL','VERTPILL'] and len(p)==4:
  return ([(-p[3],0),(p[3],0)] if shape=='HORZPILL' else [(0,-p[3]),(0,p[3])]),p[2]/2
 if shape=='ROTATEDPILL' and len(p)==3:return [(-p[1],-p[2]),(p[1],p[2])],p[0]/2
 raise ValueError(f'Unsupported paste aperture {shape}: {p}')
def gerber_evidence(path,paste=False):
 text=path.read_text();fmt=re.search(r'%FSLAX(\d)(\d)Y(\d)(\d)\*%',text)
 if fmt is None or '%MOMM*%' not in text:raise ValueError('Expected absolute, leading-zero-suppressed millimeter Gerber coordinates')
 sx,sy=10**int(fmt[2]),10**int(fmt[4]);apertures={}
 for match in re.finditer(r'%ADD(\d+)([A-Za-z][A-Za-z0-9_]*)(?:,([^*]*))?\*%',text):
  values=[float(v) for v in match[3].split('X')] if match[3] else []
  if not all(math.isfinite(v) for v in values):raise ValueError('Nonfinite aperture size')
  apertures[match[1]]=(match[2],values)
 # Remove parameter/macro bodies, retaining polarity changes in command order.
 text=re.sub(r'%([^%]*)%',lambda m:m[1] if m[1] in ['LPD*','LPC*'] else '',text)
 flashes=[];openings=[];selected=None;previous=None;region=None;dark=True;linear=True
 for token in text.split('*'):
  token=token.strip()
  if not token or token.startswith('G04'):continue
  if token in ['LPD','LPC']:dark=token=='LPD';continue
  if token in ['G01','G02','G03']:linear=token=='G01';continue
  if token=='G36':
   if paste:region=[]
   continue
  if token=='G37':
   if paste and region is not None and dark:
    rings=[ring for ring in region if len(ring)>=3]
    if not rings:raise ValueError('Empty paste region')
    openings.append((rings,0))
   region=None;continue
  match=re.fullmatch(r'(?:G54)?D(\d+)',token)
  if match:selected=match[1];continue
  match=re.fullmatch(r'X(-?\d+)Y(-?\d+)(?:I(-?\d+)J(-?\d+))?D0([123])',token)
  if match:
   point=(int(match[1])/sx,int(match[2])/sy);operation=match[5]
   if operation=='3':
    if selected not in apertures:raise ValueError(f'Flash uses undefined aperture D{selected}')
    aperture=apertures[selected];flashes.append((point,aperture,dark))
    if paste and dark:
     vertices,radius=aperture_outline(aperture)
     if radius<0:raise ValueError('Negative paste aperture radius')
     openings.append(([[(x+point[0],y+point[1]) for x,y in vertices]],radius))
   elif paste and region is not None:
    if operation=='2':region.append([point])
    else:
     if not linear or match[3] is not None:raise ValueError('Curved paste region cannot be verified')
     if not region:raise ValueError('Paste region has no starting point')
     region[-1].append(point)
   elif paste and operation=='1' and dark:
    if not linear or match[3] is not None or previous is None:raise ValueError('Unsupported paste stroke')
    shape,values=apertures[selected]
    if shape!='C' or len(values)!=1:raise ValueError('Expected a circular aperture for a paste stroke')
    openings.append(([[previous,point]],values[0]/2))
   previous=point;continue
  if paste and re.search(r'[XYID]|G7[01]|G9[01]',token):raise ValueError(f'Unsupported paste command: {token}')
 if region is not None:raise ValueError('Unclosed paste region')
 return flashes,openings
def opening_overlaps(opening,point,radius):
 rings,margin=opening
 if sum(polygon_contains(point,ring) for ring in rings if len(ring)>=3)%2:return True
 return min((path_distance(point,ring) for ring in rings),default=math.inf)<=radius+margin+.000001
def check_fiducials():
 evidence={}
 for layer in ['F_Mask','F_Cu','F_Paste']:
  try:evidence[layer]=gerber_evidence(folder/(layer+'.gbr'),paste=layer=='F_Paste')
  except (OSError,ValueError,KeyError) as exc:
   require(False,f'{layer}: cannot verify fiducial export: {exc}');evidence[layer]=None
 sources={e['source_component_id']:e['name'] for e in j if e['type']=='source_component'}
 mask_count=0 if evidence['F_Mask'] is not None else None
 paste_count=0 if evidence['F_Paste'] is not None else None
 locations=0
 for ref in ['FID1','FID2','FID3']:
  components=[e for e in j if e['type']=='pcb_component' and sources.get(e.get('source_component_id'))==ref]
  require(len(components)==1,f'{ref}: expected one Circuit JSON component')
  if len(components)!=1:continue
  pads=[e for e in j if e['type']=='pcb_smtpad' and e.get('pcb_component_id')==components[0]['pcb_component_id']]
  valid=len(pads)==1 and pads[0].get('shape')=='circle' and pads[0].get('layer')=='top' and abs(pads[0].get('radius',0)-.5)<.000001
  require(valid,f'{ref}: expected one top-side 1 mm circular copper pad')
  if not valid:continue
  pad=pads[0];point=(pad['x'],pad['y']);locations+=1
  for layer,diameter in [('F_Mask',2),('F_Cu',1)]:
   if evidence[layer] is None:continue
   hits=[(aperture,dark) for position,aperture,dark in evidence[layer][0] if math.dist(position,point)<.000002]
   verified=len(hits)==1 and hits[0][1] and hits[0][0][0]=='C' and len(hits[0][0][1])==1 and abs(hits[0][0][1][0]-diameter)<.000001
   require(verified,f'{ref}: expected one dark {diameter} mm circular flash in {layer} at {point}')
   if layer=='F_Mask' and verified:mask_count+=1
  if evidence['F_Paste'] is not None:
   hits=sum(opening_overlaps(opening,point,pad['radius']) for opening in evidence['F_Paste'][1]);paste_count+=hits
   require(hits==0,f'{ref}: {hits} solder-paste openings overlap the fiducial copper at {point}')
 # An absent/invalid fiducial or unreadable Gerber is not evidence of zero paste.
 return mask_count,paste_count if locations==3 else None
npth=drills(folder/'drill_npth.drl');pth=drills(folder/'drill-L1-L4.drl')
for name,actual,expected in [
 ('nonplated',npth,[a for a in j if a['type']=='pcb_hole']),
 ('plated',pth,[a for a in j if a['type'] in ['pcb_via','pcb_plated_hole']]),
]:
 require(len(actual)==len(expected),f'{name}: drill count {len(actual)} != {len(expected)}')
 for a in expected:
  diameter=a.get('hole_diameter',a.get('hole_width'))
  require(any(math.hypot(x-a['x'],y-a['y'])<.0002 and abs(d-diameter)<.00001 for x,y,d in actual),f'{name}: missing drill at {a["x"]}, {a["y"]}')
require(not any(abs(d-28)<.01 for x,y,d in npth),'The aperture must be routed rather than a 28 mm drill')
require(sum(abs(d-4.5)<.001 for x,y,d in npth)==6,'Expected six 4.5 mm mounting holes')
edge=(folder/'Edge_Cuts.gbr').read_text();fmt=re.search(r'%FSLAX\d(\d)Y\d\d\*%',edge)
require(fmt is not None,'Outline coordinate format is missing')
scale=10**int(fmt[1]) if fmt else 1e6
points=[(int(x)/scale,int(y)/scale) for x,y in re.findall(r'X(-?\d+)Y(-?\d+)(?:I-?\d+J-?\d+)?D0[12]\*',edge)]
radii=[math.hypot(x,y) for x,y in points]
require(sum(abs(r-56)<.001 for r in radii)>=256,'Expected the full 112 mm outer contour')
require(sum(abs(r-14)<.001 for r in radii)>=2,'Expected a separate 28 mm aperture contour')
contours=[];current=[];previous=None;cutout_arcs=0
for line in edge.splitlines():
 match=re.fullmatch(r'X(-?\d+)Y(-?\d+)(?:I(-?\d+)J(-?\d+))?D0([12])\*',line)
 if not match:continue
 x,y=int(match[1])/scale,int(match[2])/scale
 if match[5]=='2':
  if current:contours.append(current)
  current=[]
 elif match[3] is not None and previous is not None:
  cx,cy=previous[0]+int(match[3])/scale,previous[1]+int(match[4])/scale
  if math.hypot(cx,cy)<.00001 and abs(math.hypot(x-cx,y-cy)-14)<.00001 and abs(math.hypot(previous[0]-cx,previous[1]-cy)-14)<.00001:
   require(math.hypot(x+previous[0]-2*cx,y+previous[1]-2*cy)<.00001,'Cutout arc must span a semicircle')
   cutout_arcs+=1
 current.append((x,y));previous=(x,y)
if current:contours.append(current)
require(len(contours)==2 and all(math.dist(c[0],c[-1])<.00001 for c in contours),'Expected two closed profile contours')
require(cutout_arcs==2,'Expected two exact 14 mm radius semicircles for the routed opening')
for face in ['F_Cu','In1_Cu','In2_Cu','B_Cu']:require((folder/(face+'.gbr')).stat().st_size>100,f'Missing copper layer {face}')
fiducial_mask_openings,fiducial_paste_openings=check_fiducials()
parts=sum([json.loads((root/'data'/f'{n}.json').read_text()) for n in ['input-supplies-mcu-driver-inverter','sensing-fault-interfaces-brake','mechanical']],[])
expected_refs = {p['ref'] for p in parts if is_fitted(p)}
with (out/'pick-and-place-review.csv').open(newline='') as placement_file:
 rows = list(csv.DictReader(placement_file))
actual_refs = [row['Designator'] for row in rows]
require(len(rows) == len(expected_refs) and set(actual_refs) == expected_refs,
        f'Pick-and-place mismatch: missing {sorted(expected_refs - set(actual_refs))}, extra {sorted(set(actual_refs) - expected_refs)}, rows {len(rows)}')
require(not {'J1','J2','J11'}.intersection(actual_refs),'Direct-solder wire terminations must be excluded from placement data')
manifest=json.loads((out/'fabrication-export-status.json').read_text())
for entry in manifest['files']:require(hashlib.sha256((folder/entry['file']).read_bytes()).hexdigest()==entry['sha256'],'Changed fabrication file '+entry['file'])
report={'status':'failed' if errors else 'passed','platedDrills':len(pth),'nonplatedDrills':len(npth),'mountingDrills':6,'outerDiameterMm':112,'routedOpeningDiameterMm':28,'closedProfileContours':len(contours),'cutoutSemicircles':cutout_arcs,'copperLayers':4,'assemblyRows':len(rows),'fiducialMaskOpenings':fiducial_mask_openings,'fiducialPasteOpenings':fiducial_paste_openings,'errors':errors,'fabricationReady':False}
(out/'fabrication-file-audit.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2));raise SystemExit(bool(errors))
