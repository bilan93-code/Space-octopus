const fs=require('fs');const path=require('path');const {chromium}=require('playwright');
(async()=>{
 const sheets=fs.readdirSync('output/schematics').filter(f=>f.endsWith('.svg')).sort();
 const html='<!doctype html><html><style>@page{size:A3 landscape;margin:8mm}body{margin:0}.page{height:280mm;break-after:page;display:flex;align-items:center;justify-content:center}.page:last-child{break-after:auto}img{max-width:100%;max-height:100%}</style>'+sheets.map(f=>'<section class="page"><img src="data:image/svg+xml;base64,'+fs.readFileSync('output/schematics/'+f).toString('base64')+'"></section>').join('');
 const browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||'/usr/bin/chromium',headless:true,args:['--no-sandbox','--disable-dev-shm-usage']});
 try{const page=await browser.newPage();await page.setContent(html);await page.evaluate(()=>Promise.all([...document.images].map(img=>img.decode())));await page.pdf({path:'output/Space_Octopus_RevA_Schematics.pdf',printBackground:true,preferCSSPageSize:true});
 const outline=fs.readFileSync('output/mechanical-outline.svg').toString('base64');await page.setContent('<style>@page{size:A4 portrait;margin:8mm}body{margin:0}img{width:100%;height:278mm;object-fit:contain}</style><img src="data:image/svg+xml;base64,'+outline+'">');await page.evaluate(()=>document.images[0].decode());await page.pdf({path:'output/Motor112_PCB_Interface.pdf',printBackground:true,preferCSSPageSize:true});
 const mount=fs.readFileSync('output/motor-mounting-concept.svg').toString('base64');await page.setContent('<style>@page{size:A4 landscape;margin:8mm}body{margin:0}img{width:100%;height:190mm;object-fit:contain}</style><img src="data:image/svg+xml;base64,'+mount+'">');await page.evaluate(()=>document.images[0].decode());await page.pdf({path:'output/Motor112_Mounting_Concept.pdf',printBackground:true,preferCSSPageSize:true});
 }finally{await browser.close()}
 console.log(`Exported ${sheets.length} tscircuit schematic sheets to PDF.`);
})().catch(e=>{console.error(e);process.exitCode=1});
