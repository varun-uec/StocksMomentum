// Matched, top-of-page screenshots. Empty workspace responses; no personal records.
const {chromium}=require(process.cwd()+'/node_modules/playwright');
const path=require('node:path');
const root=path.resolve(__dirname,'..');
(async()=>{
 const b=await chromium.launch();
 for(const [name,url,viewport] of [
  ['d-discover','/mf',{width:1440,height:1000}],
  ['d-fund-overview','/mf/funds/122639',{width:1440,height:1000}],
  ['d-screener','/mf/screen',{width:1440,height:1000}],
  ['d-compare','/mf/compare?code=122639&code=118955&code=120166',{width:1440,height:1000}],
  ['d-overseas-tax','/mf/simulate?kind=lumpsum&code=119517&amount=1000000&start=2023-07-24&end=2024-07-25&slab=30',{width:1440,height:1000}],
  ['d-frontier','/mf/studio?mode=frontier&code=122639',{width:1440,height:1000}],
  ['d-monsoon-light','/mf/funds/122639?tab=risk',{width:1440,height:1000}],
  ['d-monsoon-dark','/mf/funds/122639?tab=risk',{width:1440,height:1000}],
  ['d-nested','/mf/screen?v='+Buffer.from(JSON.stringify({v:1,mode:'all',conditions:[{field:'status',op:'in',value:['active']},{field:'plan',op:'in',value:['direct']},{field:'option',op:'in',value:['growth']},{any:[{field:'cagr_3y',op:'>',value:.15},{field:'vol_3y',op:'<',value:.12}]}],sort:[{field:'cagr_3y',dir:'desc'}],columns:['cagr_3y','vol_3y'],formulas:{}})).toString('base64url'),{width:1440,height:1000}]
 ]){
  const c=await b.newContext({viewport,reducedMotion:'reduce'});
  if(name.startsWith('d-monsoon'))await c.addInitScript(mode=>{localStorage.setItem('mf-palette','monsoon');localStorage.setItem('m25-theme',mode)},name.endsWith('dark')?'dark':'light');
  await c.route('**/api/v1/mf/workspace/records**',r=>r.fulfill({status:200,contentType:'application/json',body:'[]'}));
  const p=await c.newPage();await p.goto('http://localhost:8000'+url);await p.waitForLoadState('networkidle');await p.evaluate(()=>scrollTo(0,0));
  await p.screenshot({path:path.join(root,'screens',name+'.png')});await c.close();
 }
 await b.close();
})().catch(e=>{console.error(e);process.exit(1)});
