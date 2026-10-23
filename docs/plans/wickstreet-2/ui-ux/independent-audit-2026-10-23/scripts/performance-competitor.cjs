const {chromium}=require('../../../../../../web/node_modules/playwright');
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const root=path.resolve(__dirname,'..');
async function main(){const browser=await chromium.launch();const measurements=[];
 for(const base of ['http://localhost:8000','http://localhost:8767']) {
  const req=await browser.newContext();const res=await req.request.get(base+'/mf');const html=await res.text();const script=html.match(/src="(\/assets\/index-[^"]+\.js)"/)[1];const js=await (await req.request.get(base+script)).body();
  measurements.push({type:'build-identity',base,script,sha256:crypto.createHash('sha256').update(js).digest('hex'),bytes:js.length});fs.writeFileSync(path.join(root,'evidence','html-'+new URL(base).port+'.html'),html);await req.close();
  for(const profile of ['desktop','mobile-slow4g'])for(const route of ['/mf','/mf/funds/122639','/mf/simulate']) {
   const c=await browser.newContext({viewport:profile==='desktop'?{width:1440,height:1000}:{width:390,height:844},isMobile:profile!=='desktop',hasTouch:profile!=='desktop',reducedMotion:'reduce'});
   await c.route('**/api/v1/mf/workspace/records**',r=>r.fulfill({status:200,contentType:'application/json',body:'[]'}));
   await c.addInitScript(()=>{window.__vitals={lcp:0,cls:0,longTasks:[]};for(const type of ['largest-contentful-paint','layout-shift','longtask'])try{new PerformanceObserver(l=>{for(const e of l.getEntries()){if(type==='largest-contentful-paint')window.__vitals.lcp=e.startTime;if(type==='layout-shift'&&!e.hadRecentInput)window.__vitals.cls+=e.value;if(type==='longtask')window.__vitals.longTasks.push(e.duration)}}).observe({type,buffered:true})}catch{}});
   const p=await c.newPage(),cdp=await c.newCDPSession(p);await cdp.send('Network.enable');await cdp.send('Network.setCacheDisabled',{cacheDisabled:true});
   if(profile!=='desktop'){await cdp.send('Emulation.setCPUThrottlingRate',{rate:4});await cdp.send('Network.emulateNetworkConditions',{offline:false,latency:150,downloadThroughput:200000,uploadThroughput:93750});}
   const t=Date.now();await p.goto(base+route);await p.waitForLoadState('networkidle');await p.waitForTimeout(300);
   const d=await p.evaluate(()=>({vitals:window.__vitals,requests:performance.getEntriesByType('resource').length,jsBytes:performance.getEntriesByType('resource').filter(r=>r.name.endsWith('.js')).reduce((s,r)=>s+r.decodedBodySize,0),transferBytes:performance.getEntriesByType('resource').reduce((s,r)=>s+r.transferSize,0),resources:performance.getEntriesByType('resource').map(r=>({name:r.name,duration:r.duration,transferSize:r.transferSize,decoded:r.decodedBodySize}))}));
   measurements.push({type:'cold-lab',base,route,profile,totalMs:Date.now()-t,...d});console.log(base,profile,route,Date.now()-t,d.vitals.lcp);
   await p.screenshot({path:path.join(root,'screens','perf-'+new URL(base).port+'-'+profile+'-'+route.split('/').filter(Boolean).join('-')+'.png')});await c.close();
  }
 }
 fs.writeFileSync(path.join(root,'evidence','performance-builds.json'),JSON.stringify(measurements,null,2));
 const competitor=[];
 for(const profile of ['desktop','mobile']) {
  const c=await browser.newContext({viewport:profile==='desktop'?{width:1440,height:1000}:{width:390,height:844},hasTouch:profile==='mobile',isMobile:profile==='mobile'});const p=await c.newPage();
  for(const [name,url]of [['fund','https://www.tickertape.in/mutualfunds/parag-parikh-flexi-cap-fund-M_PARO'],['screen','https://www.tickertape.in/screener/mutual-fund'],['collections','https://www.tickertape.in/screener/home/mutual-fund?switch=true']])try{
   await p.goto(url,{waitUntil:'domcontentloaded',timeout:30000});await p.waitForTimeout(2000);await p.screenshot({path:path.join(root,'screens','tickertape-'+profile+'-'+name+'.png'),fullPage:true});
   await p.screenshot({path:path.join(root,'screens','tickertape-'+profile+'-'+name+'-viewport.png')});
   const body=await p.locator('body').innerText();fs.writeFileSync(path.join(root,'evidence','tickertape-'+profile+'-'+name+'.txt'),body);competitor.push({profile,name,url,status:'captured',title:await p.title()});console.log('competitor',profile,name);
  }catch(e){competitor.push({profile,name,url,error:String(e)});console.log('competitor error',String(e))}
  await c.close();
 }
 fs.writeFileSync(path.join(root,'evidence','competitor-captures.json'),JSON.stringify(competitor,null,2));await browser.close();
}
main().catch(e=>{console.error(e);process.exitCode=1});
