"""Constrain the local autorouter to low-current nets; power remains explicit."""
from pathlib import Path
s=Path('routing-work/SpaceOctopus.dsn').read_text()
start=s.index('    (class kicad_default ');depth=0;end=None
for i in range(start,len(s)):
 if s[i]=='(':depth+=1
 elif s[i]==')':
  depth-=1
  if depth==0:end=i+1;break
old=s[start:end];nets=old.split('(circuit',1)[0].replace('(class kicad_default','').split()
power={'DC_IN','VBUS','GND','PH_U','PH_V','PH_W','SHUNT_U_TOP','SHUNT_V_TOP','SHUNT_W_TOP','BRAKE_PLUS','BRAKE_DRAIN'}
gates={'GH_U','GL_U','GH_V','GL_V','GH_W','GL_W','Q1_G','Q2_G','Q3_G','Q4_G','Q5_G','Q6_G','BRAKE_GATE','BRAKE_DRV_OUTH','BRAKE_DRV_OUTL'}
rails={'V12','V5','V3V3','VDDA3V3','ENC12','ENC12_FUSED','DRV_VGLS','DRV_DVDD','VCP','CP_H','CP_L','BUCK12_SW','BUCK5_SW','BST12'}
classes=[]
for name,chosen,width in [('PowerManual',power,2000),('GateDrive',gates,400),('AuxRails',rails,500),('Logic',set(nets)-power-gates-rails,250)]:
 members=sorted(set(nets)&chosen)
 classes.append('    (class '+name+' '+' '.join(members)+' (circuit(use_via "Via[0-3]_600:300_um"))(rule(width '+str(width)+')(clearance 200)))')
s=s[:start]+'\n'.join(classes)+s[end:]
Path('routing-work/SpaceOctopus-signals.dsn').write_text(s)
print('Prepared local routing input; excluded high-current backbone nets:',','.join(sorted(power)))
