"""Bounded, frozen fictional diagnostic only; never changes application settings.

Run with --stage control|candidate|hypothesis|full. Each stage is single-use.
The plan contains all requests before inference; output files journal before send.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import threading
import time
import httpx
from app.treatment_picker import resolve

OUT = Path('evaluation/picker-diagnostics-v1')

def score(content, units, positive, negative):
    ids = [s['unit']['id'] for s in resolve(content, units)]
    return {'selected': ids, 'retrieved': sorted(set(ids) & set(positive)),
            'missing': sorted(set(positive) - set(ids)),
            'extra': sorted(set(ids) & set(negative)),
            'unreviewed': sorted(set(ids) - set(positive) - set(negative)),
            'exact': set(ids) == set(positive), 'empty': not ids}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', required=True, choices=['control','candidate','hypothesis','full'])
    args = parser.parse_args()
    plan_path = OUT / ({'control':'plan.json', 'candidate':'candidate-llama-plan.json'}.get(args.stage, args.stage+'-plan.json'))
    plan = json.loads(plan_path.read_text())
    jobs = plan['jobs'][args.stage]
    assert len(jobs) <= (9 if args.stage in ('control','candidate') else 3)
    # A partial/failed stage also cannot be repeated. Count attempted jobs, not successes.
    destination = OUT / (args.stage+'-runs.json')
    with destination.open('x') as f: f.write('[]\n')
    existing = sum(len(json.loads(p.read_text())) for p in OUT.glob('*-runs.json'))
    if existing + len(jobs) > 24: raise RuntimeError('24-request budget exceeded')
    rows = []
    with httpx.Client(base_url='http://127.0.0.1:11434', timeout=120, trust_env=False) as client:
        if client.get('/api/ps').json()['models']: raise RuntimeError('Runtime already loaded; inspect ownership first')
        tags = client.get('/api/tags').json()['models']
        model = jobs[0]['request']['model']
        tag = next(x for x in tags if x['name'] == model)
        pin = OUT / (args.stage+'-identity.json')
        metadata = client.post('/api/show', json={'model':model}).json()
        metadata.pop('modelfile',None)
        pin.write_text(json.dumps({'tag':tag,'show':metadata},ensure_ascii=False,indent=2)+'\n')
        if args.stage == 'candidate':
            assert tag['digest'] == plan['model_digest']
        if args.stage == 'control':
            assert tag['digest'] == 'a7949c7fd19f24caf6f062c16c5733fa72c5c8049a53ec34681ccc426b6eb5f6'
        for job in jobs:
            request = client.build_request('POST','/api/chat',json=job['request'])
            row = {'id':job['id'],'case_id':job['case_id'],'condition':job['condition'],
                   'model_digest':tag['digest'],'plan_sha256':hashlib.sha256(plan_path.read_bytes()).hexdigest(),
                   'wire_request_utf8':request.content.decode(), 'status':'attempted', 'telemetry':[]}
            rows.append(row)
            def save(): destination.write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
            save()
            stop = threading.Event()
            def sample():
                with httpx.Client(base_url='http://127.0.0.1:11434',timeout=3,trust_env=False) as probe:
                    while not stop.wait(0.5):
                        try:
                            row['telemetry'].append({'seconds':round(time.monotonic()-start,3),
                                'ps':probe.get('/api/ps').json(),
                                'pressure_level':subprocess.check_output(['sysctl','-n','kern.memorystatus_vm_pressure_level'],text=True).strip()})
                        except Exception as e: row['telemetry'].append({'sampling_error':type(e).__name__})
            start = time.monotonic(); thread = threading.Thread(target=sample,daemon=True);thread.start()
            try:
                response = client.send(request);row['raw_response']=response.text;row['http_status']=response.status_code
                response.raise_for_status();data=response.json();row['status']='received'
                row['complete']=data.get('done') is True and data.get('done_reason')=='stop'
                row['thinking_present']=bool(data.get('message',{}).get('thinking'))
                content=data['message']['content']
                row['tokens']={k:data.get(k) for k in ('prompt_eval_count','eval_count')}
                if job['condition'] != 'C':
                    try:
                        row['score']=score(content,job['units'],job['positive'],job['negative'])
                        row['valid']=row['complete'] and not row['thinking_present']
                    except Exception as e: row.update(valid=False,validation_error=str(e),unscorable_positive=job['positive'])
                else: row['semantic_review']='pending; assess against frozen rubric; JSON validity not applicable'
            except Exception as e:
                row.update(status='error',error=repr(e));raise
            finally:
                row['wall_seconds']=time.monotonic()-start;stop.set();thread.join();save()
            print(job['id'],round(row['wall_seconds'],2),data['message']['content'],flush=True)
            # keep_alive=0 unloads after a completed call; never start another on uncertainty.
            deadline=time.monotonic()+30
            while client.get('/api/ps').json()['models']:
                if time.monotonic()>deadline: raise RuntimeError('Model still loaded; stop and inspect before any further call')
                time.sleep(0.25)

if __name__ == '__main__': main()
