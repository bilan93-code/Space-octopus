"""Compare native board and KiCad-exported netlist against the source pin map."""
import json,os,sys,xml.etree.ElementTree as E,math
from pathlib import Path
for k,v in [('XDG_CONFIG_HOME','config'),('XDG_CACHE_HOME','cache'),('XDG_DATA_HOME','data')]:os.environ.setdefault(k,'/tmp/space-octopus-kicad/'+v)
import pcbnew as pcb
root=Path(__file__).resolve().parents[1];out=Path(sys.argv[1]) if len(sys.argv)>1 else root/'kicad';parts=sum([json.loads((root/'data'/f'{n}.json').read_text()) for n in ['input-supplies-mcu-driver-inverter','sensing-fault-interfaces-brake','mechanical']],[])
board=pcb.LoadBoard(str(out/'SpaceOctopus.kicad_pcb'));expected=json.loads((root/'output/expanded-netlist.json').read_text());errors=[]
byref={f.GetReference():f for f in board.GetFootprints()};actual={};nc=[]
for ref,f in byref.items():
 for pad in f.Pads():
  if pad.GetNumber() and pad.GetNetname():actual.setdefault(pad.GetNetname(),set()).add(ref+'.'+pad.GetNumber())
for p in parts:
 f=byref.get(p['ref'])
 if not f:errors.append('Missing native footprint '+p['ref']);continue
 for pin,net in p['pins'].items():
  pads=[a for a in f.Pads() if a.GetNumber()==pin]
  if not pads:errors.append(f'Missing physical pad {p["ref"]}.{pin}')
  if any((a.GetNetname() or None)!=net for a in pads):errors.append(f'Incorrect native net on {p["ref"]}.{pin}')
  if net is None:nc.append(p['ref']+'.'+pin)
 if p['ref'].startswith('H'):
  a=next(iter(f.Pads()));x=pcb.ToMM(a.GetPosition().x)-100;y=100-pcb.ToMM(a.GetPosition().y)
  if abs(math.hypot(x,y)-52)>0.001 or abs(pcb.ToMM(a.GetDrillSize().x)-4.5)>0.001:errors.append(p['ref']+' mounting dimension mismatch')
if set(actual)!=set(expected):errors.append('Native PCB net names differ')
for n,ends in expected.items():
 if actual.get(n,set())!=set(ends):errors.append('Native PCB endpoints differ: '+n)
netlist=E.parse(out/'reports/schematic-netlist.xml');sch={}
for n in netlist.findall('.//nets/net'):
 ends={x.attrib['ref']+'.'+x.attrib['pin'] for x in n.findall('node')}
 if n.attrib['name'].startswith('unconnected-'):
  if len(ends)!=1 or next(iter(ends)) not in nc:errors.append('Unexpected unconnected schematic net '+n.attrib['name'])
 else:sch[n.attrib['name']]=ends
for n,ends in expected.items():
 if sch.get(n,set())!=set(ends):errors.append('Native schematic endpoints differ: '+n)
if set(sch)!=set(expected):errors.append('Native schematic net names differ')
# Verify geometry after KiCad's side/rotation transforms, including asymmetric
# D2PAK drain pads. Reference positions alone cannot establish this.
circuit_path=Path(sys.argv[2]) if len(sys.argv)>2 else root/'output/space-octopus.circuit.json';cj=json.loads(circuit_path.read_text());src={e['source_component_id']:e['name'] for e in cj if e['type']=='source_component'}
pc={e['pcb_component_id']:src[e['source_component_id']] for e in cj if e['type']=='pcb_component' and e.get('source_component_id') in src}
count=0
active_layers={pcb.F_Cu,pcb.In1_Cu,pcb.In2_Cu,pcb.B_Cu};layer_ids={'top':pcb.F_Cu,'inner1':pcb.In1_Cu,'inner2':pcb.In2_Cu,'bottom':pcb.B_Cu}
for e in cj:
 if e['type'] not in ['pcb_smtpad','pcb_plated_hole'] or e.get('pcb_component_id') not in pc:continue
 ref=pc[e['pcb_component_id']];hints=e.get('port_hints',[]);number=next((a for a in hints if a.isdigit()),None)
 if not number:continue
 target=(100+e['x'],100-e['y']);pads=[p for p in byref[ref].Pads() if p.GetNumber()==number]
 if not any(math.hypot(pcb.ToMM(p.GetPosition().x)-target[0],pcb.ToMM(p.GetPosition().y)-target[1])<0.001 for p in pads):errors.append(f'Native geometry transform differs: {ref}.{number}')
 for pad in pads:
  if math.hypot(pcb.ToMM(pad.GetPosition().x)-target[0],pcb.ToMM(pad.GetPosition().y)-target[1])>=.001:continue
  w=e.get('width',e.get('rect_pad_width',e.get('outer_width',e.get('outer_diameter',2*e.get('radius',0)))))
  h=e.get('height',e.get('rect_pad_height',e.get('outer_height',e.get('outer_diameter',2*e.get('radius',0)))))
  a=math.radians(e.get('rect_ccw_rotation',e.get('ccw_rotation',0)));expected_size=(abs(w*math.cos(a))+abs(h*math.sin(a)),abs(w*math.sin(a))+abs(h*math.cos(a)))
  size=pad.GetSize();a=math.radians(pad.GetOrientationDegrees());nw=pcb.ToMM(size.x);nh=pcb.ToMM(size.y);actual_size=(abs(nw*math.cos(a))+abs(nh*math.sin(a)),abs(nw*math.sin(a))+abs(nh*math.cos(a)))
  if any(abs(x-y)>.003 for x,y in zip(expected_size,actual_size)):errors.append(f'Native pad dimensions/rotation differ: {ref}.{number}: {expected_size} vs {actual_size}')
  break
 count+=1
# Check the reverse direction too: no stock library copper may be added on
# another face (including optional thermal patches in a stock footprint).
for ref,f in byref.items():
 native=[e for e in cj if e['type'] in ['pcb_smtpad','pcb_plated_hole'] and pc.get(e.get('pcb_component_id'))==ref]
 for pad in f.Pads():
  if pad.GetAttribute()==pcb.PAD_ATTRIB_NPTH:continue
  copper=set(pad.GetLayerSet().CuStack())&active_layers
  if not copper:continue
  x=pcb.ToMM(pad.GetPosition().x)-100;y=100-pcb.ToMM(pad.GetPosition().y)
  match=any(math.hypot(e['x']-x,e['y']-y)<.001 and copper=={layer_ids[l] for l in e.get('layers',[e.get('layer','top')])} and (not pad.GetNumber() or pad.GetNumber() in e.get('port_hints',[])) for e in native)
  if not match:errors.append(f'Extra or wrong-face native copper: {ref}.{pad.GetNumber()} at {x:.4f},{y:.4f}')
fiducial_masks=0
for e in cj:
 if e['type']!='pcb_smtpad' or not pc.get(e.get('pcb_component_id'),'').startswith('FID'):continue
 ref=pc[e['pcb_component_id']];margin=e.get('soldermask_margin');pads=list(byref[ref].Pads())
 if margin is None or abs(2*(e['radius']+margin)-2)>.001:errors.append('Source fiducial mask opening differs: '+ref)
 elif not any(pad.GetLocalSolderMaskMargin() is not None and abs(pcb.ToMM(pad.GetLocalSolderMaskMargin())-margin)<.001 for pad in pads):errors.append('Native fiducial mask margin differs: '+ref)
 fiducial_masks+=1
if fiducial_masks!=3:errors.append('Expected three fiducial mask openings')
areas=[z for z in board.Zones() if z.GetIsRuleArea()];geo=json.loads((root/'data/board-geometry.json').read_text());gap=geo['mounting'].get('copperKeepoutGapMm',.2)
expected_areas=[a for a in cj if a['type']=='pcb_keepout' and a['shape']=='rect' and abs(a['width']-geo['mounting']['keepoutDiameterMm'])<.001 and abs(a['height']-geo['mounting']['keepoutDiameterMm'])<.001 and set(a['layers'])==set(layer_ids)]
if len(areas)!=len(expected_areas):errors.append('Native mounting keepout count differs')
for a in expected_areas:
 x=100+a['center']['x'];y=100-a['center']['y'];w=a['width']+2*gap;h=a['height']+2*gap
 match=[]
 for z in areas:
  bounds=z.Outline().BBox();centre=bounds.GetCenter();size=bounds.GetSize()
  if abs(pcb.ToMM(centre.x)-x)<.001 and abs(pcb.ToMM(centre.y)-y)<.001 and abs(pcb.ToMM(size.x)-w)<.003 and abs(pcb.ToMM(size.y)-h)<.003:match.append(z)
 if not any(set(z.GetLayerSet().CuStack())=={layer_ids[l] for l in a['layers']} and z.GetDoNotAllowTracks() and z.GetDoNotAllowVias() and z.GetDoNotAllowCopperPour() for z in match):errors.append('Native mounting keepout policy/geometry differs: '+a['pcb_keepout_id'])
drcpath=out/'reports/drc.json';drc=json.loads(drcpath.read_text()) if drcpath.exists() else None
if out.resolve()==(root/'output/kicad').resolve():
 if drc is None:errors.append('Current derivative has no native KiCad DRC report')
 elif any(e['severity']=='error' for e in drc.get('violations',[])) or drc.get('unconnected_items'):errors.append('Current KiCad DRC has electrical/geometric errors or disconnected items')
 ercpath=out/'reports/erc.json'
 if not ercpath.exists():errors.append('Current derivative has no native schematic ERC report')
 else:
  erc=json.loads(ercpath.read_text())
  if len(erc.get('sheets',[]))!=10 or any(sheet.get('violations') for sheet in erc.get('sheets',[])):errors.append('Native schematic ERC has findings or missing sheets')
report={'status':'passed' if not errors else 'failed','kicadVersion':pcb.Version(),'pcbItems':len(byref),'electricalNets':len(expected),'padPositionsChecked':count,'fiducialMaskOpeningsChecked':fiducial_masks,'mountingRuleAreasChecked':len(expected_areas),'explicitNoConnectPins':len(nc),'electricalParity':not errors,'routingComplete':len(drc.get('unconnected_items',[]))==0 if drc is not None else None,'errors':errors}
(out/'reports/native-parity.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2));raise SystemExit(bool(errors))
