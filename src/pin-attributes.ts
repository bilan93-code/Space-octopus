import type {Part} from './design';
const outputs:Record<string,number[]>={U1:[18,19,23,24,35,36,37,38,39,40,42,43,44,46,52,54,55,56,58,59,62],U2:[5,6,8,13,15,16,18,21,22,23,38,40],U3:[7,8],U4:[7],U5:[5],U6:[4],U9:[3,5],U10:[3,5,7,9,12,14,16,18],U11:[4],U14:[4],U15:[4],U17:[2,3],U18:[1,6,7],U19:[2],U20:[1],Y1:[3]};
const openDrain:Record<string,number[]>={U2:[26,27],U3:[6],U4:[8],U7:[1,2,13,14],U8:[1,2,13,14],U12:[1],U13:[7,8],U16:[4]};
const powerOut:Record<string,number[]>={U2:[5,38,40],U5:[5],U19:[2]};
const powerPins=new Set(['VBAT','VDD','VCC','V+','V-','VIN','IN','VIO','VSSA','VSS','GND','AGND','PGND','EP','PAD','VDDA','VREF+','VM','VDRAIN','VREF']);
export function pinAttributesFor(p:Part):Record<string,any>{
 return Object.fromEntries(Object.entries(p.pins).map(([pin,net])=>{
  const n=+pin,label=p.pinLabels[pin]??'';let a:Record<string,any>={};
  if(net===null)a={doNotConnect:true};
  else if(p.kind!=='chip')a={isPassive:true};
  else if(powerOut[p.ref]?.includes(n))a={providesPower:true};
  else if(openDrain[p.ref]?.includes(n))a={isOutput:true,canUseOpenDrain:true,isUsingOpenDrain:true};
  else if(outputs[p.ref]?.includes(n))a={isOutput:true};
  else if(net==='GND'&&powerPins.has(label))a={requiresGround:true};
  else if(powerPins.has(label))a={requiresPower:true};
  else if(p.ref==='U1'&&/^P[A-G]/.test(label))a={isBidirectional:true,isGpio:true};
  else a={isInput:true};
  // Explicit supply declarations at the output of passive power paths. These
  // have the same meaning as a schematic power flag, not regulator models.
  if((p.ref==='L101'&&net==='V12')||(p.ref==='L102'&&net==='V5')||(p.ref==='FB201'&&net==='VDDA3V3')||(p.ref==='J1'&&net==='VBUS'))a.providesPower=true;
  if(p.ref==='J1'&&net==='GND')a.providesGround=true;
  return [`pin${pin}`,a];
 }));
}
