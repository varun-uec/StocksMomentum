const {chromium}=require('../../../../../../web/node_modules/playwright');
const fs=require('node:fs'),path=require('node:path');const root=path.resolve(__dirname,'..');let out=[];
async function main(){const b=await chromium.launch();
async function open(base,route,extra={}){const c=await b.newContext({viewport:{width:1440,height:1000},reducedMotion:'reduce',...extra});await c.route('**/api/v1/mf/workspace/records**',r=>r.fulfill({status:200,contentType:'application/json',body:'[]'}));const p=await c.newPage();p.setDefaultTimeout(5000);await p.goto(base+route);await p.waitForLoadState('networkidle');return{c,p}}
async function shot(p,name){await p.screenshot({path:path.join(root,'screens','probe2-'+name+'.png'),fullPage:true})}
for(const port of [8000,8767]){
 const base='http://localhost:'+port;
 const {c,p}=await open(base,'/mf/screen');let requests=[];p.on('request',r=>{if(r.url().endsWith('/screener/run'))requests.push(r.postDataJSON())});
 await p.getByRole('radio',{name:'Match any'}).click();await p.waitForTimeout(700);out.push({name:'Match any '+port,request:requests.at(-1),text:(await p.locator('main').innerText()).slice(0,1000)});await shot(p,'match-any-'+port);await c.close();
 for(const route of ['studio','compare','simulate']){const {c,p}=await open(base,'/mf/'+route);out.push({name:'first use '+port+'/'+route,charts:await p.locator('.recharts-wrapper').count(),body:(await p.locator('main').innerText()).slice(0,650)});await shot(p,'first-'+port+'-'+route);await c.close()}
}
{
 const {c,p}=await open('http://localhost:8767','/mf/simulate?kind=lumpsum&code=122639');await p.locator('main input[type=number]').first().fill('1000000');await p.locator('main input[type=date]').nth(0).fill('2023-07-24');await p.locator('main input[type=date]').nth(1).fill('2024-07-24');await p.waitForTimeout(1200);await shot(p,'tax-boundary');out.push({name:'tax UI',body:await p.locator('main').innerText()});await c.close();
}
{
 const {c,p}=await open('http://localhost:8767','/mf/compare?code=122639&code=118955');await p.getByRole('button',{name:'Show data table'}).first().click();await shot(p,'compare-table-units');out.push({name:'compare units',table:await p.locator('table').first().innerText()});await c.close();
}
{
 const {c,p}=await open('http://localhost:8767','/mf/studio?mode=regimes&code=122639');
 const data=await p.evaluate(()=>{const chart=document.querySelector('[aria-label="Proxy level with regime windows"]');const line=chart.querySelector('.recharts-cartesian-grid-horizontal line');return {grid:{x1:+line.getAttribute('x1'),x2:+line.getAttribute('x2')},bands:[...chart.querySelectorAll('.mf-band path')].map(n=>({bbox:(()=>{const r=n.getBBox();return{x:r.x,y:r.y,width:r.width,height:r.height}})(),fill:n.getAttribute('fill')})),ticks:[...chart.querySelectorAll('.recharts-xAxis .recharts-cartesian-axis-tick-value')].map(n=>n.textContent)}});
 const api=await(await p.request.get('http://localhost:8000/api/v1/mf/regimes')).json();const first=Date.parse(api.proxy.levels[0][0]),last=Date.parse(api.proxy.levels.at(-1)[0]);
 data.edges=api.windows.map((w,i)=>{const rect=data.bands[i]?.bbox,expectedX=data.grid.x1+(Date.parse(w.start)-first)/(last-first)*(data.grid.x2-data.grid.x1);return{window:w.start,bbox:rect,expectedX,errorDays:rect?(rect.x-expectedX)/(data.grid.x2-data.grid.x1)*(last-first)/864e5:null}});
 out.push({name:'regime geometry',...data});await c.close();
}
{
 const {c,p}=await open('http://localhost:8767','/mf/funds/122639?tab=risk');const chart=p.getByRole('img',{name:'Drawdown from peak over time'});await chart.scrollIntoViewIfNeeded();
 const raw=await(await p.request.get('http://localhost:8000/api/v1/mf/funds/122639/underwater')).json();const thin=(a,n)=>a.length<=n?a:a.filter((_,i)=>i%Math.ceil(a.length/n)===0||i===a.length-1);const display=thin(thin(raw.series,800),700),table=thin(thin(raw.series,800),150);const min=a=>a.reduce((a,b)=>b[1]<a[1]?b:a);
 const box=await chart.boundingBox();const first=Date.parse(display[0][0]),last=Date.parse(display.at(-1)[0]),low=min(display);const x=box.x+58+(Date.parse(low[0])-first)/(last-first)*(box.width-66);await p.mouse.move(x,box.y+130);await p.waitForTimeout(200);await shot(p,'drawdown-omitted-trough');out.push({name:'risk omitted trough',fullMinimum:min(raw.series),displayMinimum:low,tableMinimum:min(table),tooltip:await p.locator('.recharts-tooltip-wrapper').allTextContents()});await c.close();
}
{
 const {c,p}=await open('http://localhost:8767','/mf/funds/122639');await p.locator('input[type=checkbox]').filter({hasText:'___'}).count();const checkbox=p.getByRole('checkbox',{name:'Log scale'});await checkbox.check();await shot(p,'log-scale');
 const brush=p.locator('.recharts-brush-traveller').first();const before=await brush.getAttribute('aria-valuenow');await brush.focus();await p.keyboard.press('ArrowRight');const after=await brush.getAttribute('aria-valuenow');out.push({name:'zoom keyboard and log',before,after,aria:await brush.getAttribute('aria-label'),logChecked:await checkbox.isChecked()});await c.close();
}
{
 const {c,p}=await open('http://localhost:8767','/mf',{viewport:{width:390,height:844},isMobile:true,hasTouch:true});await p.getByRole('button',{name:'Search funds',exact:true}).click();const search=p.getByRole('combobox',{name:'Search funds',exact:true});await search.fill('nippon india');await p.waitForTimeout(950);await shot(p,'mobile-nippon-search');out.push({name:'nippon search mobile',options:await p.getByRole('option').allTextContents()});await c.close();
}
await b.close();fs.writeFileSync(path.join(root,'evidence','followup.json'),JSON.stringify(out,null,2));}
main().catch(e=>{console.error(e);fs.writeFileSync(path.join(root,'evidence','followup.json'),JSON.stringify(out,null,2));process.exitCode=1});
