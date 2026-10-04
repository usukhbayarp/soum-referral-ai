"""Predeclared matched control/smoke comparison: four old dev inputs, <=8 calls."""
import argparse, asyncio, hashlib, json, time
from pathlib import Path
import httpx
from scripts.medication_experiment import ROOT,request,load_cases,validate_envelope,validate_output
OUT=ROOT/'evaluation/clinician-partial-v08'


async def run(plan_path):
    plan=json.loads(plan_path.read_text());path=OUT/'matched-comparison.json'
    if path.exists():raise FileExistsError(path)
    cases=load_cases();assert [c['case_id'] for c in cases]==plan['case_ids']
    models=plan['models'];assert len(models)==2 and 'pipeline-test' in models[1]['tag']
    result={'plan':plan,'runs':[],'finished':False,'clinical_quality_claim':None}
    def save():path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    async with httpx.AsyncClient(base_url='http://127.0.0.1:11434',trust_env=False,timeout=60) as client:
        tags={m['name']:m['digest'] for m in (await client.get('/api/tags')).json()['models']}
        assert all(tags.get(m['tag'])==m['digest'] for m in models)
        for m in models:
            show=(await client.post('/api/show',json={'model':m['tag']})).json()
            assert hashlib.sha256(show['template'].encode()).hexdigest()==plan['serving_template_sha256']
        for case in cases:
            for model in models:
                req,mapping=request('A',case['source_note'],2);req['model']=model['tag'];wire=client.build_request('POST','/api/chat',json=req)
                row={'case_id':case['case_id'],'model':model,'source_mapping':mapping,'request':req,'serialized_request':wire.content.decode()};start=time.monotonic()
                try:
                    async with asyncio.timeout(60):
                        resp=await client.send(wire);row['raw_response']=resp.text;resp.raise_for_status();row['response']=resp.json();row['validation']=validate_output('A',validate_envelope(row['response']),mapping)
                except (TimeoutError,httpx.TimeoutException):
                    row['error']='timeout';row['residency_after_timeout']=(await client.get('/api/ps')).json();result['stop_reason']='Timeout: no further heavyweight work until stopped/idle verified'
                except (ValueError,httpx.HTTPError) as exc:row['error']=type(exc).__name__
                row['wall_seconds']=time.monotonic()-start;row['empty_selections']=all(v=='other' for v in row['validation']['output'].values()) if row.get('validation') else None;result['runs'].append(row);save()
                if row.get('error')=='timeout':return
    result['agreements']=[]
    for case in cases:
        left,right=[r for r in result['runs'] if r['case_id']==case['case_id']]
        a,b=left.get('validation',{}).get('output'),right.get('validation',{}).get('output')
        result['agreements'].append({'case_id':case['case_id'],'exact_agreement':a==b if a and b else None,'differences':{u:[a[u],b[u]] for u in a if a[u]!=b[u]} if a and b else None})
    result['finished']=True;save()


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('plan',type=Path);a=p.parse_args();asyncio.run(run(a.plan))
