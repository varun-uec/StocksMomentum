"""Real HTTP application and PostgreSQL, exclusively on the dedicated *_test database."""
import concurrent.futures, json
from pathlib import Path
from fastapi.testclient import TestClient
from wickstreet.app import create_app
from wickstreet.config import WickstreetSettings
OUT=Path(__file__).resolve().parents[1]/'evidence/workspace-concurrency.json'
settings=WickstreetSettings(database_url='postgresql+asyncpg://wickstreet_app:wickstreet_app@127.0.0.1:65479/momentum25_test',migration_database_url='postgresql+asyncpg://wickstreet_owner:wickstreet_owner@127.0.0.1:65479/momentum25_test')
result={}
with TestClient(create_app(settings),base_url='http://localhost') as client:
 r=client.post('/workspace/records',json={'kind':'note','name':'ZZ-INDEPENDENT-AUDIT-concurrency','body':{'text':'original'}});result['create']=r.status_code;r.raise_for_status();record=r.json();url='/workspace/records/'+record['id']
 result['without_if_match']=client.put(url,json={'name':record['name'],'body':{'text':'invalid'}}).status_code
 def update(i):return client.put(url,json={'name':record['name'],'body':{'text':'writer '+str(i)}},headers={'If-Match':'"1"'}).status_code
 with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool: result['parallel_statuses']=list(pool.map(update,range(6)))
 final=client.get(url).json();result['final_version']=final['version'];result['final_body']=final['body']
 result['malformed_if_match']=client.put(url,json={'name':record['name'],'body':{}},headers={'If-Match':'nonsense'}).status_code
with TestClient(create_app(settings),base_url='http://localhost') as reopened:
 read=reopened.get(url);result['new_app_instance_read']=read.status_code;result['persisted_after_new_lifespan']=read.json()['body']==result['final_body'] and read.json()['version']==2
 result['archive']=reopened.put(url,json={'name':record['name'],'body':final['body'],'archived':True},headers={'If-Match':'"2"'}).status_code
OUT.write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
