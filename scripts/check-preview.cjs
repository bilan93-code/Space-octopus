const fs=require('fs');const {createHash}=require('crypto');const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||'/usr/bin/chromium',headless:true,args:['--no-sandbox','--disable-dev-shm-usage']});
 const errors=[];const report={};
 try{
  const page=await browser.newPage({viewport:{width:1500,height:1100}});page.on('pageerror',e=>errors.push(String(e)));
  const base=process.env.OCTOPUS_PREVIEW_URL||'http://127.0.0.1:3021';
  await page.goto(base+'/index.html');await page.waitForSelector('#pcb svg');
  const wireTerminations={J1:['VBUS','GND'],J2:['PH_U','PH_V','PH_W'],J11:['BRAKE_PLUS','BRAKE_DRAIN']};
  for(const [ref,nets] of Object.entries(wireTerminations)){
   await page.locator(`#pcb [data-pad-name^="${ref}."]`).first().dispatchEvent('click');
   const shown=await page.locator('#inspector .pin span:last-child').allTextContents();
   if(await page.locator('#inspector h2').textContent()!==ref || JSON.stringify(shown)!==JSON.stringify(nets))throw new Error(`${ref}: wire pad inspection returned ${shown}`);
  }
  await page.screenshot({path:'output/review-preview.png'});
  await page.click('#face');await page.waitForFunction(()=>document.querySelector('#pcb-link').getAttribute('href')==='pcb-bottom.svg');await page.screenshot({path:'output/review-bottom-preview.png'});
  await page.click('#ratsnest');await page.waitForFunction(()=>document.querySelector('#ratsnest').textContent.includes('Hide'));
  await page.click('[data-tab="bom"]');
  await page.locator('#bom').getByText('U1',{exact:true}).first().click();
  if((await page.locator('#inspector h2').textContent())!=='U1')throw new Error('Component inspection failed');
  await page.click('[data-tab="schematics"]');await page.selectOption('#sheet','02_MCU');await page.waitForFunction(()=>document.querySelector('#schematic').complete&&document.querySelector('#schematic').naturalWidth>0);
  report.twoDimensional={passed:true,componentInspection:'U1',wireTerminations,faces:['top','bottom'],connectionsToggle:true,schematic:'02_MCU'};
  await page.goto(base+'/3d.html');await page.waitForFunction(()=>window.boardReady||window.boardError,null,{timeout:60000});
  const state=await page.evaluate(()=>({ready:window.boardReady,error:window.boardError,bounds:window.boardBounds,status:document.querySelector('#status').textContent,routing:document.querySelector('#routing-status').textContent}));
  if(!state.ready||state.error)throw new Error('3D viewer failed: '+state.error);
  const visibleParts=await page.evaluate(refs=>{
   const f2=window.boardScene.getObjectByName('F2');
   let hasBrakeFuseMesh=false;
   f2?.traverse(node=>{if(node.isMesh)hasBrakeFuseMesh=true;});
   return {hasBrakeFuseMesh,unexpectedBodies:refs.filter(ref=>window.boardScene.getObjectByName(ref))};
  },['F1',...Object.keys(wireTerminations)]);
  if(!visibleParts.hasBrakeFuseMesh || visibleParts.unexpectedBodies.length)throw new Error('3D fuse/wire termination mismatch: '+JSON.stringify(visibleParts));
  if(Math.abs(state.bounds.max[0]-state.bounds.min[0]-112)>.01)throw new Error('3D width is not 112 mm');
  await page.screenshot({path:'output/board-3d-angle.png'});
  await page.click('#mount');
  await page.waitForFunction(()=>window.motorEnvelope.visible);
  await page.screenshot({path:'output/board-3d-motor.png'});
  await page.click('#explode');
  await page.waitForFunction(()=>window.motorEnvelope.position.y===-25);
  await page.screenshot({path:'output/board-3d-separated.png'});
  await page.click('#explode');
  await page.waitForFunction(()=>window.motorEnvelope.position.y===0);
  await page.click('#mount');
  await page.waitForFunction(()=>!window.motorEnvelope.visible);
  for(const mode of ['top','bottom']){await page.click('#'+mode);await page.waitForTimeout(250);await page.screenshot({path:'output/board-3d-'+mode+'.png'});}
  report.threeDimensional={passed:true,...state,...visibleParts,views:['angle','top','bottom','motor','separated'],motorControls:true,modelSha256:createHash('sha256').update(fs.readFileSync('output/space-octopus.glb')).digest('hex')};
 }finally{await browser.close()}
 report.pageErrors=errors;report.passed=errors.length===0;fs.writeFileSync('output/browser-audit.json',JSON.stringify(report,null,2)+'\n');fs.writeFileSync('output/3d-browser-check.json',JSON.stringify(report.threeDimensional,null,2)+'\n');
 console.log(JSON.stringify(report,null,2));if(errors.length)process.exitCode=1;
})().catch(e=>{console.error(e);process.exitCode=1});
