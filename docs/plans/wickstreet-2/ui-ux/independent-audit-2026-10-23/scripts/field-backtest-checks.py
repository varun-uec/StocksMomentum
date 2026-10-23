"""API field coverage and independent raw-NAV backtest reconstruction; no app imports."""
import json, math, statistics, urllib.request, concurrent.futures
from pathlib import Path
from bisect import bisect_right
from calendar import monthrange
from datetime import date
ROOT=Path(__file__).resolve().parents[1]/'evidence';BASE='http://localhost:8000/api/v1/mf'
def req(url,body=None):
 r=urllib.request.Request(BASE+url,data=json.dumps(body).encode() if body else None,headers={'Content-Type':'application/json'})
 with urllib.request.urlopen(r,timeout=90) as f:return json.load(f)
fields=json.loads((ROOT/'api/fields.json').read_text())['response']['fields']
def field_test(f):
 d=req('/screener/run',{'filter':{'all':[{'field':f['id'],'op':'is_available','value':None}]},'sort':[{'field':f['id'],'dir':'asc'}],'columns':[f['id']],'page':{'size':1}})
 return {'field':f['id'],'type':f['type'],'expected':f['coverage']['values'],'matched':d['matched'],'pass':d['matched']==f['coverage']['values'],'revision':d['data_revision']}
if (ROOT/'all-field-checks.json').exists(): checks=json.loads((ROOT/'all-field-checks.json').read_text())
else:
 with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool: checks=list(pool.map(field_test,fields))
(ROOT/'all-field-checks.json').write_text(json.dumps(checks,indent=2));print('fields',sum(c['pass'] for c in checks),'/',len(checks),flush=True)
group=[{'field':'category','op':'in','value':['Equity Scheme - Flexi Cap Fund']},{'field':'plan','op':'in','value':['direct']},{'field':'option','op':'in','value':['growth']}]
members=req('/screener/run',{'filter':{'all':group},'sort':[],'columns':['status','cagr_3y'],'page':{'size':50}})
(ROOT/'api/backtest-members.json').write_text(json.dumps(members,indent=2))
cache=ROOT/'backtest-navs';cache.mkdir(exist_ok=True)
def load(row):
 code=row['amfi_code'];p=cache/(code+'.json')
 if p.exists():d=json.loads(p.read_text())
 else:d=req('/funds/'+code+'/navs');p.write_text(json.dumps(d))
 points=[(date.fromisoformat(n['date']).toordinal(),float(n['nav'])) for n in d['navs'] if n['nav'] is not None and float(n['nav'])>0]
 return code,points
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:series=dict(pool.map(load,members['rows']))
def backday(day,years):
 d=date.fromordinal(day);y=d.year-years;return date(y,d.month,min(d.day,monthrange(y,d.month)[1])).toordinal()
monthnav={};signals={}
for code,points in series.items():
 if not points:continue
 ds,ns=map(list,zip(*points));monthends={}
 for i,(day,nav) in enumerate(points):
  d=date.fromordinal(day)
  if (d.year,d.month)>=(2026,10):continue
  monthends[(d.year,d.month)]=i
 for (year,month),i in monthends.items():
  last=date(year,month,monthrange(year,month)[1]).toordinal()
  if last-ds[i]>7:continue
  key=f'{year:04d}-{month:02d}';monthnav.setdefault(key,{})[code]=ns[i]
  anchor=backday(ds[i],3);j=bisect_right(ds,anchor)-1
  if j<0 or anchor-ds[j]>7 or max((ds[k]-ds[k-1] for k in range(j+1,i+1)),default=0)>7:continue
  signals.setdefault(key,{})[code]=(ns[i]/ns[j])**(365.25/(ds[i]-ds[j]))-1
api=json.loads((ROOT/'api/backtest.json').read_text())['response'];results=[]
for m in api['months']:
 key=m['signal_month'];year,month=map(int,key.split('-'));year,month=(year+1,1) if month==12 else (year,month+1)
 later=monthnav[f'{year:04d}-{month:02d}'];now=monthnav[key];available=now.keys()&later.keys()
 returns={c:later[c]/now[c]-1 for c in available};ranked=sorted(signals[key],key=lambda c:(-signals[key][c],c))[:5];picks=[c for c in ranked if c in returns]
 strat=statistics.mean(returns[c] for c in picks);median=statistics.median(returns.values())
 results.append({'month':key,'picks_match':picks==m['picks'],'strategy_error':abs(strat-m['strategy']),'median_error':abs(median-m['median']),'pass':picks==m['picks'] and abs(strat-m['strategy'])<1e-10 and abs(median-m['median'])<1e-10})
summary={'group_members':len(series),'matched':members['matched'],'months':len(results),'passed':sum(x['pass'] for x in results),'results':results}
(ROOT/'independent-backtest-results.json').write_text(json.dumps(summary,indent=2));print('backtest',summary['passed'],'/',summary['months'],'members',len(series))
for r in results:
 if not r['pass']:print(r)
