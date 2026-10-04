"""Frozen successor contract: one untuned call per reviewed development input, <=4."""
import argparse,asyncio,hashlib,json,time
from pathlib import Path
import httpx
from scripts.medfacts import ROOT,request,validate,MODEL,hashes
from scripts.medfacts_data import validated
from scripts.medication_experiment import validate_envelope
OUT=ROOT/'evaluation/medfacts-v1'


def score(output,case):
    expected=case['target']['facts'];actual=output.get('facts',[]) if output is not None else [];items=[];used=set()
    for gold in expected:
        matches=[(i,p) for i,p in enumerate(actual) if p['topic']==gold['topic'] and p['evidence']==gold['evidence']]
        forbidden=set()
        attrs=set(gold['attributes'])
        if 'regular_use' in attrs:forbidden.add('encounter_administered')
        if 'encounter_administered' in attrs:forbidden.update(['planned','not_administered'])
        if 'not_administered' in attrs:forbidden.add('encounter_administered')
        for state in ['not_asked','unknown','not_documented','not_clarified','explicit_absence']:
            if state in attrs:forbidden.update(set(['not_asked','unknown','not_documented','not_clarified','explicit_absence'])-{state})
        if gold['topic']=='investigation' and 'explicit_absence' in attrs:forbidden.add('pending_result')
        best=next(((i,p) for i,p in matches if attrs<=set(p['attributes']) and not forbidden.intersection(p['attributes'])),matches[0] if matches else None)
        if best:used.add(best[0])
        pred=best[1] if best else None
        items.append({'expected':gold,'status':'unscorable' if output is None else 'correct' if pred and attrs<=set(pred['attributes']) and not forbidden.intersection(pred['attributes']) else 'incorrect','missing_attributes':sorted(attrs-set(pred['attributes'])) if pred else sorted(attrs),'contradicted_attributes':sorted(forbidden.intersection(pred['attributes'])) if pred else [],'exact_evidence_match':bool(best),'unreviewed_extra_attributes':sorted(set(pred['attributes'])-attrs-forbidden) if pred else [],'overlapping_alternatives_require_review':[p for p in actual if p['topic']==gold['topic'] and set(e['unit_id'] for e in p['evidence']) & set(e['unit_id'] for e in gold['evidence'])] if not best else []})
    return {'denominator':len(items),'correct':sum(i['status']=='correct' for i in items),'incorrect':sum(i['status']=='incorrect' for i in items),'unscorable':sum(i['status']=='unscorable' for i in items),'items':items,'unmatched_predictions_unreviewed':[p for i,p in enumerate(actual) if i not in used],'limitation':'Exact spans/topic + explicitly reviewed positive/contradicted attributes only; unmatched facts and extra attributes are unreviewed, not automatic clinical errors; lexical evidence alone is not semantic correctness.'}


async def run(output,model=MODEL):
    _,cases=validated();assert len(cases)<=4 and all(c['split']=='development' for c in cases)
    if output.exists():raise FileExistsError(output)
    report={'contract_hashes':hashes(),'model':model,'predeclared_cases':[c['case_id'] for c in cases],'max_requests':len(cases),'runs':[],'finished':False,'training_cases_used':False}
    async with httpx.AsyncClient(base_url='http://127.0.0.1:11434',trust_env=False,timeout=120) as client:
        tags={m['name']:m['digest'] for m in (await client.get('/api/tags')).json()['models']};report['model_digest']=tags[model]
        pins=json.loads((ROOT/'evaluation/pipeline4b-smoke/imported-pins.json').read_text())
        if model==MODEL:assert tags[model]==pins['comparison_models'][1]['digest']
        show=(await client.post('/api/show',json={'model':model})).json();assert hashlib.sha256(show['template'].encode()).hexdigest()==pins['serving_template_sha256'];report['template_sha256']=pins['serving_template_sha256']
        output.write_text(json.dumps(report,indent=2)+'\n')
        for case in cases:
            req,mapping=request(case['source_note'],case['scope'],model);wire=client.build_request('POST','/api/chat',json=req);start=time.monotonic();row={'case_id':case['case_id'],'underlying_case_id':case['underlying_case_id'],'source_sha256':case['source_sha256'],'request':req,'serialized_request':wire.content.decode(),'source_mapping':mapping}
            try:
                async with asyncio.timeout(120):
                    response=await client.send(wire);row['raw_response']=response.text;response.raise_for_status();row['response']=response.json();row['validation']=validate(validate_envelope(row['response']),case['source_note'],case['scope'])
            except (TimeoutError,httpx.TimeoutException):
                row['error']='timeout';row['residency_after_timeout']=(await client.get('/api/ps')).json();report['stop_reason']='No further heavy work until stopped/idle verified'
            except (ValueError,httpx.HTTPError) as exc:row['error']=type(exc).__name__+': '+str(exc)[:120]
            row['wall_seconds']=time.monotonic()-start;value=row.get('validation',{}).get('output');row['empty']=value=={'facts':[]};row['reviewed_subset']=score(value,case);report['runs'].append(row);output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
            if row.get('error','')=='timeout':return
    report['finished']=True;output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=OUT/'untuned-baseline.json');p.add_argument('--model',default=MODEL);a=p.parse_args();asyncio.run(run(a.output,a.model))
