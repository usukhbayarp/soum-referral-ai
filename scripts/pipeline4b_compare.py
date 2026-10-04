"""Predeclared 3-model x 4-case A-v2 comparison, maximum 12 requests, no retries.
Timeout with unproven idleness aborts all remaining heavy work.
"""
import argparse,asyncio,json,time
from pathlib import Path
import httpx
from scripts.medication_experiment import request,load_cases,validate_envelope,validate_output,ROOT

async def run(pins_path,output):
 pins=json.loads(pins_path.read_text());models=pins['comparison_models']
 if len(models)!=3 or any(not m.get('digest') for m in models):raise ValueError('Pin all three actual imported digests before comparison')
 if 'pipeline-test' not in models[2]['tag']:raise ValueError('Smoke tag must remain explicitly pipeline-test')
 cases=load_cases();assert [c['case_id'] for c in cases]==['DEV-002','dev-003','dev-004','probe-med-001']
 if output.exists():raise FileExistsError(output)
 output.mkdir(parents=True);report={'purpose':'engineering-only, unreviewed development','max_requests':12,'runs':[],'finished':False}
 def save():(output/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
 async with httpx.AsyncClient(base_url='http://127.0.0.1:11434',trust_env=False,timeout=60) as c:
  tags={m['name']:m['digest'] for m in (await c.get('/api/tags')).json()['models']}
  if any(tags.get(m['tag'])!=m['digest'] for m in models):raise ValueError('Tag identity changed')
  for case in cases:
   for model in models:
    req,mapping=request('A',case['source_note'],2);req['model']=model['tag'];wire=c.build_request('POST','/api/chat',json=req)
    row={'case_id':case['case_id'],'model':model,'request':req,'serialized_request':wire.content.decode(),'source_mapping':mapping};start=time.monotonic()
    try:
     async with asyncio.timeout(60):
      response=await c.send(wire);row['raw_response']=response.text;response.raise_for_status();row['response']=response.json();row['validation']=validate_output('A',validate_envelope(row['response']),mapping)
    except (TimeoutError,httpx.TimeoutException) as exc:
     row['error']='timeout';row['wall_seconds']=time.monotonic()-start;row['residency_after_timeout']=(await c.get('/api/ps')).json();row['idle_proven']=not row['residency_after_timeout'].get('models');report['runs'].append(row);report['stop_reason']='Timeout: stop rather than assume a resident model is idle';save();return
    except (ValueError,httpx.HTTPError) as exc:row['error']=type(exc).__name__
    row['wall_seconds']=time.monotonic()-start;report['runs'].append(row);save()
 report['agreements']=[]
 for case in cases:
  runs=[r for r in report['runs'] if r['case_id']==case['case_id']]
  for left,right in [(0,1),(1,2)]:
   a,b=runs[left].get('validation'),runs[right].get('validation')
   report['agreements'].append({'case_id':case['case_id'],'pair':[models[left]['tag'],models[right]['tag']],'exact_output_agreement':a['output']==b['output'] if a and b else None,'changed_roles':{k:[a['output'][k],b['output'][k]] for k in a['output'] if a['output'][k]!=b['output'][k]} if a and b else None,'clinical_correctness':'not inferred from agreement'})
 report['finished']=True;save()

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--pins',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();asyncio.run(run(a.pins,a.output))
