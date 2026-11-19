"""Local Specctra interchange from current tscircuit capture, never native source.
The native board is a routing work file; the tscircuit project remains authoritative.
"""
import os,json,math,re,sys
from pathlib import Path
for key,leaf in [('XDG_CONFIG_HOME','config'),('XDG_CACHE_HOME','cache'),('XDG_DATA_HOME','data')]:os.environ.setdefault(key,'/tmp/space-octopus-kicad/'+leaf)
import pcbnew as p
root=Path(__file__).resolve().parents[1];out=root/'routing-work/revision';out.mkdir(parents=True,exist_ok=True)
parts=sum([json.loads((root/'data'/f'{n}.json').read_text()) for n in ['input-supplies-mcu-driver-inverter','sensing-fault-interfaces-brake','mechanical']],[])
loc=json.loads((root/'data/placement.json').read_text());geo=json.loads((root/'data/board-geometry.json').read_text())
j=json.loads(Path(sys.argv[1] if len(sys.argv)>1 else 'output/space-octopus.circuit.json').read_text())
mm=p.FromMM
def pt(x,y):return p.VECTOR2I(mm(x),mm(y))
def xy(v):return pt(100+v['x'],100-v['y'])
b=p.BOARD();b.SetCopperLayerCount(4);b.GetDesignSettings().SetBoardThickness(mm(1.6));b.GetDesignSettings().m_MinClearance=mm(.2);b.GetDesignSettings().m_TrackMinWidth=mm(.15);b.GetDesignSettings().m_ViasMinSize=mm(.4);b.GetDesignSettings().m_MinThroughDrill=mm(.2);b.GetDesignSettings().m_CopperEdgeClearance=mm(.5);b.GetDesignSettings().m_HoleClearance=mm(.31)
nets={}
for i,n in enumerate(sorted({v for a in parts for v in a['pins'].values() if v}),1):
 z=p.NETINFO_ITEM(b,n,i);b.Add(z);nets[n]=z
for a in parts:
 lib,name=a['footprint'].split('/');fp=p.FootprintLoad(str(root/'footprints/kicad'),lib+'__'+name)
 if not fp:
  # FootprintLoad requires .pretty conventions; the vendored KiCad library is
  # an exact copy apart from explicit U13 thermal-drill correction.
  fp=p.FootprintLoad(str(root/'kicad/libraries/SpaceOctopus.pretty'),lib+'__'+name)
 if not fp:raise RuntimeError(a['footprint'])
 b.Add(fp);fp.SetReference(a['ref']);fp.SetValue(a.get('mpn',a['value']));v=loc[a['ref']]
 if v['layer']=='bottom':fp.Flip(pt(0,0),False)
 fp.SetOrientationDegrees(v['rotation']+(180 if v['layer']=='bottom' else 0));fp.SetPosition(pt(100+v['x'],100-v['y']))
 for pad in fp.Pads():
  n=a['pins'].get(pad.GetNumber())
  if n:pad.SetNet(nets[n])
  else:pad.SetNetCode(0)
  if a['ref']=='U13' and pad.GetNumber()=='9' and pad.GetDrillSize().x>0:pad.SetDrillSize(pt(.3,.3));pad.SetSize(pt(.6,.6))
for r in [geo['outerDiameterMm']/2-.31,geo['centralOpeningDiameterMm']/2+.31]:
 s=p.PCB_SHAPE();s.SetShape(p.SHAPE_T_CIRCLE);s.SetCenter(pt(100,100));s.SetEnd(pt(100+r,100));s.SetLayer(p.Edge_Cuts);s.SetWidth(mm(.01));b.Add(s)
netnames={x['source_net_id']:x['name'] for x in j if x['type']=='source_net'}
tracenet={x['source_trace_id']:netnames.get(x.get('connected_source_net_ids',[None])[0]) for x in j if x['type']=='source_trace' and x.get('connected_source_net_ids')}
layers={'top':p.F_Cu,'inner1':p.In1_Cu,'inner2':p.In2_Cu,'bottom':p.B_Cu};vias=set()
for a in j:
 if a['type']!='pcb_trace':continue
 net=tracenet.get(a.get('source_trace_id')) or netnames.get(a.get('connection_name'))
 if not net:raise ValueError(a)
 for k,v in enumerate(a['route']):
  if v['route_type']=='via':
   key=(net,v['x'],v['y'])
   if key in vias:continue
   vias.add(key);t=p.PCB_VIA(b);t.SetPosition(xy(v));t.SetWidth(p.F_Cu,mm(v.get('via_diameter',.4)));t.SetDrill(mm(v.get('via_hole_diameter',.2)));t.SetViaType(p.VIATYPE_THROUGH);t.SetLayerPair(p.F_Cu,p.B_Cu);t.SetNet(nets[net]);b.Add(t)
  elif k and a['route'][k-1]['route_type']=='wire':
   u=a['route'][k-1]
   if math.hypot(u['x']-v['x'],u['y']-v['y'])<1e-7:continue
   t=p.PCB_TRACK(b);t.SetStart(xy(u));t.SetEnd(xy(v));t.SetLayer(layers[v['layer']]);t.SetWidth(mm(v['width']));t.SetNet(nets[net]);b.Add(t)
# Export explicit reference planes. No KiCad zone fill is used here: native
# tscircuit generates the final clipped copper after route import.
p.SaveBoard(str(out/'SpaceOctopus.kicad_pcb'),b)
assert p.ExportSpecctraDSN(b,str(out/'SpaceOctopus.dsn'))
s=(out/'SpaceOctopus.dsn').read_text()
# KiCad's default net class is independent of the board minimum.
s=s.replace('(width 250)','(width 200)').replace('(type route)','(type protect)')
# The two 0.5-mm pitch chips require 0.15-mm necks; all other default routes .2.
# A net class can neck a whole logic net; power widths are assigned separately.
start=s.index('    (class kicad_default ');depth=0
for i in range(start,len(s)):
 if s[i]=='(':depth+=1
 if s[i]==')':
  depth-=1
  if depth==0:end=i+1;break
power={'DC_IN','VBUS','PH_U','PH_V','PH_W','SHUNT_U_TOP','SHUNT_V_TOP','SHUNT_W_TOP','BRAKE_PLUS','BRAKE_DRAIN'}
gates={'GH_U','GL_U','GH_V','GL_V','GH_W','GL_W','Q1_G','Q2_G','Q3_G','Q4_G','Q5_G','Q6_G','BRAKE_GATE','BRAKE_DRV_OUTH','BRAKE_DRV_OUTL'}
classes=[]
for name,ns,w in [('PowerBranches',power,150),('Gates',gates,200),('Logic',set(nets)-power-gates,150)]:
 classes.append('    (class '+name+' '+' '.join(sorted(ns))+' (circuit(use_via "Via[0-3]_400:200_um"))(rule(width '+str(w)+')(clearance 200)))')
s=s[:start]+'\n'.join(classes)+s[end:]
# Enforce actual square screw-head reservations on every signal layer, including
# the extra .2-mm copper gap, as Specctra board-level keepouts.
keep=[]
for ref,v in loc.items():
 if not re.fullmatch(r'H\d+',ref):continue
 r=(geo['mounting']['keepoutDiameterMm']/2+.2)*1000;x=(100+v['x'])*1000;y=(v['y']-100)*1000
 keep.append(f'(keepout "{ref}" (rect signal {x-r} {y-r} {x+r} {y+r}))')
def polygon(layer,points):
 return '(polygon '+layer+' 0 '+' '.join(str(round(v*1000,2)) for x,y in points for v in [100+x,y-100])+')'
for plane in json.loads((out/'planes.json').read_text()):
 layer={'inner1':'In1.Cu','inner2':'In2.Cu'}[plane['layer']]
 keep.append('(plane '+plane['name']+' '+polygon(layer,plane['outer'])+' '+''.join('(window '+polygon(layer,ring)+')' for ring in plane['holes'])+')')
s=s.replace('    (via \"','\n'.join(keep)+'\n    (via \"',1)
(out/'SpaceOctopus.dsn').write_text(s)
print('Exported current placement and protected copper:',len(parts),'parts,',len(nets),'nets,',len(vias),'pre-routed vias.')
