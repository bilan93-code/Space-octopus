import fs from 'node:fs';
import {checkDanglingTraces,checkPadTraceClearance} from '@tscircuit/checks';
const [input,output]=process.argv.slice(2);
const json=JSON.parse(fs.readFileSync(input,'utf8'));
const diagnostics=[...checkDanglingTraces(json),...checkPadTraceClearance(json)];
fs.writeFileSync(output,JSON.stringify(diagnostics,null,2)+'\n');
console.log(`${diagnostics.length} endpoint/pad clearance diagnostics`);
