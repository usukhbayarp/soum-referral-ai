"""Re-score saved compatible predictions on explicit partial-review scope only."""
import json
from collections import Counter
from scripts.partial_review import OUT, validate, digest
from scripts.medication_experiment import ROOT, request, model_view


def oral(value, evidence, unit):
    """Narrow approved normalization, never a global lexical-check exemption."""
    if not isinstance(value,str) or value.casefold().strip() not in {'oral','амаар','уудаг','уусан'}:
        return False
    return any(e.get('source_unit')==unit['uid'] and e.get('quote') and e['quote'] in unit['text'] and any(w in e['quote'] for w in ['уудаг','уусан','амаар']) for e in evidence)


def compatible(run, case, candidate):
    req,m = request(candidate,case['source_note'],2)
    return run.get('source_mapping')==m and run.get('request',{}).get('messages')==req['messages'] and run.get('request',{}).get('format')==req['format']


def counts(items):
    c=Counter(x['status'] for x in items)
    return {'denominator':len(items),**{k:c[k] for k in ['correct','incorrect','unscorable']}}


def score():
    bundle=validate(json.loads((OUT/'annotations.json').read_text()));cases={r['case_id']:r for r in bundle['cases']}
    sources=[('1.7B','evaluation/medication-v1/run-v2/report.json'),('original-4B','evaluation/original4b-v07/run-v2/report.json'),('converted-control','evaluation/pipeline4b-smoke/comparison/report.json')]
    results=[];details=[]
    for label,path in sources:
        report=json.loads((ROOT/path).read_text())
        rows=[x for x in report['runs'] if (label!='converted-control' or 'control:' in x['model']['tag']) and not x.get('repeat')]
        for run in rows:
            candidate=run.get('candidate','A');case=cases[run['case_id']]
            if candidate!='A':continue
            ok=compatible(run,case,'A');pred=run.get('validation',{}).get('output',{})
            items=[]
            for u,expected in case['reviewed_A_v2_labels'].items():
                actual=pred.get(u);status='unscorable' if not ok or not isinstance(actual,str) else 'correct' if actual==expected else 'incorrect'
                items.append({'unit':u,'expected':expected,'actual':actual,'status':status})
            results.append({'model':label,'case_id':case['case_id'],'artifact':path,'artifact_sha256':digest((ROOT/path).read_text()),'source_and_frozen_contract_match':ok,'reviewed_unit_coverage':len(items),'total_units':len(case['source_mapping']),'excluded_units':[u for u in case['source_mapping'] if u not in case['reviewed_A_v2_labels']],'counts':counts(items),'items':items,'detail_attributes':'unscorable: A-v2 emits roles, not drug-dose-route-time associations or generated allergy statements'})
        # B has association-bearing outputs. Keep a separate task and denominator.
        for run in rows:
            if run.get('candidate')!='B' or run['case_id'] not in ['DEV-002','dev-003']:continue
            case=cases[run['case_id']];ok=compatible(run,case,'B');pred=run.get('validation',{}).get('output');items=[]
            def add(name,value):items.append({'fact':name,'status':'unscorable' if value is None else 'correct' if value else 'incorrect'})
            if run['case_id']=='DEV-002':
                for uid,drug,role,dose,frequency,tm in [('U11','амлодипин','regular_medication','5 мг','өдөрт 1 удаа',None),('U21','парацетамол','administered_treatment','500 мг','нэг удаа','10:15')]:
                    meds=[m for m in (pred or {}).get('medications',[]) if m.get('name','').casefold()==drug]
                    med=meds[0] if len(meds)==1 else None
                    linked=med and any(e['source_unit']==uid and e['quote'] in case['source_mapping'][uid]['text'] for e in med['evidence'])
                    for key,expected in [('role',role),('dose',dose),('frequency',frequency),('time',tm),('route','oral')]:
                        value=None if not ok or pred is None else False
                        if ok and med and linked:
                            v=med.get(key)
                            if key=='route':value=oral(v,med['evidence'],{'uid':uid,'text':case['source_mapping'][uid]['text']})
                            elif key=='time':value=v is None if expected is None else v in ['10:15','10:15-д']
                            else:value=v==expected
                        add(uid+'.'+key,value)
                for name,uid,word,area in [('patient_attribution','U13','гэж хэлэв','allergies'),('today_dose_not_asked','U12','асуугаагүй','medication_context'),('no_other_treatment','U23','өөр эмчилгээ хийгээгүй','medication_context')]:
                    value=None if not ok or pred is None else any(word in x['statement'] and any(e['source_unit']==uid and e['quote'] in case['source_mapping'][uid]['text'] and word in e['quote'] for e in x['evidence']) for x in pred.get(area,[]))
                    # U12 may be preserved as linked medication evidence, without invented time/negative assertion.
                    if name=='today_dose_not_asked' and ok and pred is not None:
                        value=value or any(m.get('time') is None and any(e['source_unit']==uid and word in e['quote'] and e['quote'] in case['source_mapping'][uid]['text'] for e in m['evidence']) for m in pred.get('medications',[]))
                    add(name,value)
            else:
                add('no_invented_medication_rows',None if not ok or pred is None else pred['medications']==[])
                for uid,word,area in [('U5','Эмийн харшилгүй','allergies'),('U6','Эмчилгээ хийгээгүй','medication_context')]:
                    add(uid,None if not ok or pred is None else any(word in x['statement'] and any(e['source_unit']==uid and e['quote'] in case['source_mapping'][uid]['text'] for e in x['evidence']) for x in pred[area]))
            details.append({'model':label,'case_id':case['case_id'],'contract':'B-v2 structured association task, separate from A','artifact':path,'compatible':ok,'counts':counts(items),'items':items,'note':'Missing structured fact is incorrect; unavailable/invalid whole output unscorable. Only explicit reviewed facts scored.'})
    forms=[]
    for path in ['evaluation/recovery-v06/baseline-1.7b-other/report.json','evaluation/recovery-v06/grouped-1.7b/report.json']:
        report=json.loads((ROOT/path).read_text())
        for run in report['cases']:
            if run['case_id'] not in cases:continue
            case=cases[run['case_id']];ok=run['source_sha256']==case['source_sha256'] and run['units']==[ {k:v for k,v in u.items() if k not in ['original_s_id','model_text']} for u in case['source_mapping'].values()]
            assignments=run.get('assignments');items=[]
            for field,units in case['reviewed_form_categories'].items():
                for u in units:
                    actual=[f for f,ids in (assignments or {}).items() if int(u[1:]) in ids]
                    status='unscorable' if not ok or assignments is None or field=='vital_measurements_phase_unspecified' else 'correct' if actual==[field] else 'incorrect'
                    items.append({'unit':u,'expected_category':field,'actual_categories':actual,'status':status,'missing_expected_category':field not in actual,'extra_categories':[f for f in actual if f!=field]})
            forms.append({'model':'qwen3:1.7b','prompt':report['prompt_version'],'artifact':path,'case_id':case['case_id'],'source_match':ok,'counts':counts(items),'items':items})
    output={'review_version':bundle['version'],'quality_claim':'Partial reviewed development diagnostics only; neither held-out nor clinical validation','medication_A_v2':results,'structured_B_v2':details,'full_form_source_assignment':forms,'excluded':['All original dev-004 home-use clarification facts; they were not in the original source','probe-med-001 whole-case labels remain unreviewed','All unlisted facts, mixed-unit remainder, and unavailable full-form predictions for original-4B/control','Full-form dev-004 observation phase: clinician approved measurements, not initial/current timing','A-v2 cannot score generated patient attribution or drug-dose-route-time associations'],'training_exported':False}
    return output


if __name__=='__main__':
    p=OUT/'reviewed-subset-results.json'
    if p.exists():raise FileExistsError(p)
    p.write_text(json.dumps(score(),ensure_ascii=False,indent=2)+'\n')
