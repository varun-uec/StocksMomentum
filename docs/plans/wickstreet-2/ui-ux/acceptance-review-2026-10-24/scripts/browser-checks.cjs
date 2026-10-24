// Focused acceptance evidence; writes only artifacts and isolated in-memory records.
const {chromium}=require(process.cwd()+'/node_modules/playwright');
const fs=require('node:fs'), path=require('node:path'), assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..'), base='http://localhost:8000';
const results={screens:[],checks:[],performance:[]};
const shot=async(p,name)=>{await p.screenshot({path:path.join(root,'screens',name+'.png')});results.screens.push({name,url:p.url(),viewport:p.viewportSize()});};
async function isolated(browser,options={}) {
 const c=await browser.newContext({viewport:{width:1440,height:1000},reducedMotion:'reduce',...options});
 c.setDefaultTimeout(15000);
 const records=[];
 await c.route('**/api/v1/mf/workspace/records**', async r=>{
  const req=r.request(), id=new URL(req.url()).pathname.split('/records/')[1];
  let body,status=200;
  if(req.method()==='GET')body=id?records.find(x=>x.id===id):records.filter(x=>!new URL(req.url()).searchParams.get('kind')||x.kind===new URL(req.url()).searchParams.get('kind'));
  else if(req.method()==='POST'){body={...req.postDataJSON(),id:'00000000-0000-4000-8000-'+String(records.length+1).padStart(12,'0'),version:1,schema_version:1,archived:false,created_at:'2026-10-24T00:00:00Z',updated_at:'2026-10-24T00:00:00Z'};records.push(body);status=201;}
  else throw Error('Unexpected mock mutation '+req.method());
  await r.fulfill({status,contentType:'application/json',body:JSON.stringify(body)});
 });
 return {c,records};
}
async function main(){
 const browser=await chromium.launch();
 // Independent save -> navigate away -> replay for every calculator kind.
 const {c,records}=await isolated(browser), p=await c.newPage();
 const scenarios=[
  ['sip',{code:'122639',amount:25000,day:15,start:'2019-04-15',end:'2025-10-15',step_up:.1,tax_class:'equity'}],
  ['lumpsum',{code:'122639',amount:250000,start:'2021-02-01',end:'2025-10-15',tax_class:'equity'}],
  ['swp',{code:'118987',amount:1500000,instalment:7500,day:7,start:'2020-01-01',end:'2025-10-15',tax_class:'debt',slab_rate:.2}],
  ['stp',{code:'118987',target:'122639',amount:600000,instalment:12500,day:3,start:'2021-02-01',end:'2025-10-15',tax_class:'debt',slab_rate:.3}]
 ];
 for(const [kind,req] of scenarios){
  const params=new URLSearchParams({kind,...req,tax:req.tax_class,slab:(req.slab_rate??.3)*100,step_up:(req.step_up??0)*100});
  const first=p.waitForResponse(r=>r.url().includes('/calculators/'+kind)&&r.status()===200);
  await p.goto(base+'/mf/simulate?'+params); await first;
  const save=p.getByRole('button',{name:'Save scenario',exact:true}); await save.waitFor(); await save.click();
  await p.getByRole('button',{name:'Saved to your workspace'}).waitFor();
  const rec=records.at(-1); assert.deepEqual(rec.body.request,req);
  await p.goto(base+'/mf/workspace?tab=scenarios');
  await p.getByRole('button',{name:new RegExp('^'+(kind==='lumpsum'?'Lump sum':kind.toUpperCase())+' ·')}).first().click();
  const replay=p.waitForRequest(r=>r.url().includes('/calculators/'+kind));
  await p.getByRole('link',{name:'Replay on that snapshot'}).click();
  const replayBody=(await replay).postDataJSON(); assert.deepEqual(replayBody,{...req,data_revision:rec.body.provenance.data_revision});
  results.checks.push({name:'save-replay-'+kind,saved:rec.body.request,replayed:replayBody,provenance:rec.body.provenance,pass:true});
 }
 // Chart truth: table carries trough and every displayed comparison value is in rupees.
 await p.goto(base+'/mf/funds/122639?tab=risk');
 await p.getByText('Deepest −31.2% · 24 Mar 2020',{exact:true}).waitFor(); await shot(p,'d-risk');
 await p.goto(base+'/mf/compare?code=122639&code=118955&code=120166');
 const growth=p.getByRole('region',{name:/^Growth of ₹10,000/});
 await growth.getByRole('button',{name:'Show data table'}).click();
 const moneyRows=await growth.locator('tbody tr').allTextContents(); assert(moneyRows.length>10&&moneyRows.every(r=>r.includes('₹')));
 results.checks.push({name:'compare-table-currency',rows:moneyRows.length,first:moneyRows[0],last:moneyRows.at(-1),pass:true});
 await growth.getByRole('button',{name:'Show chart',exact:true}).click();
 // Check continuity: selecting 1Y does not enter URL, survives neither reload nor Lab.
 await p.getByRole('radio',{name:'1Y',exact:true}).click();
 const periodURL=p.url(); await p.reload();
 results.checks.push({name:'compare-period-reload',selected:'1Y',url:periodURL,afterReload:await p.getByRole('radio',{name:'All',exact:true}).getAttribute('aria-checked')});
 await shot(p,'d-compare');
 await p.goto(base+'/mf'); await p.getByRole('heading',{name:'Ideas to research'}).waitFor(); await shot(p,'d-discover');
 await p.goto(base+'/mf/funds/122639'); await p.waitForLoadState('networkidle'); await shot(p,'d-fund-overview');
 await p.goto(base+'/mf/screen'); await p.getByRole('table').first().waitFor(); await shot(p,'d-screener');
 await p.goto(base+'/mf/simulate?kind=lumpsum&code=119517&amount=1000000&start=2023-07-24&end=2024-07-25&slab=30');
 await p.getByRole('region',{name:'Tax estimate'}).waitFor(); await shot(p,'d-overseas-tax');
 results.checks.push({name:'overseas-tax-browser',text:await p.getByRole('region',{name:'Tax estimate'}).innerText()});
 // Essential responsive and palette captures; existing baseline images are referenced, not copied.
 await c.close();
 for(const [name,opts,route] of [
  ['m-fund-overview',{viewport:{width:390,height:844},isMobile:true,hasTouch:true},'/mf/funds/122639'],
  ['m-risk',{viewport:{width:390,height:844},isMobile:true,hasTouch:true},'/mf/funds/122639?tab=risk'],
  ['m-lab',{viewport:{width:390,height:844},isMobile:true,hasTouch:true},'/mf/simulate?code=118987'],
  ['m-screen',{viewport:{width:390,height:844},isMobile:true,hasTouch:true},'/mf/screen'],
  ['t-fund',{viewport:{width:768,height:1024}},'/mf/funds/122639'],
  ['narrow-risk',{viewport:{width:320,height:740},isMobile:true,hasTouch:true},'/mf/funds/122639?tab=risk'],
  ['d-compare-dark',{},'/mf/compare?code=122639&code=118955&code=120166']
 ]){
  const {c}=await isolated(browser,opts);if(name.endsWith('dark'))await c.addInitScript(()=>localStorage.setItem('m25-theme','dark'));
  const p=await c.newPage();await p.goto(base+route);await p.waitForLoadState('networkidle');await shot(p,name);
  results.checks.push({name:'layout-'+name,overflow:await p.evaluate(()=>document.documentElement.scrollWidth-innerWidth)});await c.close();
 }
 // Repeatable cold measurements against the delivered server: 3 samples per key route.
 for(const route of ['/mf','/mf/funds/122639','/mf/simulate?code=118987'])for(let run=1;run<=3;run++){
  const {c}=await isolated(browser,{viewport:{width:390,height:844},isMobile:true,hasTouch:true});
  await c.addInitScript(()=>{
   window.acceptanceVitals={lcp:0,cls:0,longTasks:[]};
   for(const type of ['largest-contentful-paint','layout-shift','longtask'])new PerformanceObserver(list=>{for(const e of list.getEntries()){
    if(type==='largest-contentful-paint')window.acceptanceVitals.lcp=e.startTime;
    if(type==='layout-shift'&&!e.hadRecentInput)window.acceptanceVitals.cls+=e.value;
    if(type==='longtask')window.acceptanceVitals.longTasks.push(e.duration);
   }}).observe({type,buffered:true});
  });
  const p=await c.newPage(),cdp=await c.newCDPSession(p);await cdp.send('Network.enable');await cdp.send('Network.setCacheDisabled',{cacheDisabled:true});
  await cdp.send('Emulation.setCPUThrottlingRate',{rate:4});await cdp.send('Network.emulateNetworkConditions',{offline:false,latency:150,downloadThroughput:200000,uploadThroughput:93750});
  await p.goto(base+route);await p.waitForLoadState('networkidle');await p.waitForTimeout(300);
  const perf=await p.evaluate(()=>({vitals:window.acceptanceVitals,jsBytes:performance.getEntriesByType('resource').filter(r=>new URL(r.name).pathname.endsWith('.js')).reduce((s,r)=>s+r.decodedBodySize,0),transferBytes:performance.getEntriesByType('resource').reduce((s,r)=>s+r.transferSize,0),js:performance.getEntriesByType('resource').filter(r=>new URL(r.name).pathname.endsWith('.js')).map(r=>({url:new URL(r.name).pathname,decoded:r.decodedBodySize,encoded:r.encodedBodySize,duration:r.duration}))}));
  results.performance.push({route,run,profile:'390x844, 4x CPU, 150ms latency, 200000 B/s download, cold cache',...perf});
  console.log(route,run,JSON.stringify(perf.vitals));await c.close();
 }
 await browser.close();fs.writeFileSync(path.join(root,'evidence/browser-checks.json'),JSON.stringify(results,null,2));
}
main().catch(e=>{fs.writeFileSync(path.join(root,'evidence/browser-checks.json'),JSON.stringify({...results,error:String(e)},null,2));console.error(e);process.exit(1)});
