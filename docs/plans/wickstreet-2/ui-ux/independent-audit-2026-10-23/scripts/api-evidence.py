"""Read-only independent API evidence. No workspace endpoints or financial implementation imports."""
import concurrent.futures as futures
import json
from pathlib import Path
import time
import urllib.request
import urllib.parse
import urllib.error

ROOT = Path(__file__).resolve().parents[1] / 'evidence' / 'api'
ROOT.mkdir(exist_ok=True)
BASE = 'http://localhost:8000/api/v1/mf'
GROUP = {'category':'Equity Scheme - Flexi Cap Fund','plan':'direct','option':'growth'}
GATES = [{'field':'status','op':'in','value':['active']},{'field':'plan','op':'in','value':['direct']},{'field':'option','op':'in','value':['growth']}]
tasks = [('fields','/screener/fields',None),('presets','/screener/presets',None),('regimes','/regimes',None),('risk-free','/risk-free',None),('frontier','/peers/frontier?'+urllib.parse.urlencode(GROUP),None),('transitions','/peers/transitions?'+urllib.parse.urlencode(GROUP),None),('compare','/compare?code=122639&code=118955&code=120166',None),('backtest','/backtests',{**GROUP,'signal':'cagr_3y','top':5})]
for code in ['122639','118955','120166']:
 for part in ['','metrics','score','confidence','navs','annual','rolling?window=1y','rolling?window=3y','drawdowns','underwater','rank-history','regimes','direct-regular','near-duplicates']:
  tasks.append((code+'-'+(part or 'detail').replace('?window=','-'),f'/funds/{code}'+('/'+part if part else ''),None))
for q in ['parag','ppfas','sbi smallcap','axis bluechip','elss','hdfc flexicap','quant small cap','icici bluechip','nippon india','122639','INF879O01027','parag parik','Parag Parikh Flexi Cap']:
 tasks.append(('search-'+q.replace(' ','-'),'/funds?'+urllib.parse.urlencode({'q':q,'limit':8}),None))
for kind in ['sip','lumpsum','swp','stp']:
 body={'code':'122639','amount':10000 if kind=='sip' else 100000 if kind=='lumpsum' else 1000000 if kind=='swp' else 500000,'start':'2021-10-01','end':'2026-10-23','day':1,'tax_class':'equity'}
 if kind in ['swp','stp']:body['instalment']=6000 if kind=='swp' else 10000
 if kind=='stp':body['target']='118955'
 tasks.append(('calculate-'+kind,'/calculators/'+kind,body))
tasks += [('spark','/funds/sparklines?code=122639&code=118955',None),('rolling-sip','/funds/122639/rolling-sip?tenor=3y&amount=10000',None)]
for name,fil in [('gates',{'all':GATES}),('default',{'all':GATES+[{'field':'category','op':'in','value':[GROUP['category']]}]}),('gates-any',{'all':GATES+[{'any':[{'field':'cagr_3y','op':'>','value':.15},{'field':'sharpe_3y','op':'>','value':.8}]}]})]:
 tasks.append(('screen-'+name,'/screener/run',{'filter':fil,'sort':[{'field':'score','dir':'desc'}],'columns':['category','status','plan','option','cagr_3y','score','cagr_3y_cat_pct','cagr_3y_cat_median'],'page':{'size':50}}))
def get(t):
 name,url,body=t;t0=time.monotonic()
 try:
  req=urllib.request.Request(BASE+url,data=json.dumps(body).encode() if body else None,headers={'Content-Type':'application/json'})
  with urllib.request.urlopen(req,timeout=180) as res: status=res.status; payload=json.load(res)
 except urllib.error.HTTPError as e: status=e.code;payload=json.loads(e.read())
 except Exception as e: status=0;payload={'error':str(e)}
 out={'path':url,'request':body,'status':status,'elapsed_ms':round((time.monotonic()-t0)*1000),'response':payload}
 (ROOT/(name+'.json')).write_text(json.dumps(out,indent=2))
 print(name,status,out['elapsed_ms'],flush=True)
 return {'name':name,'path':url,'status':status,'elapsed_ms':out['elapsed_ms']}
with futures.ThreadPoolExecutor(max_workers=3) as ex: results=list(ex.map(get,tasks))
(ROOT/'index.json').write_text(json.dumps(results,indent=2))
