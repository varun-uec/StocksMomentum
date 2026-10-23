const { chromium } = require('../../../../../../web/node_modules/playwright');
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '..', process.env.AUDIT_VARIANT || '.');
for (const dir of ['screens','evidence']) fs.mkdirSync(path.join(root,dir), {recursive:true});
const host = process.env.AUDIT_BASE || 'http://localhost:8000';
const routes = [
 ['discover','/mf'], ['screen','/mf/screen'], ['screen-consistent','/mf/screen?preset=consistent_large_cap'],
 ...['overview','performance','risk','peers','holdings','profile'].map(t=>['fund-'+t, '/mf/funds/122639?tab='+t]),
 ...['rolling','drawdown','ranks','frontier','transitions','regimes','backtest'].map(t=>['studio-'+t,'/mf/studio?mode='+t+'&code=122639']),
 ['compare','/mf/compare?code=122639&code=120503&code=120841'],
 ...['sip','lumpsum','swp','stp'].map(t=>['lab-'+t,'/mf/simulate?kind='+t+'&code=122639']),
 ['workspace','/mf/workspace'],['workspace-notes','/mf/workspace?tab=notes'],['workspace-screens','/mf/workspace?tab=screens'],['workspace-scenarios','/mf/workspace?tab=scenarios'],['alerts','/mf/workspace?tab=alerts'],
 ['portfolio','/mf/portfolio'],['ask','/mf/ask']
];
const result = {host, capturedAt:new Date().toISOString(), measurements:[], errors:[], blockedWrites:[]};
async function installIsolation(ctx) {
 await ctx.route('**/api/v1/mf/workspace/records**', async route => {
  const req=route.request();
  if(req.method()==='GET') return route.fulfill({status:200,contentType:'application/json',body:'[]'});
  result.blockedWrites.push({method:req.method(),url:req.url()});
  return route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({detail:'Independent audit blocks real workspace writes'})});
 });
}
async function main() {
 const browser = await chromium.launch({headless:true});
 const ctx = await browser.newContext({viewport:{width:1440,height:1000},timezoneId:'Asia/Kolkata',reducedMotion:'reduce'});
 await installIsolation(ctx);
 await ctx.addInitScript(()=>{
  localStorage.setItem('m25-theme','light'); localStorage.setItem('mf-palette','paper');
  window.__auditVitals={lcp:0,cls:0,longTasks:[]};
  try{new PerformanceObserver(l=>{for(const e of l.getEntries())window.__auditVitals.lcp=e.startTime}).observe({type:'largest-contentful-paint',buffered:true});}catch{}
  try{new PerformanceObserver(l=>{for(const e of l.getEntries())if(!e.hadRecentInput)window.__auditVitals.cls+=e.value}).observe({type:'layout-shift',buffered:true});}catch{}
  try{new PerformanceObserver(l=>{for(const e of l.getEntries())window.__auditVitals.longTasks.push(e.duration)}).observe({type:'longtask',buffered:true});}catch{}
 });
 const page=await ctx.newPage();
 page.on('pageerror',e=>result.errors.push({route:page.url(),type:'pageerror',message:e.message}));
 page.on('console',m=>{if(m.type()==='error'||m.type()==='warning')result.errors.push({route:page.url(),type:m.type(),message:m.text()})});
 page.on('response',r=>{if(r.status()>=400)result.errors.push({route:page.url(),type:'http',status:r.status(),url:r.url()})});
 for(const [name,url] of routes) {
  const t=Date.now(); await page.goto(host+url); await page.waitForLoadState('networkidle');
  await page.screenshot({path:path.join(root,'screens','d-'+name+'.png'),fullPage:true});
  await page.screenshot({path:path.join(root,'screens','d-'+name+'-viewport.png')});
  const data=await page.evaluate(()=>({title:document.title,text:document.querySelector('main')?.innerText,scrollWidth:document.documentElement.scrollWidth,width:innerWidth,vitals:window.__auditVitals,resources:performance.getEntriesByType('resource').map(r=>({name:r.name,duration:r.duration,transferSize:r.transferSize,decoded:r.decodedBodySize})),bands:[...document.querySelectorAll('.mf-band')].map(n=>({x:n.getAttribute('x'),width:n.getAttribute('width'),fill:n.getAttribute('fill')})),smallTargets:[...document.querySelectorAll('main button,main a,main input,main select')].map(n=>({label:n.getAttribute('aria-label')||n.innerText,rect:n.getBoundingClientRect().toJSON()})).filter(n=>n.rect.width>0&&n.rect.height>0&&Math.min(n.rect.width,n.rect.height)<44)}));
  fs.writeFileSync(path.join(root,'evidence','d-'+name+'.json'),JSON.stringify(data,null,2));
  result.measurements.push({name,url,elapsed:Date.now()-t,scrollWidth:data.scrollWidth,vitals:data.vitals});
  console.log('desktop',name,Date.now()-t);
 }
 for (const [width,height,prefix] of [[390,844,'m'],[768,1024,'t'],[320,740,'s']]) {
  await page.setViewportSize({width,height});
  for(const [name,url] of routes.filter(([n])=>width===390? !['screen-consistent','workspace-screens','workspace-scenarios','lab-lumpsum'].includes(n) : ['discover','screen','fund-overview','fund-risk','studio-regimes','compare','lab-sip','workspace'].includes(n))) {
   await page.goto(host+url); await page.waitForLoadState('networkidle');
   await page.screenshot({path:path.join(root,'screens',prefix+'-'+name+'.png'),fullPage:true});
   await page.screenshot({path:path.join(root,'screens',prefix+'-'+name+'-viewport.png')});
   const data=await page.evaluate(()=>({text:document.querySelector('main')?.innerText,width:innerWidth,scrollWidth:document.documentElement.scrollWidth,targets:[...document.querySelectorAll('button,a,input,select')].map(n=>({label:n.getAttribute('aria-label')||n.innerText,rect:n.getBoundingClientRect().toJSON()})).filter(n=>n.rect.width>0&&n.rect.height>0&&Math.min(n.rect.width,n.rect.height)<44)}));
   fs.writeFileSync(path.join(root,'evidence',prefix+'-'+name+'.json'),JSON.stringify(data,null,2));
   result.measurements.push({name:prefix+'-'+name,width,scrollWidth:data.scrollWidth});
   console.log(prefix,name,data.scrollWidth);
  }
 }
 await ctx.close();
 for(const palette of ['paper','monsoon']) for(const mode of ['light','dark']) {
  const tc=await browser.newContext({viewport:{width:1440,height:1000},reducedMotion:'reduce'}); await installIsolation(tc);
  await tc.addInitScript(({palette,mode})=>{localStorage.setItem('m25-theme',mode);localStorage.setItem('mf-palette',palette)}, {palette,mode});
  const p=await tc.newPage();
  await p.addInitScript({path:path.resolve(__dirname,'../../../../../../web/node_modules/axe-core/axe.min.js')});
  for(const [name,url] of routes.filter(([n])=>['discover','screen','fund-overview','fund-risk','studio-regimes','compare','lab-sip','workspace','ask','portfolio'].includes(n))) {
   await p.goto(host+url);await p.waitForLoadState('networkidle');
   await p.screenshot({path:path.join(root,'screens',palette+'-'+mode+'-'+name+'.png'),fullPage:true});
   const axe=await p.evaluate(async()=>{const r=await axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21a','wcag21aa','wcag22aa']}});return {violations:r.violations,incomplete:r.incomplete.map(i=>({id:i.id,nodes:i.nodes.length}))}});
   fs.writeFileSync(path.join(root,'evidence',palette+'-'+mode+'-'+name+'-axe.json'),JSON.stringify(axe,null,2));
   console.log('theme',palette,mode,name,axe.violations.map(v=>v.id).join(','));
  }
  await tc.close();
 }
 fs.writeFileSync(path.join(root,'evidence','capture-summary.json'),JSON.stringify(result,null,2));
 await browser.close();
}
main().catch(e=>{console.error(e);fs.writeFileSync(path.join(root,'evidence','capture-summary.json'),JSON.stringify(result,null,2));process.exitCode=1});
