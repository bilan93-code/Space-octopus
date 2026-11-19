import fs from 'node:fs';
import path from 'node:path';
import parse from 's-expression';
import {createHash} from 'node:crypto';
const catalog=JSON.parse(fs.readFileSync('footprints/catalog.json'));
const models={},report=[];
const trimmedKey='Package_TO_SOT_THT/TO-220-2_Vertical';
const bulkKey='Capacitor_THT/CP_Radial_D18.0mm_P7.50mm';
const representative={
 'Package_DFN_QFN/DFN-10-1EP_3x3mm_P0.5mm_EP1.65x2.38mm':{file:'Package_DFN_QFN.3dshapes/DFN-10-1EP_3x3mm_P0.5mm_EP1.55x2.48mm.step',note:'Representative 3 x 3 mm 10-lead DFN body. Use the LT3065 DD drawing for land and exposed-pad dimensions.'},
 'Package_DFN_QFN/TI_RTA0040B_DRV8353':{file:'Package_DFN_QFN.3dshapes/QFN-40-1EP_6x6mm_P0.5mm_EP4.6x4.6mm.step',note:'Representative body geometry. TI RTA0040B defines the board copper and stencil.'},
 'Oscillator/Oscillator_SMD_Abracon_ASE-4Pin_3.2x2.5mm':{file:'Crystal.3dshapes/Crystal_SMD_3225-4Pin_3.2x2.5mm.step',note:'Representative 3.2 x 2.5 mm four-pad metal package. Oscillator height and case details require manufacturer verification.'},
 'Package_DFN_QFN/VQFN-40-1EP_6x6mm_P0.5mm_EP3.5x3.5mm':{file:'Package_DFN_QFN.3dshapes/QFN-40-1EP_6x6mm_P0.5mm_EP4.6x4.6mm.step',note:'Representative 6 x 6 mm 40-lead package body only. Model exposed pad differs; it does not validate the DRV8353 land pattern.'},
 'Package_DFN_QFN/Texas_DRB0008A':{file:'Package_DFN_QFN.3dshapes/DFN-8-1EP_3x3mm_P0.65mm_EP1.7x2.05mm.step',note:'Representative 3 x 3 mm eight-lead package body only. Model exposed pad differs; it does not validate the TPS3431 land pattern.'},
};
for(const key of Object.keys(catalog)){
 const raw=fs.readFileSync(`footprints/kicad/${key.replace('/','__')}.kicad_mod`,'utf8');
 const tree=parse(raw), model=tree.find(x=>Array.isArray(x)&&x[0]==='model');
 if(!model)continue;
 const originalName=String(model[1]).replaceAll('"','').replace(/^.*?\}\//,'').replace(/\.wrl$/,'.step');
 const sourceName=key===bulkKey?'generated/Rubycon_ZLJ_D18_40_MaxEnvelope.step':key===trimmedKey?'generated/TO-220-2_Vertical_LeadTrim2mm.step':representative[key]?.file??originalName;
 const file=`assets/3d/${sourceName.replace('/','__')}`;
 if(!fs.existsSync(file)){report.push({footprint:key,status:'missing',model:sourceName});continue;}
 const vector=(name)=>{const v=model.find(x=>Array.isArray(x)&&x[0]===name)?.[1];return v?{x:+v[1],y:+v[2],z:+v[3]}:{x:0,y:0,z:0};};
 const bytes=fs.readFileSync(file),sha256=createHash('sha256').update(bytes).digest('hex');
 models[key]={stepUrl:`data:application/step;base64,${bytes.toString('base64')}`,modelOriginPosition:{x:0,y:0,z:0},positionOffset:vector('offset'),rotationOffset:vector('rotate'),modelUnitToMmScale:1,modelBoardNormalDirection:'z+'};
 report.push({footprint:key,status:'available',model:sourceName,sha256,bytes:bytes.length,verification:representative[key]?'representative body only':key===trimmedKey?'stock package with 2 mm lead trim':'stock KiCad package-family model',...(representative[key]?{limitation:representative[key].note}:{}),...(key===trimmedKey?{assemblyRequirement:'Trim D2 leads to <=2 mm below the motor-facing PCB plane; see lead-trim-provenance.json.'}:{}),source:`https://raw.githubusercontent.com/KiCad/kicad-packages3D/master/${key===trimmedKey?originalName:sourceName}`});
 if(key==='Connector_JST/JST_SH_BM02B-SRSS-TB_1x02-1MP_P1.00mm_Vertical')Object.assign(report.at(-1),{verification:'part-specific STEP aligned to footprint frame',source:'https://github.com/SwashBuckler104/Micromouse/blob/ff4a18b755ba36d4287c2b25b5d82626a1462fe4/Components/BM02B-SRSS-TB_LF__SN_/BM02B-SRSS-TB_LF__SN_.step',transform:'Rotate +90 degrees around X and translate +1.2 mm along Y to align seating plane and contacts.'});
 if(key===bulkKey)Object.assign(report.at(-1),{verification:'manufacturer-dimension maximum envelope; generated STEP',source:'https://github.com/hank-bond/digikey-cap-finder/blob/37c424a900e3784d245f79d2d9c9938dea847907/series_pdfs/rubycon/ZLJ.pdf',assemblyRequirement:'18.5mm maximum diameter, 42mm maximum can length, 1mm seating allowance; reserve 3mm above the vent. Trim leads to <=2mm below PCB.',limitation:'Not a vendor appearance model. See bulk-cap-envelope-provenance.json.'});
}
fs.writeFileSync('data/cad-models.json',JSON.stringify(models)+'\n');
fs.writeFileSync('data/cad-model-report.json',JSON.stringify(report,null,2)+'\n');
fs.writeFileSync('assets/3d/current-model-provenance.json',JSON.stringify(report,null,2)+'\n');
console.log(`${Object.keys(models).length} real STEP models, ${report.filter(x=>x.status==='missing').length} unavailable model families. Models embedded for offline use.`);
