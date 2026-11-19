import fs from 'node:fs';
const parts=['input-supplies-mcu-driver-inverter','sensing-fault-interfaces-brake','mechanical'].flatMap(n=>JSON.parse(fs.readFileSync(`data/${n}.json`)));
const catalog=JSON.parse(fs.readFileSync('footprints/catalog.json')),models=JSON.parse(fs.readFileSync('data/cad-model-report.json')),references=JSON.parse(fs.readFileSync('data/reference-pinmaps.json'));
const errors=[],rows=[];
for(const p of parts){const fp=catalog[p.footprint];if(!fp){errors.push('Missing footprint '+p.ref);continue;}
 const pads=fp.elements.filter(e=>['pcb_smtpad','pcb_plated_hole'].includes(e.type));
 for(const pin of Object.keys(p.pins))if(!pads.some(e=>(e.port_hints??[]).includes(pin)||(e.port_hints??[]).includes('pin'+pin)))errors.push(`Missing footprint pin ${p.ref}.${pin}`);
 if(references[p.ref])for(const [pin,label] of Object.entries(references[p.ref].pins))if(![label,label+'_NRST'].includes(p.pinLabels[pin]))errors.push(`Independent library pin mismatch ${p.ref}.${pin}`);
 const model=models.find(m=>m.footprint===p.footprint);
 rows.push({ref:p.ref,footprint:p.footprint,mpn:p.mpn??null,physicalCopperPads:pads.length,logicalPins:Object.keys(p.pins).length,manufacturerReviewPending:!!p.provisional,openItem:p.provisionalReason??null,bodyModel:p.ref==='JP701'?'bare PCB feature':model?.verification??'no body required or unavailable'});
}
const report={status:errors.length?'failed':'passed',errors,inventoryItems:parts.length,independentlyComparedMcuPins:Object.keys(references.U1.pins).length,provisionalParts:rows.filter(r=>r.manufacturerReviewPending).length,parts:rows,limitations:['Pin presence and the MCU library comparison do not qualify manufacturer land patterns.','Exact DRV8353 RTA, FLUX cable mapping for J4, provisional diode pinouts and remaining open component choices require manufacturer review.','Direct manufacturer access remains blocked. Archived manufacturer PDFs now verify the targeted Rubycon bulk selection and TI TPS3431 pins/timing/copper; other unresolved drawings are not claimed verified.','The new JST GH candidates change the provisional XH mating harness. Verify exact mating parts and current/voltage ratings.','Phoenix MKDS 3 terminal families are candidates; exact ordering codes, wire ratings and the >=100 Vdc requirement are unconfirmed.']};
if(fs.existsSync('docs/manufacturer-access-review.json'))report.manufacturerAccessEvidence=JSON.parse(fs.readFileSync('docs/manufacturer-access-review.json'));
fs.writeFileSync('output/package-review.json',JSON.stringify(report,null,2)+'\n');console.log('Package capture review:',report.status,';',report.independentlyComparedMcuPins,'MCU pins independently compared;',report.provisionalParts,'provisional parts.');for(const e of errors)console.log(e);process.exitCode=errors.length?1:0;
