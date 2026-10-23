"""Independent checks from raw API responses; imports no Wickstreet implementation."""
from bisect import bisect_left, bisect_right
from calendar import monthrange
from datetime import date
import json, math, statistics
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]/'evidence'
API=ROOT/'api'
def response(name): return json.loads((API/(name+'.json')).read_text())['response']
def ordinal(s):return date.fromisoformat(s).toordinal()
def back(d,months):
 dt=date.fromordinal(d); y,m=divmod(dt.year*12+dt.month-1-months,12);m+=1
 return date(y,m,min(dt.day,monthrange(y,m)[1])).toordinal()
def navs(code):return [(ordinal(n['date']),float(n['nav'])) for n in response(code+'-navs')['navs'] if float(n['nav'])>0]
checks=[]
def check(name,actual,expected,atol=1e-9):
 err=abs(actual-expected) if actual is not None and expected is not None else None
 checks.append(dict(name=name,actual=actual,expected=expected,absolute_error=err,pass_=err is not None and err<=atol))
rf=response('risk-free')['points'];rfd=[ordinal(d) for d,_ in rf];rfv=[v for _,v in rf]
def rf_growth(start,end):
 value=1.
 for d in range(start,end):value*=1+rfv[bisect_right(rfd,d)-1]/100/365
 return value-1
for code in ['122639','118955','120166']:
 series=navs(code); ds,ns=map(list,zip(*series)); metrics=response(code+'-metrics');v=metrics['values'];end=ds[-1]
 for field,months,annual in [('ret_1m',1,False),('ret_3m',3,False),('ret_6m',6,False),('ret_1y',12,False),('cagr_3y',36,True),('cagr_5y',60,True),('cagr_10y',120,True)]:
  k=bisect_right(ds,back(end,months))-1
  if k>=0:check(code+' '+field,v[field],(ns[-1]/ns[k])**(365.25/(end-ds[k]) if annual else 1)-1)
 k=bisect_right(ds,back(end,36))-1; returns=[ns[i]/ns[i-1]-1 for i in range(k+1,len(ns))]
 vol=statistics.stdev(returns)*math.sqrt(252);check(code+' vol_3y',v['vol_3y'],vol)
 peak=ns[k];deep=0.
 for n in ns[k:]:peak=max(peak,n);deep=min(deep,n/peak-1)
 check(code+' mdd_3y',v['mdd_3y'],deep)
 peak=max(ns);check(code+' dd_now',v['dd_now'],ns[-1]/peak-1)
 riskfree=(1+rf_growth(ds[k],end))**(365.25/(end-ds[k]))-1
 check(code+' rf_3y',v['rf_3y'],riskfree)
 check(code+' sharpe_3y',v['sharpe_3y'],(v['cagr_3y']-riskfree)/vol)
 excess_dev=math.sqrt(statistics.mean(min(r-rf_growth(ds[i-1],ds[i]),0)**2 for i,r in enumerate(returns,k+1)))*math.sqrt(252)
 check(code+' sortino_3y',v['sortino_3y'],(v['cagr_3y']-riskfree)/excess_dev)
 ordered=sorted(returns);tail=math.ceil(.05*len(ordered));check(code+' VaR95',v['var95_3y'],ordered[tail-1]);check(code+' CVaR95',v['cvar95_3y'],statistics.mean(ordered[:tail]))
 for window,months in [('1y',12),('3y',36)]:
  points=[]
  for i in range(len(ns)):
   anchor=back(ds[i],months);j=bisect_right(ds,anchor)-1
   if j>=0 and anchor-ds[j]<=7 and max((ds[z]-ds[z-1] for z in range(j+1,i+1)),default=0)<=7:
    points.append((ds[i],(ns[i]/ns[j])**(365.25/(ds[i]-ds[j]))-1))
  for stat,fn in [('min',min),('max',max),('median',statistics.median),('mean',statistics.mean),('count',len)]:
   check(code+' rolling_'+window+'_'+stat,v['rolling_'+window+'_'+stat],fn([r for _,r in points]))
  actual=response(code+'-rolling-'+window)['points']
  check(code+' rolling '+window+' endpoint length',len(actual),len(points),0)
  check(code+' rolling '+window+' max point error',max(abs(a[1]-e[1]) for a,e in zip(actual,points)),0)
 score=response(code+'-score');check(code+' score',score['score'],statistics.mean(p['category_percentile'] for p in score['parts']))
 # Direct return calculation for each regime, on the API's exact endpoint dates.
 for w in response(code+'-regimes')['windows']:
  if w['fund_return'] is None:continue
  j=bisect_right(ds,ordinal(w['start']))-1;i=bisect_right(ds,ordinal(w['end']))-1
  if j>=0:check(code+' regime '+w['start'],w['fund_return'],ns[i]/ns[j]-1)

cmp=response('compare')
for pair in cmp['correlations']:
 a=navs(pair['a']);b=navs(pair['b']);ad=dict(a);bd=dict(b);dates=sorted(ad.keys()&bd.keys())
 ar=[ad[dates[i]]/ad[dates[i-1]]-1 for i in range(1,len(dates))];br=[bd[dates[i]]/bd[dates[i-1]]-1 for i in range(1,len(dates))]
 check('correlation '+pair['a']+'/'+pair['b'],pair['correlation'],statistics.correlation(ar,br))
 check('correlation observations '+pair['a']+'/'+pair['b'],pair['observations'],len(ar),0)

ds,ns=map(list,zip(*navs('122639')));td,tn=map(list,zip(*navs('118955')))
start=ordinal('2021-10-01');finish=ordinal('2026-10-22')
sched=[]
for year in range(2021,2027):
 for month in range(1,13):
  d=date(year,month,1).toordinal()
  if start<=d<=finish:
   i=bisect_left(ds,d)
   if i<len(ds) and ds[i]<=finish:sched.append(i)
def solve(flows):
 first=flows[0][0]
 def npv(r):return sum(a/(1+r)**((d-first)/365) for d,a in flows)
 lo,hi=-.9,5
 for _ in range(180):
  m=(lo+hi)/2
  if npv(m)>0:lo=m
  else:hi=m
 return (lo+hi)/2
for kind in ['sip','lumpsum','swp','stp']:
 amount={'sip':10000,'lumpsum':100000,'swp':1000000,'stp':500000}[kind]
 flows=[];holding=0.;target=0.;withdrawn=0.;lots=[]
 if kind=='sip':
  for i in sched:
   units=amount*.99995/ns[i];holding+=units;flows.append((ds[i],-amount));lots.append((ds[i],units,amount))
 else:
  i=sched[0];holding=amount*.99995/ns[i];flows=[(ds[i],-amount)]
  if kind in ['swp','stp']:
   for i in sched[1:]:
    cash=min(6000 if kind=='swp' else 10000,holding*ns[i]);holding-=cash/ns[i]
    if kind=='swp':flows.append((ds[i],cash));withdrawn+=cash
    else:target+=cash*.99995/tn[bisect_left(td,ds[i])]
 value=holding*ns[-1]+target*tn[-1];s=response('calculate-'+kind)['summary']
 check(kind+' value',s['value'],value,1e-6);check(kind+' withdrawn',s['withdrawn'],withdrawn,1e-6)
 check(kind+' XIRR',s['xirr'],solve(flows+[(finish,value)]))
 if kind=='sip':
  gains={'short':0.,'long':0.}
  for bought,units,cost in lots:gains['long' if finish>back(bought+0, -12) else 'short']+=units*ns[-1]-cost
  st,lt=gains['short'],gains['long']
  if st<0:lt+=st;st=0
  tax=(max(st,0)*.2+max(lt-125000,0)*.125)*1.04
  check('SIP equity tax netting and cess',response('calculate-sip')['tax']['total'],tax,1e-6)

backtest=response('backtest')
for period,select in [('in_sample',lambda m:m['signal_month']<'2024-01'),('holdout',lambda m:m['signal_month']>='2024-01'),('whole',lambda m:True)]:
 rows=[m for m in backtest['months'] if select(m)];s=backtest['summary'][period]
 for strategy in ['strategy','median']:
  growth=math.prod(1+m[strategy] for m in rows)-1
  check('backtest '+period+' '+strategy+'_growth',s[strategy+'_growth'],growth)
  check('backtest '+period+' '+strategy+'_annualised',s[strategy+'_annualised'],(1+growth)**(12/len(rows))-1)

boundary=response('tax-12m-anniversary');gain=boundary['summary']['gain']
check('DEFECT: 12 calendar months equity tax',boundary['tax']['total'],gain*.2*1.04,.01)
result={'pass':sum(c['pass_'] for c in checks),'fail':sum(not c['pass_'] for c in checks),'checks':checks,'tax_boundary_understatement':gain*.2*1.04-boundary['tax']['total'],'method':'Independent standard-library calculations from saved raw NAVs and RBI yields; no application imports. Tax threshold is calendar months; other metrics follow disclosed v5 methods.'}
(ROOT/'independent-financial-results.json').write_text(json.dumps(result,indent=2))
print(json.dumps({k:v for k,v in result.items() if k!='checks'},indent=2))
for c in checks:
 if not c['pass_']:print(c)
