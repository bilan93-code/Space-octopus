"""One-time migration to native KiCad 9 files. Native files are editable sources.
Do not rerun after hand editing the KiCad project: it replaces generated files.
"""
import json,math,re,uuid,shutil,os,sys
from pathlib import Path
for key,leaf in [('XDG_CONFIG_HOME','config'),('XDG_CACHE_HOME','cache'),('XDG_DATA_HOME','data')]:os.environ.setdefault(key,'/tmp/space-octopus-kicad/'+leaf)
import pcbnew as pcb
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'kicad';LIB=OUT/'libraries';PRETTY=LIB/'SpaceOctopus.pretty';PRETTY.mkdir(parents=True,exist_ok=True)
if (OUT/'SpaceOctopus.kicad_pro').exists() and '--replace-generated' not in sys.argv:
 raise SystemExit('Native KiCad files already exist. Edit them directly. --replace-generated explicitly replaces them from the earlier baseline and discards native edits.')
PROJECT='SpaceOctopus';ROOTID=str(uuid.uuid5(uuid.NAMESPACE_URL,'space-octopus/kicad/root'))
def uid(s):return str(uuid.uuid5(uuid.NAMESPACE_URL,'space-octopus/kicad/'+s))
def q(s):return json.dumps(str(s),ensure_ascii=False)
def mm(n):return pcb.FromMM(n)
def pt(x,y):return pcb.VECTOR2I(mm(x),mm(y))
parts=sum([json.loads((ROOT/'data'/f'{n}.json').read_text()) for n in ['input-supplies-mcu-driver-inverter','sensing-fault-interfaces-brake','mechanical']],[])
position=json.loads((ROOT/'data/placement.json').read_text());geometry=json.loads((ROOT/'data/board-geometry.json').read_text())
sheets=['00_Input','01_Supplies','02_MCU','03_GateDriver','04_Inverter','05_Sensing','06_FaultLogic','07_Interfaces','08_Brake']
netnames=sorted({v for p in parts for v in p['pins'].values() if v is not None})
# Each custom symbol preserves the PDF's exact package pin map. Power and I/O
# electrical types are explicit, so ERC has useful checks instead of all-passive ICs.
POWER_IN={'VBAT','VDD','VCC','V+','V-','VIN','IN','VIO','VSSA','VSS','GND','AGND','PGND','EP','PAD','VDDA','VREF+','VM','VDRAIN','VREF'}
OUT_PINS={
 'U1':{18,19,23,24,35,36,37,38,39,40,42,43,44,46,52,54,55,56,58,59,62},
 'U2':{5,6,8,13,15,16,18,21,22,23,38,40},'U3':{7,8},'U4':{7},'U5':{5},'U6':{4},
 'U9':{3,5},'U10':{3,5,7,9,12,14,16,18},'U11':{4},'U14':{4},'U15':{4},'U17':{2,3},'U18':{1,6,7},'U19':{2},'U20':{1},'Y1':{3}}
OPEN_DRAIN={'U2':{26,27},'U3':{6},'U4':{8},'U7':{1,2,13,14},'U8':{1,2,13,14},'U12':{1},'U13':{7,8},'U16':{4}}
POWER_OUT={'U2':{5,38,40},'U5':{5},'U19':{2}}
def pin_type(p,pin,label,net):
 n=int(pin);ref=p['ref']
 if p['kind'] not in ['chip']:return 'passive'
 if n in POWER_OUT.get(ref,set()):return 'power_out'
 if n in OPEN_DRAIN.get(ref,set()):return 'open_collector'
 if n in OUT_PINS.get(ref,set()):return 'output'
 if label in POWER_IN or (net in ['V3V3','V5','V12','VDDA3V3','GND'] and label not in ['D','/PRE','EN','SET1','IN-']):return 'power_in'
 if ref=='U1' and label.startswith(('PA','PB','PC','PD','PF','PG')):return 'bidirectional'
 return 'input'
# Local symbols deliberately use a unique lib_id per physical part; MPN and
# provisional status are retained as fields on symbol and footprint.
symbols={};pins_xy={};symbol_size={}
def line(x1,y1,x2,y2):return f'(polyline (pts (xy {x1} {y1})(xy {x2} {y2}))(stroke(width 0.254)(type default))(fill(type none)))'
def rect(x1,y1,x2,y2):return f'(rectangle(start {x1} {y1})(end {x2} {y2})(stroke(width 0.254)(type default))(fill(type background)))'
def make_symbol(p):
 ref=p['ref'];n=len(p['pins']);base='P_'+ref;graphics=[];loc={}
 simple=n==2 and p['kind'] in ['resistor','capacitor','inductor','fuse','diode','led','switch','thermistor']
 if simple:
  w=5.08;h=2.54;loc={'1':(-w,0,0),'2':(w,0,180)}
  if p['kind']=='capacitor':graphics=[line(-1.27,-2.54,-1.27,2.54),line(1.27,-2.54,1.27,2.54)];pinlength=3.81
  elif p['kind'] in ['diode','led']:
   graphics=[line(-1.27,-1.905,-1.27,1.905),line(-1.27,0,1.27,1.905),line(1.27,1.905,1.27,-1.905),line(1.27,-1.905,-1.27,0),line(-2.54,0,-1.27,0),line(1.27,0,2.54,0)];pinlength=2.54
  else:graphics=[rect(-2.54,1.016,2.54,-1.016)];pinlength=2.54
 elif p['kind']=='mosfet':
  w=7.62;h=5.08;loc={'1':(-7.62,0,0),'2':(5.08,5.08,270),'3':(5.08,-5.08,90)};pinlength=2.54
  graphics=[line(-5.08,0,-2.54,0),line(-2.54,-2.54,-2.54,2.54),line(-1.27,-2.54,-1.27,2.54),line(-1.27,2.54,5.08,2.54),line(-1.27,-2.54,5.08,-2.54)]
 elif n==1:
  w=2.54;h=2.54;loc={'1':(-5.08,0,0)};pinlength=2.54;graphics=['(circle(center 0 0)(radius 1.27)(stroke(width 0.254)(type default))(fill(type none)))',line(-2.54,0,-1.27,0)]
 else:
  count=math.ceil(n/2);w=15.24 if n>20 else 10.16;h=max(3.81,(count-1)*1.27+2.54);pinlength=2.54
  graphics=[rect(-w,h,w,-h)]
  keys=list(p['pins'])
  for i,key in enumerate(keys):
   side=0 if i<count else 1;k=i if side==0 else i-count
   y=(count-1)*1.27-k*2.54;loc[key]=((-w-2.54 if side==0 else w+2.54),y,0 if side==0 else 180)
 # A small named unconnected symbol for mounting holes / fiducials is useful
 # in the mechanical row and keeps PCB/schematic reference parity exact.
 if n==0:w=3.81;h=3.81;graphics=[rect(-w,h,w,-h)]
 libid='SpaceOctopus:'+base
 header=f'(symbol {q(libid)}(pin_names(offset 0.508))(exclude_from_sim no)(in_bom {"no" if p["kind"] in ["hole","fiducial"] else "yes"})(on_board yes)'
 header+=f'(property "Reference" {q(re.sub(r"[0-9]+$","",ref))}(at 0 {h+2.54} 0)(effects(font(size 1.27 1.27))))'
 header+=f'(property "Value" {q(p.get("mpn",p["value"]))}(at 0 {-h-2.54} 0)(effects(font(size 1.0 1.0))))'
 header+=f'(symbol {q(base+"_0_1")}{"".join(graphics)})'
 pintext=[]
 for pin,(x,y,a) in loc.items():
  label=p['pinLabels'].get(pin,pin);ptype=pin_type(p,pin,label,p['pins'][pin]);pintext.append(f'(pin {ptype} line(at {x} {y} {a})(length {pinlength})(name {q(label)}(effects(font(size 0.95 0.95))))(number {q(pin)}(effects(font(size 0.95 0.95)))))')
 header+=f'(symbol {q(base+"_1_1")}{"".join(pintext)}))'
 symbols[ref]=header;pins_xy[ref]=loc;symbol_size[ref]=(w,h);return header
for p in parts:make_symbol(p)
# Global labels join sheets by net name; each package pin gets a short wire,
# or an explicit no-connect mark. Repeated supply pins remain separate pins.
def prop(name,value,x,y,hidden=False,size=1.0):return f'(property {q(name)} {q(value)}(at {x:.4f} {y:.4f} 0)(effects(font(size {size} {size})){"(hide yes)" if hidden else ""}))'
def instantiate(p,x,y,sheetpath):
 ref=p['ref'];w,h=symbol_size[ref];sid=uid('symbol/'+ref);fpname=p['footprint'].replace('/','__')
 value=p.get('mpn',p['value']);s=f'(symbol(lib_id {q("SpaceOctopus:P_"+ref)})(at {x:.4f} {y:.4f} 0)(unit 1)(in_bom {"no" if p["kind"] in ["hole","fiducial"] else "yes"})(on_board yes)(dnp {"yes" if p["dnp"] else "no"})(uuid {q(sid)})'
 s+=prop('Reference',ref,x,y-h-3.81,size=1.27)+prop('Value',value,x,y+h+3.81)
 s+=prop('Footprint','SpaceOctopus:'+fpname,x,y,True)+prop('Datasheet','',x,y,True)
 s+=prop('Design status','PROVISIONAL' if p['provisional'] else 'Captured',x,y,True)+prop('Notes',p.get('provisionalReason',p.get('notes','')),x,y,True)
 for pin in p['pins']:s+=f'(pin {q(pin)}(uuid {q(uid("pin/"+ref+"/"+pin))}))'
 s+=f'(instances(project {q(PROJECT)}(path {q(sheetpath)}(reference {q(ref)})(unit 1)))))'
 wires=[]
 for pin,(px,py,a) in pins_xy[ref].items():
  ax=x+px;ay=y-py;net=p['pins'][pin]
  if net is None:wires.append(f'(no_connect(at {ax:.4f} {ay:.4f})(uuid {q(uid("nc/"+ref+"/"+pin))}))');continue
  dx=-5.08 if px<0 else 5.08
  # Vertical MOSFET D/S pin stubs follow their pin directions.
  if a in [90,270]:dx=0;dy=-5.08 if py>0 else 5.08
  else:dy=0
  bx=ax+dx;by=ay+dy
  wires.append(f'(wire(pts(xy {ax:.4f} {ay:.4f})(xy {bx:.4f} {by:.4f}))(stroke(width 0)(type default))(uuid {q(uid("wire/"+ref+"/"+pin))}))')
  angle=0 if dx<0 else 180 if dx>0 else 90 if dy<0 else 270
  wires.append(f'(global_label {q(net)}(shape input)(at {bx:.4f} {by:.4f} {angle})(effects(font(size 0.95 0.95))(justify {"left" if angle in [0,90] else "right"}))(uuid {q(uid("label/"+ref+"/"+pin))}))')
 return s+''.join(wires)
def sch_header(id,title):return f'(kicad_sch(version 20250114)(generator "eeschema")(generator_version "9.0")(uuid {q(id)})(paper "A3")(title_block(title {q(title)})(rev "A-KiCad-draft")(comment 1 "Unrouted motor controller; provisional packages and assembly fit pending"))'
def save_schematic(sheet,items,page):
 sheetid=uid('schematic/'+sheet);path='/'+ROOTID+'/'+uid('sheet/'+sheet)
 text=sch_header(sheetid,'SPACE OCTOPUS / '+sheet)+ '(lib_symbols'+''.join(symbols[p['ref']] for p in items)+')'
 # Large ICs occupy the first row; small components are arranged as pin/net
 # review cells below. A3 is enough for 64 physical pins at normal pitch.
 major=[p for p in items if p['kind'] in ['chip','connector']];minor=[p for p in items if p not in major]
 for i,p in enumerate(major):
  col=i%4;row=i//4;x=55.88+101.6*col;y=68.58+55.88*row
  if p['ref']=='U1':y=76.2
  text+=instantiate(p,x,y,path)
 start=139.7 if len(major)<=4 else 177.8
 for i,p in enumerate(minor):text+=instantiate(p,25.4+55.88*(i%7),start+25.4*(i//7),path)
 text+=f'(sheet_instances(path {q(path)}(page {q(page)})))(embedded_fonts no))'
 (OUT/(sheet+'.kicad_sch')).write_text(text)
for i,sheet in enumerate(sheets,2):save_schematic(sheet,[p for p in parts if p['sheet']==sheet],i)
mechanical=[p for p in parts if p['sheet']=='Mechanical']
flag='(symbol "SpaceOctopus:PowerFlag"(power)(pin_names(offset 0)(hide yes))(in_bom no)(on_board no)(property "Reference" "#FLG"(at 0 3.81 0)(effects(font(size 1 1))(hide yes)))(property "Value" "PWR_FLAG"(at 0 5.08 0)(effects(font(size 1 1))))(symbol "PowerFlag_0_1"(polyline(pts(xy 0 0)(xy 0 2.54)(xy -1.27 2.54)(xy 0 3.81)(xy 1.27 2.54)(xy 0 2.54))(stroke(width 0.254)(type default))(fill(type none))))(symbol "PowerFlag_1_1"(pin power_out line(at 0 0 90)(length 0)(name "pwr"(effects(font(size 1 1))))(number "1"(effects(font(size 1 1)))))))'
root=sch_header(ROOTID,'SPACE OCTOPUS / 48 V MOTOR CONTROLLER')+'(lib_symbols'+''.join(symbols[p['ref']] for p in mechanical)+flag+')'
for i,sheet in enumerate(sheets):
 x=25.4+(i%3)*127;y=38.1+(i//3)*55.88
 root+=f'(sheet(at {x} {y})(size 106.68 35.56)(stroke(width 0.254)(type default))(fill(color 0 0 0 0))(uuid {q(uid("sheet/"+sheet))})'
 root+=prop('Sheetname',sheet,x,y-1.27,size=1.27)+prop('Sheetfile',sheet+'.kicad_sch',x,y+36.83,size=1.0)
 root+=f'(instances(project {q(PROJECT)}(path {q("/"+ROOTID)}(page {q(i+2)})))))'
for i,p in enumerate(mechanical):root+=instantiate(p,25.4+i*43.18,238.76,'/'+ROOTID)
for i,net in enumerate(['VBUS','V12','V5','GND','VDDA3V3']):
 x=55.88+i*66.04;y=269.24;ref='#FLG0'+str(i+1)
 root+=f'(symbol(lib_id "SpaceOctopus:PowerFlag")(at {x} {y} 0)(unit 1)(in_bom no)(on_board no)(dnp no)(uuid {q(uid(ref))})'+prop('Reference',ref,x,y,True)+prop('Value','PWR_FLAG',x,y-5.08)+f'(pin "1"(uuid {q(uid(ref+"pin"))}))(instances(project {q(PROJECT)}(path {q("/"+ROOTID)}(reference {q(ref)})(unit 1)))))'
 root+=f'(global_label {q(net)}(shape input)(at {x} {y} 0)(effects(font(size 1 1))(justify left))(uuid {q(uid(ref+"label"))}))'
root+=f'(sheet_instances(path "/"(page "1")))(embedded_fonts no))'
(OUT/(PROJECT+'.kicad_sch')).write_text(root)
# Install a complete local symbol library matching the embedded definitions.
libtext='(kicad_symbol_lib(version 20241209)(generator "kicad_symbol_editor")'+''.join(s.replace('"SpaceOctopus:P_','"P_',1) for s in symbols.values())+flag.replace('SpaceOctopus:PowerFlag','PowerFlag',1)+')'
(LIB/'SpaceOctopus.kicad_sym').write_text(libtext)
(OUT/'sym-lib-table').write_text('(sym_lib_table(version 7)(lib(name "SpaceOctopus")(type "KiCad")(uri "${KIPRJMOD}/libraries/SpaceOctopus.kicad_sym")(options "")(descr "Exact package pin maps from Rev A motor controller")))\n')
(OUT/'fp-lib-table').write_text('(fp_lib_table(version 7)(lib(name "SpaceOctopus")(type "KiCad")(uri "${KIPRJMOD}/libraries/SpaceOctopus.pretty")(options "")(descr "Vendored native footprints; provisional mappings retained")))\n')
board=pcb.BOARD();board.SetCopperLayerCount(4);board.GetDesignSettings().SetBoardThickness(mm(1.6))
nets={}
for i,name in enumerate(netnames,1):n=pcb.NETINFO_ITEM(board,name,i);board.Add(n);nets[name]=n
for p in parts:
 lib,name=p['footprint'].split('/');fname=lib+'__'+name;src=ROOT/'footprints/kicad'/f'{fname}.kicad_mod';content=src.read_text()
 # Models ship inside the project, retaining each original offset/rotation.
 def model_path(m):
  rel=m.group(1);local='libraries/SpaceOctopus.3dshapes/'+rel.replace('/','__')
  return '(model "${KIPRJMOD}/'+local+'"'
 content=re.sub(r'\(model\s+"\$\{KICAD\d+_3DMODEL_DIR\}/([^"\n]+)"',model_path,content)
 (PRETTY/(fname+'.kicad_mod')).write_text(content)
 fp=pcb.FootprintLoad(str(PRETTY),fname)
 if not fp:raise RuntimeError('Cannot load '+fname)
 # Adapt the four EP thermal drills to the project's 0.3 mm drill rule,
 # retaining EP9 and its land geometry; save the same local library variant.
 if p['ref']=='U13':
  for pad in fp.Pads():
   if pad.GetNumber()=='9' and pad.GetDrillSize().x>0:
    pad.SetDrillSize(pt(0.3,0.3));pad.SetSize(pt(0.6,0.6))
  pcb.FootprintSave(str(PRETTY),fp)
 board.Add(fp);fp.SetReference(p['ref']);fp.SetValue(p.get('mpn',p['value']));fp.SetFPID(pcb.LIB_ID('SpaceOctopus',fname))
 path='/'+ROOTID+('/'+uid('sheet/'+p['sheet']) if p['sheet'] in sheets else '')+'/'+uid('symbol/'+p['ref'])
 fp.SetPath(pcb.KIID_PATH(path))
 xy=position[p['ref']];origin=pt(100+xy['x'],100-xy['y'])
 if xy['layer']=='bottom':fp.Flip(pt(0,0),False)
 fp.SetOrientationDegrees(xy['rotation']+(180 if xy['layer']=='bottom' else 0));fp.SetPosition(origin)
 fp.SetField('Design status','PROVISIONAL' if p['provisional'] else 'Captured');fp.SetField('Design note',p.get('provisionalReason',p.get('notes','')))
 for fieldname in ['Design status','Design note']:fp.GetFieldByName(fieldname).SetVisible(False)
 if p['dnp']:fp.SetAttributes(fp.GetAttributes()|pcb.FP_DNP)
 fp.Value().SetVisible(False);fp.Reference().SetTextSize(pt(0.8,0.8));fp.Reference().SetTextThickness(mm(0.12))
 if p['kind']=='hole':fp.Reference().SetVisible(False)
 for pad in fp.Pads():
  number=pad.GetNumber()
  if number in p['pins'] and p['pins'][number] is not None:pad.SetNet(nets[p['pins'][number]])
  elif number:pad.SetNetCode(0)
 # Unverified placeholder physical packages remain visible; no 3D body is
 # advertised as a manufacturer-specific model beyond its footprint family.
 for model in fp.Models():
  modelpath=str(model.m_Filename).replace('${KIPRJMOD}',str(OUT))
  if not Path(modelpath).is_file():model.m_Show=False
for radius in [geometry['outerDiameterMm']/2,geometry['centralOpeningDiameterMm']/2]:
 shape=pcb.PCB_SHAPE();shape.SetShape(pcb.SHAPE_T_CIRCLE);shape.SetCenter(pt(100,100));shape.SetEnd(pt(100+radius,100));shape.SetLayer(pcb.Edge_Cuts);shape.SetWidth(mm(0.05));board.Add(shape)
for text,x,y,size in [('SPACE OCTOPUS / REV A',100,61,0.8),('D112 / 48V / ROUTING DRAFT',100,139,0.8)]:
 t=pcb.PCB_TEXT(board);t.SetText(text);t.SetPosition(pt(x,y));t.SetTextSize(pt(size,size));t.SetTextThickness(mm(0.12));t.SetLayer(pcb.F_SilkS);board.Add(t)
board.SetFileName(str(OUT/(PROJECT+'.kicad_pcb')));pcb.SaveBoard(str(OUT/(PROJECT+'.kicad_pcb')),board)
# Stable KiCad project defaults; no DRC findings are excluded.
project=json.loads(Path('/usr/share/kicad/template/kicad.kicad_pro').read_text());project['meta']['filename']=PROJECT+'.kicad_pro'
project['board']['design_settings']['rules']={'min_clearance':0.2,'min_track_width':0.2,'min_via_diameter':0.6,'min_through_hole_diameter':0.3,'min_copper_edge_clearance':0.5,'min_hole_clearance':0.25}
project['board']['design_settings']['track_widths']=[0.25,0.3,0.5,1.0,2.0]
project['board']['design_settings']['via_dimensions']=[{'diameter':0.6,'drill':0.3}]
project['net_settings']={'classes':[{'name':'Default','clearance':0.2,'track_width':0.25,'via_diameter':0.6,'via_drill':0.3,'microvia_diameter':0.3,'microvia_drill':0.1,'diff_pair_width':0.25,'diff_pair_gap':0.2,'diff_pair_via_gap':0.25,'bus_width':12,'wire_width':6,'line_style':0,'schematic_color':[0,0,0,0],'pcb_color':[0,0,0,0]}],'meta':{'version':3},'netclass_assignments':{},'netclass_patterns':[]}
(OUT/(PROJECT+'.kicad_pro')).write_text(json.dumps(project,indent=2)+'\n')
(OUT/'reports/conversion-manifest.json').write_text(json.dumps({'kicadVersion':pcb.Version(),'pcbItems':len(parts),'nets':len(nets),'rootSchematic':PROJECT+'.kicad_sch','electricalSheets':sheets,'rootUUID':ROOTID,'boardOriginMm':[100,100],'routingStatus':'not routed','dimensions':geometry},indent=2)+'\n')
print('Created native KiCad',pcb.Version(),'project:',len(parts),'PCB items,',len(nets),'nets, 9 electrical sheets + root.')
