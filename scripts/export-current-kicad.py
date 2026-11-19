"""Export the current tscircuit PCB into a separate, editable KiCad project."""
import json,math,os,shutil,sys,hashlib,uuid
from pathlib import Path
for key,leaf in [('XDG_CONFIG_HOME','config'),('XDG_CACHE_HOME','cache'),('XDG_DATA_HOME','data')]:os.environ.setdefault(key,'/tmp/space-octopus-kicad/'+leaf)
import pcbnew as p
root=Path(__file__).resolve().parents[1];src=Path(sys.argv[1] if len(sys.argv)>1 else root/'output/space-octopus.circuit.json');out=Path(sys.argv[2]) if len(sys.argv)>2 else root/'output/kicad';out.mkdir(parents=True,exist_ok=True)
# Preserve the earlier KiCad project. Its symbols, UUIDs and exact pin maps
# remain valid; only the generated derivative receives the current board.
for path in (root/'kicad').iterdir():
 if path.name not in ['libraries','assets','fp-lib-table','sym-lib-table','motor-interface.json','external-assemblies.json'] and path.suffix not in ['.kicad_sch','.kicad_pro']:continue
 dest=out/path.name
 if path.is_dir():shutil.copytree(path,dest,dirs_exist_ok=True)
 elif path.suffix not in ['.kicad_pcb','.kicad_prl']:shutil.copy2(path,dest)
for path in out.glob('*.kicad_sch'):
 path.write_text(path.read_text().replace('Unrouted motor controller; provisional packages and assembly fit pending','Motor controller from tscircuit; package and system qualification pending'))
j=json.loads(src.read_text());parts=sum([json.loads((root/'data'/f'{n}.json').read_text()) for n in ['input-supplies-mcu-driver-inverter','sensing-fault-interfaces-brake','mechanical']],[]);loc=json.loads((root/'data/placement.json').read_text());geo=json.loads((root/'data/board-geometry.json').read_text());mm=p.FromMM
# Normalize the vendored definition as well as the board instance, so KiCad
# compares it against the same SMT face policy used by the source importer.
library=out/'libraries/SpaceOctopus.pretty'
model_report={r['footprint']:r for r in json.loads((root/'data/cad-model-report.json').read_text()) if r['status']=='available'}
model_dir=out/'libraries/SpaceOctopus.3dshapes';model_dir.mkdir(parents=True,exist_ok=True)
for key in {part['footprint'] for part in parts}:
 fname=key.replace('/','__');shutil.copy2(root/'footprints/kicad'/(fname+'.kicad_mod'),library/(fname+'.kicad_mod'))
 for change in json.loads((root/'data/motor-mount-revision.json').read_text())['changes']:
  if change['newFootprint']==key and change['oldFootprint']!=key:
   for sch in out.glob('*.kicad_sch'):sch.write_text(sch.read_text().replace('SpaceOctopus:'+change['oldFootprint'].replace('/','__'),'SpaceOctopus:'+fname))
for path in library.glob('*.kicad_mod'):
 fp=p.FootprintLoad(str(library),path.stem);changed=True
 key=path.stem.replace('__','/',1)
 if key in model_report:
  name=model_report[key]['model'].replace('/','__');shutil.copy2(root/'assets/3d'/name,model_dir/name)
  for model in fp.Models():model.m_Filename='${KIPRJMOD}/libraries/SpaceOctopus.3dshapes/'+name;model.m_Show=True
 if json.loads((root/'data/silkscreen-plan.json').read_text()).get('enabled'):
  for item in fp.GraphicalItems():
   if item.GetLayer()==p.F_SilkS:item.SetLayer(p.F_Fab)
   elif item.GetLayer()==p.B_SilkS:item.SetLayer(p.B_Fab)
  fp.Reference().SetLayer(p.F_Fab)
 for pad in fp.Pads():
  stack=pad.GetLayerSet();cu=list(stack.CuStack())
  if pad.GetAttribute()==p.PAD_ATTRIB_SMD and cu and cu!=[p.F_Cu]:
   for layer in cu:stack.RemoveLayer(layer)
   stack.AddLayer(p.F_Cu);pad.SetLayerSet(stack);changed=True
 if changed:
  fp.SetFPID(p.LIB_ID('SpaceOctopus',path.stem));p.FootprintSave(str(library),fp)

def point(x,y):return p.VECTOR2I(mm(x),mm(y))
def xy(v):return point(100+v['x'],100-v['y'])
b=p.BOARD();b.SetCopperLayerCount(4)
settings=b.GetDesignSettings();settings.SetBoardThickness(mm(1.6));settings.m_MinClearance=mm(.2);settings.m_TrackMinWidth=mm(.15);settings.m_ViasMinSize=mm(.4);settings.m_MinThroughDrill=mm(.2);settings.m_CopperEdgeClearance=mm(.5);settings.m_HoleClearance=mm(.2)
net_by_name={}
for index,name in enumerate(sorted({n for part in parts for n in part['pins'].values() if n}),1):
 net=p.NETINFO_ITEM(b,name,index);b.Add(net);net_by_name[name]=net
for part in parts:
 fname=part['footprint'].replace('/','__');fp=p.FootprintLoad(str(out/'libraries/SpaceOctopus.pretty'),fname)
 if not fp:raise RuntimeError('Missing native footprint '+fname)
 b.Add(fp);fp.SetReference(part['ref']);fp.SetFPID(p.LIB_ID('SpaceOctopus',fname));fp.Value().SetVisible(False)
 if part['ref']=='JP701':fp.SetAttributes(fp.GetAttributes()|p.FP_EXCLUDE_FROM_POS_FILES)
 def uid(value):return str(uuid.uuid5(uuid.NAMESPACE_URL,'space-octopus/kicad/'+value))
 symbol_path='/'+uid('root')+('/'+uid('sheet/'+part['sheet']) if part['sheet']!='Mechanical' else '')+'/'+uid('symbol/'+part['ref'])
 fp.SetPath(p.KIID_PATH(symbol_path))
 if part['dnp']:fp.SetAttributes(fp.GetAttributes()|p.FP_DNP)
 for model in fp.Models():
  if not Path(str(model.m_Filename).replace('${KIPRJMOD}',str(out))).is_file():model.m_Show=False
 v=loc[part['ref']];bottom=v['layer']=='bottom'
 if (fp.GetLayer()==p.B_Cu)!=bottom:fp.Flip(point(0,0),False)
 fp.SetOrientationDegrees(v['rotation']+(180 if bottom else 0));fp.SetPosition(point(100+v['x'],100-v['y']));fp.SetValue(part.get('mpn') or part['value'])
 for pad in fp.Pads():
  # The source importer places SMT copper on the component face. Some stock
  # thermal footprints also contain a reverse-side copper patch; follow the
  # actual tscircuit geometry rather than silently adding that extra patch.
  if pad.GetAttribute()==p.PAD_ATTRIB_SMD and list(pad.GetLayerSet().CuStack()):
   target=p.B_Cu if bottom else p.F_Cu
   if list(pad.GetLayerSet().CuStack())!=[target]:
    stack=pad.GetLayerSet()
    for layer in list(stack.CuStack()):stack.RemoveLayer(layer)
    stack.AddLayer(target);pad.SetLayerSet(stack)
  name=part['pins'].get(pad.GetNumber())
  if name:pad.SetNet(net_by_name[name])
  else:pad.SetNetCode(0)
for radius in [geo['outerDiameterMm']/2,geo['centralOpeningDiameterMm']/2]:
 shape=p.PCB_SHAPE();shape.SetShape(p.SHAPE_T_CIRCLE);shape.SetCenter(point(100,100));shape.SetEnd(point(100+radius,100));shape.SetLayer(p.Edge_Cuts);shape.SetWidth(mm(.05));b.Add(shape)
netnames={a['source_net_id']:a['name'] for a in j if a['type']=='source_net'};tracenet={a['source_trace_id']:a.get('connected_source_net_ids',[None])[0] for a in j if a['type']=='source_trace' and a.get('connected_source_net_ids')};ls={'top':p.F_Cu,'inner1':p.In1_Cu,'inner2':p.In2_Cu,'bottom':p.B_Cu};seen=set();via_count=0;track_count=0;zone_count=0;rule_area_count=0;track_map=[]

def addvia(v,net):
 global via_count
 key=(round(v['x'],6),round(v['y'],6))
 if key in seen:return
 seen.add(key);via=p.PCB_VIA(b);via.SetPosition(xy(v));via.SetWidth(p.F_Cu,mm(v.get('outer_diameter',v.get('via_diameter',.4))));via.SetDrill(mm(v.get('hole_diameter',v.get('via_hole_diameter',.2))));via.SetViaType(p.VIATYPE_THROUGH);via.SetLayerPair(p.F_Cu,p.B_Cu);via.SetNet(net_by_name[net]);b.Add(via);via_count+=1
for a in j:
 if a['type']=='pcb_trace':
  if a.get('pcb_trace_id','').startswith('pad_contact_'):continue
  net=netnames.get(tracenet.get(a.get('source_trace_id')) or a.get('connection_name'))
  if not net:raise RuntimeError('Unresolved net on '+a['pcb_trace_id'])
  for k,v in enumerate(a['route']):
   if v['route_type']=='via':addvia(v,net)
   elif k and a['route'][k-1]['route_type']=='wire':
    u=a['route'][k-1]
    if math.dist((u['x'],u['y']),(v['x'],v['y']))<1e-7:continue
    t=p.PCB_TRACK(b);t.SetStart(xy(u));t.SetEnd(xy(v));t.SetWidth(mm(v.get('width',u.get('width',.25))));t.SetLayer(ls[v['layer']]);t.SetNet(net_by_name[net]);b.Add(t);track_count+=1;track_map.append({'uuid':t.m_Uuid.AsString(),'traceId':a['pcb_trace_id'],'segmentIndex':k,'net':net,'layer':v['layer']})
 elif a['type']=='pcb_via':
  net=netnames.get(a.get('source_net_id') or tracenet.get(a.get('source_trace_id')))
  if not net:raise RuntimeError('Unresolved via net')
  addvia(a,net)
 elif a['type']=='pcb_copper_pour':
  if a['shape']!='brep':raise RuntimeError('Expected a BRep copper region')
  z=p.ZONE(b);layer=ls[a['layer']];z.SetLayer(layer);z.SetNet(net_by_name[netnames[a['source_net_id']]]);z.SetLocalClearance(mm(.2));z.SetMinThickness(mm(.15));z.SetPadConnection(p.ZONE_CONNECTION_FULL);poly=p.SHAPE_POLY_SET();poly.NewOutline()
  for v in a['brep_shape']['outer_ring']['vertices']:q=xy(v);poly.Append(q.x,q.y,0,-1)
  for ring in a['brep_shape'].get('inner_rings',[]):
   hole=poly.NewHole(0)
   for v in ring['vertices']:q=xy(v);poly.Append(q.x,q.y,0,hole)
  z.Outline().Append(poly);poly.Fracture();z.SetFilledPolysList(layer,poly);z.SetIsFilled(True);z.SetNeedRefill(False);b.Add(z);zone_count+=1
 elif a['type']=='pcb_keepout':
  if a['shape']!='rect' or abs(a['width']-geo['mounting']['keepoutDiameterMm'])>.001 or abs(a['height']-geo['mounting']['keepoutDiameterMm'])>.001 or set(a['layers'])!=set(ls):continue
  z=p.ZONE(b);z.SetIsRuleArea(True);stack=p.LSET()
  for layer in a['layers']:stack.AddLayer(ls[layer])
  z.SetLayerSet(stack);z.SetDoNotAllowTracks(True);z.SetDoNotAllowVias(True);z.SetDoNotAllowCopperPour(True)
  # The owning mechanical hole is intentionally inside this reservation.
  # Component bodies/pads are checked against the source assembly envelopes.
  z.SetDoNotAllowPads(False);z.SetDoNotAllowFootprints(False)
  gap=geo['mounting'].get('copperKeepoutGapMm',.2);x=a['center']['x'];y=a['center']['y'];rx=a['width']/2;ry=a['height']/2
  poly=z.Outline();poly.NewOutline()
  # Match the source square buffered by the Euclidean copper gap, including
  # its rounded offset corners. A larger bounding rectangle blocks legal
  # power copper near those corners.
  for cx,cy,start in [(x+rx,y+ry,0),(x-rx,y+ry,90),(x-rx,y-ry,180),(x+rx,y-ry,270)]:
   for k in range(17):
    angle=math.radians(start+k*90/16);q=xy({'x':cx+gap*math.cos(angle),'y':cy+gap*math.sin(angle)});poly.Append(q.x,q.y)
  b.Add(z);rule_area_count+=1
 elif a['type']=='pcb_silkscreen_path':
  for u,v in zip(a['route'],a['route'][1:]):
   if math.dist((u['x'],u['y']),(v['x'],v['y']))<1e-7:continue
   shape=p.PCB_SHAPE();shape.SetShape(p.SHAPE_T_SEGMENT);shape.SetStart(xy(u));shape.SetEnd(xy(v));shape.SetLayer(p.F_SilkS if a.get('layer','top')=='top' else p.B_SilkS);shape.SetWidth(mm(a.get('stroke_width',.12)));b.Add(shape)
 elif a['type']=='pcb_silkscreen_text':
  text=p.PCB_TEXT(b);text.SetText(a['text']);text.SetPosition(xy(a['anchor_position']));text.SetLayer(p.F_SilkS if a.get('layer','top')=='top' else p.B_SilkS);text.SetTextSize(point(a.get('font_size',.8),a.get('font_size',.8)));text.SetTextThickness(mm(.12));text.SetMirrored(a.get('layer')=='bottom');text.SetHorizJustify(p.GR_TEXT_H_ALIGN_CENTER);text.SetVertJustify(p.GR_TEXT_V_ALIGN_CENTER);b.Add(text)
b.BuildConnectivity();b.SetFileName(str(out/'SpaceOctopus.kicad_pcb'));p.SaveBoard(str(out/'SpaceOctopus.kicad_pcb'),b)
project=json.loads((out/'SpaceOctopus.kicad_pro').read_text());rules=project['board']['design_settings']['rules'];rules.update({'min_clearance':.2,'min_track_width':.15,'min_via_diameter':.4,'min_through_hole_diameter':.2,'min_copper_edge_clearance':.5,'min_hole_clearance':.2});(out/'SpaceOctopus.kicad_pro').write_text(json.dumps(project,indent=2)+'\n')
(out/'README.md').write_text('# Current KiCad derivative\n\nGenerated from the current tscircuit source and saved copper. The root `kicad/` directory remains the earlier snapshot. Open `SpaceOctopus.kicad_pro`; schematics and component libraries are included. Copper zones preserve the audited tscircuit fill geometry.\n\nThis remains an engineering draft: provisional packages, stackup, current/thermal behavior and motor axial fit require qualification. Filled and capped via-in-pad manufacture is required. The 28 mm opening is proposed.\n')
report={'source':str(src.relative_to(root)) if src.is_relative_to(root) else str(src),'sourceSha256':hashlib.sha256(src.read_bytes()).hexdigest(),'pcbItems':len(parts),'nets':len(net_by_name),'trackSegments':track_count,'vias':via_count,'filledZones':zone_count,'mountingRuleAreas':rule_area_count,'kicadVersion':p.Version(),'fabricationReady':False};(out/'export-status.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
(out/'track-map.json').write_text(json.dumps(track_map,indent=2)+'\n')
