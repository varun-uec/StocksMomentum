const {chromium}=require('../../../../../../web/node_modules/playwright');
const fs=require('node:fs'),path=require('node:path');
const root=path.resolve(__dirname,'..');
const results=[];
const record=(kind,id,name,body)=>({id,kind,name,body,schema_version:1,version:1,created_at:'2026-10-23T10:00:00Z',updated_at:'2026-10-23T10:00:00Z',archived:false});
async function main(){
const browser=await chromium.launch();
async function context(records=[],options={}){
 const c=await browser.newContext({viewport:{width:1440,height:1000},reducedMotion:'reduce'});let requests=[];
 await c.route('**/api/v1/mf/workspace/records**',async route=>{
  const req=route.request(),u=new URL(req.url()),id=u.pathname.split('/records/')[1];requests.push({method:req.method(),url:req.url(),body:req.postData()});
  const json=(status,body)=>route.fulfill({status,contentType:'application/json',body:JSON.stringify(body)});
  if(req.method()==='GET')return json(200,id?records.find(r=>r.id===id):records.filter(r=>(!u.searchParams.get('kind')||r.kind===u.searchParams.get('kind'))&&r.archived===(u.searchParams.get('archived')==='true')));
  if(options.failWrites)return json(503,{detail:'Isolated audit: simulated save failure'});
  if(req.method()==='POST'){const b=req.postDataJSON(),r=record(b.kind,'new-record',b.name,b.body);records.unshift(r);return json(201,r)}
  const r=records.find(r=>r.id===id);if(!r)return json(404,{detail:'Missing'});
  if(options.conflictRename&&req.method()==='PUT'){r.name='ZZ-AUDIT-other-window';r.version++;return json(412,{detail:'The record is at version '+r.version})}
  if(req.headers()['if-match']!==`"${r.version}"`)return json(412,{detail:'Version conflict'});
  Object.assign(r,req.postDataJSON(),{version:r.version+1});return json(200,r);
 });
 return {c,p:await c.newPage(),requests,records};
}
async function save(p,name){await p.screenshot({path:path.join(root,'screens','probe-'+name+'.png'),fullPage:true});fs.writeFileSync(path.join(root,'evidence','probe-'+name+'.txt'),await p.locator('body').innerText())}
async function probe(name,fn){try{await fn();console.log('done',name)}catch(e){results.push({name,error:String(e)});console.log('error',name,String(e))}fs.writeFileSync(path.join(root,'evidence','interactions.json'),JSON.stringify(results,null,2))}
for(const port of [8000,8767])await probe('served-fixes-'+port,async()=>{
 const {c,p}=await context();let seen=[];p.on('request',r=>{if(r.url().endsWith('/screener/run'))seen.push(r.postDataJSON())});
 await p.goto(`http://localhost:${port}/mf/screen`);await p.waitForLoadState('networkidle');
 const before=(await p.locator('main').innerText()).match(/[\d,]+ funds/)[0];
 await p.getByRole('radio',{name:'Match any'}).click();await p.waitForLoadState('networkidle');const after=(await p.locator('main').innerText()).match(/[\d,]+ funds/)[0];
 await save(p,'match-any-'+port);results.push({name:'Match any '+port,before,after,request:seen.at(-1)});
 await p.goto(`http://localhost:${port}/mf`);await p.waitForLoadState('networkidle');await p.keyboard.press('/');await p.keyboard.type('parag');await p.waitForTimeout(1200);
 results.push({name:'keyboard search '+port,active:await p.evaluate(()=>document.activeElement?.outerHTML),options:await p.getByRole('option').allTextContents()});await save(p,'search-'+port);
 await c.close();
});
await probe('scenario-replay',async()=>{
 const r=record('scenario','00000000-0000-4000-8000-000000000001','ZZ-AUDIT-scenario',{kind:'sip',request:{code:'122639',amount:25000,day:15,start:'2019-04-15',end:'2025-10-15',step_up:.1,tax_class:'equity'},summary:{invested:1000000,value:1500000,gain:500000,xirr:.15}});
 const {c,p}=await context([r]);await p.goto('http://localhost:8767/mf/workspace?tab=scenarios');await p.waitForLoadState('networkidle');await save(p,'scenario-saved');
 await p.getByRole('link',{name:'Open in the lab'}).click();await p.waitForLoadState('networkidle');await save(p,'scenario-replayed');
 const values=await p.locator('main input').evaluateAll(ns=>ns.map(n=>({type:n.type,value:n.value})));
 results.push({name:'scenario replay',saved:r.body.request,url:p.url(),values});await c.close();
});
await probe('search-pending',async()=>{
 const {c,p}=await context();await p.route('**/api/v1/mf/funds?q=sbi*',async route=>{await new Promise(r=>setTimeout(r,2000));await route.continue()});
 await p.goto('http://localhost:8767/mf');await p.getByRole('combobox',{name:'Search funds',exact:true}).fill('parag');await p.waitForTimeout(850);
 await p.getByRole('combobox',{name:'Search funds',exact:true}).fill('sbi smallcap');await p.waitForTimeout(600);await save(p,'stale-search');
 const options=await p.getByRole('option').allTextContents();await p.keyboard.press('Enter');await p.waitForTimeout(300);results.push({name:'stale search selection',query:'sbi smallcap',shown:options,selectedUrl:p.url()});await c.close();
});
await probe('workspace-unsaved-and-errors',async()=>{
 const a=record('note','00000000-0000-4000-8000-000000000002','ZZ-AUDIT-note-A',{text:'Saved A'}),b=record('note','00000000-0000-4000-8000-000000000003','ZZ-AUDIT-note-B',{text:'Saved B'});
 const {c,p}=await context([a,b]);await p.goto('http://localhost:8767/mf/workspace?tab=notes');await p.waitForLoadState('networkidle');await p.getByRole('textbox',{name:'Note',exact:true}).fill('UNSAVED AUDIT DRAFT');
 await p.getByRole('button',{name:/ZZ-AUDIT-note-B/}).click();await p.getByRole('button',{name:/ZZ-AUDIT-note-A/}).click();
 results.push({name:'unsaved note switch',value:await p.getByRole('textbox',{name:'Note',exact:true}).inputValue()});await save(p,'note-draft-switch');await c.close();
 const w=record('watchlist','00000000-0000-4000-8000-000000000004','ZZ-AUDIT-watchlist',{codes:['122639']});
 const x=await context([w],{failWrites:true});await x.p.goto('http://localhost:8767/mf/workspace');await x.p.waitForLoadState('networkidle');await x.p.getByRole('button',{name:/Remove Parag/}).click();await x.p.waitForTimeout(600);await save(x.p,'watchlist-save-failure');results.push({name:'watchlist failed save',alerts:await x.p.getByRole('alert').allTextContents(),body:await x.p.locator('main').innerText()});await x.c.close();
});
await probe('rename-conflict',async()=>{
 const r=record('note','00000000-0000-4000-8000-000000000005','ZZ-AUDIT-original',{text:'Saved text'});const {c,p}=await context([r],{conflictRename:true});
 await p.goto('http://localhost:8767/mf/workspace?tab=notes');await p.waitForLoadState('networkidle');await p.getByRole('textbox',{name:'Name',exact:true}).fill('ZZ-AUDIT-my-important-new-name');await p.getByRole('button',{name:'Rename',exact:true}).click();await p.waitForTimeout(650);await save(p,'rename-conflict');results.push({name:'rename conflict',nameValue:await p.getByRole('textbox',{name:'Name',exact:true}).inputValue(),alerts:await p.getByRole('alert').allTextContents()});await c.close();
});
await probe('zoom-and-dimensions',async()=>{
 const {c,p}=await context();await p.goto('http://localhost:8767/mf/funds/122639');await p.waitForLoadState('networkidle');
 const chart=p.getByRole('figure',{name:'Growth of ₹10,000 chart',exact:true});const travellers=chart.locator('.recharts-brush-traveller');let before=await travellers.first().getAttribute('aria-valuenow');await travellers.first().focus();await p.keyboard.press('ArrowRight');await p.keyboard.press('ArrowRight');await p.waitForTimeout(100);let after=await travellers.first().getAttribute('aria-valuenow');
 results.push({name:'brush keyboard',before,after,aria:await travellers.first().getAttribute('aria-label')});await save(p,'brush-keyboard');await p.getByRole('button',{name:'Log',exact:true}).click().catch(()=>{});await save(p,'growth-log');
 for(const width of [320,390,768,1280]){await p.setViewportSize({width,height:width<500?844:1000});await p.goto('http://localhost:8767/mf/screen');await p.waitForLoadState('networkidle');await p.getByRole('button',{name:/Filters/}).first().click().catch(()=>{});await save(p,'filters-'+width)}await c.close();
});
await probe('tax-ui',async()=>{
 const {c,p}=await context();await p.goto('http://localhost:8767/mf/simulate?kind=lumpsum&code=122639');await p.waitForLoadState('networkidle');await p.getByRole('spinbutton',{name:'Initial investment (₹)',exact:true}).fill('1000000');await p.getByLabel('Start',{exact:true}).fill('2023-07-24');await p.getByLabel('End',{exact:true}).fill('2024-07-24');await p.waitForTimeout(850);await save(p,'tax-12m-anniversary');await c.close();
});
await browser.close();fs.writeFileSync(path.join(root,'evidence','interactions.json'),JSON.stringify(results,null,2));
}
main().catch(e=>{console.error(e);process.exitCode=1});
