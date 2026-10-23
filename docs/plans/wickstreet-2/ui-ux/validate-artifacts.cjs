/* Validate local documentation artefacts. No application or database writes. */
const fs = require('fs');
const path = require('path');
const { pathToFileURL } = require('url');
const { chromium } = require(path.resolve(__dirname, '../../../../web/node_modules/@playwright/test'));
const root=__dirname, wire=path.join(root,'wireframes'), evidence=path.join(root,'evidence');
(async()=>{
 const browser=await chromium.launch({headless:true});
 const page=await browser.newPage({viewport:{width:1440,height:1050}});
 const failures=[], external=[];page.on('pageerror',e=>failures.push('pageerror: '+e.message));page.on('request',r=>{if(/^https?:/.test(r.url()))external.push(r.url())});
 const url=pathToFileURL(path.join(wire,'index.html')).href;
 await page.goto(url);await page.locator('#artboard').evaluate(img=>img.decode());
 await page.locator('#screens button').nth(1).focus();await page.keyboard.press('Enter');if(await page.locator('#screens button').nth(1).getAttribute('aria-pressed')!=='true')failures.push('keyboard navigation failed');
 const checks=[];
 for(let i=0;i<10;i++){
  await page.locator('#screens button').nth(i).click();
  for(const device of ['desktop','mobile']){
   await page.locator('#'+device).click();await page.locator('#artboard').evaluate(img=>img.decode());
   const state=await page.evaluate(()=>({loaded:document.querySelector('#artboard').naturalWidth>0,device:document.querySelector('#mobile').getAttribute('aria-pressed'),hash:location.hash}));
   if(!state.loaded)failures.push('image not loaded '+i+' '+device);
   checks.push({screen:i+1,device,loaded:state.loaded});
  }
 }
 await page.locator('#toggle').click();if(!await page.locator('#notes').isHidden())failures.push('notes did not hide');await page.locator('#toggle').click();
 await page.goto(url+'#fund/desktop');await page.locator('#artboard').evaluate(img=>img.decode());
 await page.screenshot({path:path.join(evidence,'gallery-desktop.png'),fullPage:true});
 await page.setViewportSize({width:390,height:844});await page.goto(url+'#fund/mobile');await page.locator('#artboard').evaluate(img=>img.decode());
 if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth))failures.push('gallery page overflows at 390');
 await page.screenshot({path:path.join(evidence,'gallery-mobile.png'),fullPage:true});
 for(const width of [320,768,1024,1440]){await page.setViewportSize({width,height:900});if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth))failures.push('gallery overflow '+width)}
 const axePath=path.resolve(__dirname,'../../../../web/node_modules/axe-core/axe.min.js');
 await page.addScriptTag({path:axePath});const axe=await page.evaluate(async()=>{const r=await window.axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21a','wcag21aa']}});return r.violations.map(x=>({id:x.id,impact:x.impact,nodes:x.nodes.map(n=>n.target)}))});if(axe.length)failures.push({axe});
 const svgFiles=[...fs.readdirSync(wire).filter(f=>f.endsWith('.svg')).map(f=>path.join(wire,f)),...fs.readdirSync(path.join(root,'flows')).filter(f=>f.endsWith('.svg')).map(f=>path.join(root,'flows',f))];
 fs.mkdirSync('/tmp/wickstreet-wireframe-previews',{recursive:true});const bounds=[];
 for(const f of svgFiles){
  await page.goto(pathToFileURL(f).href);const size=await page.locator('svg').first().evaluate(s=>({w:s.viewBox.baseVal.width,h:s.viewBox.baseVal.height}));
  await page.setViewportSize({width:Math.ceil(size.w),height:Math.ceil(size.h)});
  const outside=await page.locator('svg').first().evaluate(s=>{const v=s.viewBox.baseVal;return Array.from(s.querySelectorAll('text')).filter(t=>{const b=t.getBBox();return b.x<0||b.y<0||b.x+b.width>v.width+1||b.y+b.height>v.height+1}).map(t=>t.textContent)});
  // Contact sheet embeds transformed artboards, whose local BBoxes use their own viewBox.
  if(!f.endsWith('contact-sheet.svg')&&outside.length)failures.push({file:path.basename(f),outside});
  bounds.push({file:path.basename(f),outside:outside.length});
  await page.screenshot({path:'/tmp/wickstreet-wireframe-previews/'+path.basename(f,'.svg')+'.png'});
 }
 if(external.length)failures.push({external});
 await browser.close();const result={date:'2026-10-23',checks,svgCount:svgFiles.length,bounds,externalRequests:external.length,axeViolations:axe,failures};
 fs.writeFileSync(path.join(evidence,'artifact-checks.json'),JSON.stringify(result,null,2)+'\n');console.log(JSON.stringify({screenDeviceChecks:checks.length,svgCount:svgFiles.length,axe,externalRequests:external.length,failures},null,2));if(failures.length)process.exitCode=1;
})().catch(e=>{console.error(e);process.exitCode=1});
