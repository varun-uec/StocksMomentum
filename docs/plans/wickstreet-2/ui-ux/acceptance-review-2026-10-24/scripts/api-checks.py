"""Focused read-only acceptance probes. No workspace calls or product imports."""
import hashlib
import json
import urllib.request
import urllib.error
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = 'http://localhost:8000'
results = {}

def read(name, path, body=None):
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode() if body else None,
                                 headers={'Content-Type': 'application/json', 'Accept-Encoding': 'gzip'})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read()
            if r.headers.get('Content-Encoding') == 'gzip':
                import gzip
                raw = gzip.decompress(raw)
            data = json.loads(raw)
            status = r.status
    except urllib.error.HTTPError as e:
        status, data = e.code, json.loads(e.read())
    results[name] = {'path': path, 'request': body, 'status': status, 'response': data}
    return data

html = urllib.request.urlopen(BASE + '/mf').read().decode()
import re
entry = re.search(r'src="(/assets/index-[^"]+\.js)"', html)[1]
req = urllib.request.Request(BASE + entry, headers={'Accept-Encoding': 'gzip, br'})
with urllib.request.urlopen(req) as r:
    raw = r.read()
    results['artifact'] = {'entry': entry, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest(),
                           'headers': dict(r.headers)}
for q in ['nippon india', 'hdfc', 'sbi', '144891', 'uti nifty 50 index', 'international equity']:
    read('search-' + q, '/api/v1/mf/funds?' + urllib.parse.urlencode({'q':q, 'limit':8}))

template = {'code':'122639','amount':1000000,'start':'2023-07-24','tax_class':'equity'}
for end in ['2024-07-22','2024-07-23','2024-07-24','2024-07-25']:
    data = read('equity-' + end, '/api/v1/mf/calculators/lumpsum', {**template,'end':end})
    gain = data['summary']['gain']
    expected = max(0, gain - 125000) * .125 * 1.04 if end > '2024-07-24' else gain * (.15 if end < '2024-07-23' else .2) * 1.04
    results['equity-' + end]['independent_expected_tax'] = expected
    results['equity-' + end]['tax_agrees'] = abs(data['tax']['total'] - expected) < .01
for code in ['118987','119517']:
    read('fund-' + code, '/api/v1/mf/funds/' + code)
    read('default-tax-' + code, '/api/v1/mf/calculators/sip', {'code':code,'amount':10000,'day':1,'start':'2021-10-01','end':'2026-10-24','slab_rate':.3})
overseas = read('overseas-tax-boundary', '/api/v1/mf/calculators/lumpsum', {'code':'119517','amount':1000000,'start':'2023-07-24','end':'2024-07-25','slab_rate':.3})
results['overseas-tax-boundary']['independent_expected_tax'] = overseas['summary']['gain'] * .3 * 1.04
read('overseas-tax-explicit-other', '/api/v1/mf/calculators/lumpsum', {'code':'119517','amount':1000000,'start':'2023-07-24','end':'2024-07-25','slab_rate':.3,'tax_class':'other'})
index_code = results['search-uti nifty 50 index']['response']['funds'][0]['amfi_code']
read('ambiguous-tax', '/api/v1/mf/calculators/lumpsum', {'code':index_code,'amount':100000,'start':'2021-10-01','end':'2026-10-22','slab_rate':.3})

navs = read('navs', '/api/v1/mf/funds/122639/navs')['navs']
peak = 0
trough = (None, 0)
for n in navs:
    if n['nav'] is None or n['anomaly']: continue
    nav = float(n['nav'])
    peak = max(peak, nav)
    dd = nav/peak-1
    if dd < trough[1]: trough = (n['date'],dd)
uw = read('underwater', '/api/v1/mf/funds/122639/underwater')
results['independent-drawdown'] = {'raw_nav_trough':trough, 'api_trough':min(uw['series'],key=lambda x:x[1]), 'valid_nav_count':sum(n['nav'] is not None and not n['anomaly'] for n in navs)}
# Keep compact summaries; existing audits already preserve whole historical payloads.
results['navs']['response'] = {'rows':len(navs), 'data_revision':results['navs']['response']['data_revision']}
results['underwater']['response'] = {k:v for k,v in uw.items() if k != 'series'}
read('replay-current', '/api/v1/mf/calculators/lumpsum', {**template,'end':'2024-07-24','data_revision':2801})
read('replay-missing', '/api/v1/mf/calculators/lumpsum', {**template,'end':'2024-07-24','data_revision':1})

gates = [{'field':'status','op':'in','value':['active']},{'field':'plan','op':'in','value':['direct']},{'field':'option','op':'in','value':['growth']}]
cols = ['status','plan','option','cagr_3y','vol_3y']
def screen(name, f):
    return read(name, '/api/v1/mf/screener/run', {'filter':f,'sort':[{'field':'cagr_3y','dir':'desc'}], 'columns':cols,'page':{'size':100}})
a = {'field':'cagr_3y','op':'>','value':.15}
b = {'field':'vol_3y','op':'<','value':.12}
screened = screen('nested-any', {'all':[*gates, {'any':[a,b]}]})
checks = []
for row in screened['rows']:
    v = row['values']
    a, b = v.get('cagr_3y'), v.get('vol_3y')
    checks.append(v['status'] == 'active' and v['plan'] == 'direct' and v['option'] == 'growth'
                  and ((isinstance(a, (int,float)) and a > .15) or (isinstance(b, (int,float)) and b < .12)))
results['nested-any']['independent_predicate_check'] = {'returned_rows':len(checks),'matched_all_rows':all(checks),'total_matched':screened['matched'],'scope':'first 100 rows only; not a new all-field audit'}
ROOT.joinpath('evidence/api-checks.json').write_text(json.dumps(results,indent=2))
print(json.dumps({'artifact':results['artifact'],'tax':{k:v['tax_agrees'] for k,v in results.items() if 'tax_agrees' in v},'drawdown':results['independent-drawdown'],'default_tax':{c:results['default-tax-'+c]['response']['tax'] for c in ['118987','119517']}},indent=2))
