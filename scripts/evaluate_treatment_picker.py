"""One frozen treatment-picker attempt per three partial reviewed development inputs."""
import asyncio,hashlib,json,time
from pathlib import Path
from app.treatment_picker import CONTRACT,DIRECTORY,build_request,suggest
from app.core import ExtractionError
OUT=Path('evaluation/treatment-picker-v1')
async def main():
    if (OUT/'plan.json').exists():raise FileExistsError('No retries/sweep in this experiment')
    annotations=json.loads(Path('evaluation/clinician-partial-v08/annotations.json').read_text())['cases'][:3]
    cases=[]
    for c in annotations:
        relevant=[int(x[1:]) for x in c['reviewed_form_categories'].get('treatment_source',[])]
        irrelevant=[int(x[1:]) for x in c['reviewed_A_v2_labels'] if int(x[1:]) not in relevant]
        req,units=build_request(c['source_note']);assert hashlib.sha256(c['source_note'].encode()).hexdigest()==c['source_sha256']
        cases.append({'case_id':c['case_id'],'source_note':c['source_note'],'source_sha256':c['source_sha256'],'reviewed_relevant':relevant,'reviewed_irrelevant':irrelevant,'request':req,'units':units})
    plan={'contract':CONTRACT,'hashes':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in DIRECTORY.iterdir()},'request_budget':3,'attempts_per_case':1,'cases':cases,'metrics':'Reviewed relevant retrieved/missed; reviewed irrelevant selected; all other selected units unreviewed. Context displayed separately, not counted as selected. Invalid/empty/timeouts retained.','limitation':'Partial labels; DEV004 has no reviewed treatment positives and no approved home-use clarification in original. Zero known positives does not mean no treatment.'}
    (OUT/'plan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2)+'\n');runs=[]
    for c in cases:
        capture={};start=time.monotonic();row={'case_id':c['case_id']}
        try:
            result=await suggest(c['source_note'],capture);row['result']=result;ids=[s['unit']['id'] for s in result['suggestions']];row.update(retrieved=sorted(set(ids)&set(c['reviewed_relevant'])),missed=sorted(set(c['reviewed_relevant'])-set(ids)),irrelevant=sorted(set(ids)&set(c['reviewed_irrelevant'])),unreviewed=sorted(set(ids)-set(c['reviewed_relevant'])-set(c['reviewed_irrelevant'])),empty=not ids)
        except ExtractionError as e:row.update(error=e.code,unscorable_relevant=c['reviewed_relevant'])
        row.update(capture=capture,wall_seconds=time.monotonic()-start);runs.append(row);(OUT/'results.json').write_text(json.dumps(runs,ensure_ascii=False,indent=2)+'\n')
        if row.get('error')=='inference_timeout':break
if __name__=='__main__':asyncio.run(main())
