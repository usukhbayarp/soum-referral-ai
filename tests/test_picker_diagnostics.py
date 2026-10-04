"""Offline checks for diagnostic scoring and frozen source provenance; no inference."""
import copy
import json
from pathlib import Path
import pytest
from app.core import ExtractionError
from scripts.diagnose_picker import score

ROOT=Path(__file__).resolve().parents[1]
PLAN=json.loads((ROOT/'evaluation/picker-diagnostics-v1/plan.json').read_text())

def test_scoring_keeps_omissions_extras_and_unknown_review_scope_separate():
    units=[{'id':i,'text':str(i)} for i in [1,2,3,4]]
    result=score('{"ids":[2,3]}',units,[1,2],[4])
    assert result['retrieved']==[2] and result['missing']==[1]
    assert result['unreviewed']==[3] and result['extra']==[] and not result['exact']
    assert score('{"ids":[4]}',units,[1,2],[4])['extra']==[4]
    assert score('{"ids":[]}',units,[1,2],[4])['missing']==[1,2]

@pytest.mark.parametrize('content',['{"ids":[true]}','{"ids":[1,1]}','{"ids":[99]}','{"units":[]}','{"ids":[],"ids":[1]}'])
def test_invalid_outputs_never_receive_retrieval_credit(content):
    with pytest.raises(ExtractionError):score(content,[{'id':1,'text':'original'}],[1],[])

def test_snippets_use_only_reviewed_original_development_units():
    original=json.loads((ROOT/'evaluation/treatment-picker-v1/plan.json').read_text())['cases']
    for case in PLAN['cases']:
        source=next(c for c in original if c['case_id']==case['original_case_id'])
        assert case['split']=='development'
        assert case['source_sha256']==source['source_sha256']
        ids={u['id'] for u in case['original_units']}
        assert ids==set(case['expected_ids']+case['reviewed_negative_ids'])
        assert ids=={u['id'] for u in case['english']}=={u['id'] for u in case['mongolian']}
        for u in case['original_units']:
            assert u in source['units'] and source['source_note'][u['start']:u['end']]==u['text']
        assert set(case['expected_ids'])<=set(source['reviewed_relevant'])
        assert set(case['reviewed_negative_ids'])<=set(source['reviewed_irrelevant'])

def test_paired_conditions_and_native_model_controls():
    for stage,jobs in PLAN['jobs'].items():
        assert len(jobs)==9
        for i in range(0,9,3):
            a,b,c=[copy.deepcopy(j['request']) for j in jobs[i:i+3]]
            assert a['messages'][0]==b['messages'][0]
            a['messages'][1]['content']=b['messages'][1]['content']
            assert a==b
            assert 'format' not in c and all(m['role']=='user' for m in c['messages'])
        for j in jobs:
            assert ('think' in j['request'])==(stage=='control')
    h=json.loads((ROOT/'evaluation/picker-diagnostics-v1/hypothesis-plan.json').read_text())['jobs']['hypothesis']
    a=[j for j in PLAN['jobs']['control'] if j['condition']=='A']
    for before,after in zip(a,h):
        req=copy.deepcopy(before['request']);req.pop('format')
        assert req==after['request']

def test_candidate_native_plan_only_merges_system_into_first_user():
    native=json.loads((ROOT/'evaluation/picker-diagnostics-v1/candidate-native-plan.json').read_text())['jobs']['candidate']
    for original,actual in zip(PLAN['jobs']['candidate'],native):
        expected=copy.deepcopy(original)
        messages=expected['request']['messages']
        if messages[0]['role']=='system':
            expected['request']['messages']=[{'role':'user','content':messages[0]['content']+'\n\n'+messages[1]['content']}]
        assert expected==actual
        assert [m['role'] for m in actual['request']['messages']]==['user']
        assert 'think' not in actual['request']

def test_sole_executed_alternative_has_same_task_and_no_qwen_controls():
    native=json.loads((ROOT/'evaluation/picker-diagnostics-v1/candidate-llama-plan.json').read_text())
    assert native['model_digest']=='46e0c10c039e019119339687c3c1757cc81b9da49709a3b3924863ba87ca666e'
    for original,actual in zip(PLAN['jobs']['control'],native['jobs']['candidate']):
        expected=copy.deepcopy(original)
        expected['request']['model']='llama3.1:8b'
        expected['request'].pop('think')
        assert expected==actual

def test_executed_requests_match_frozen_plans_and_budget():
    import hashlib
    root=ROOT/'evaluation/picker-diagnostics-v1'
    count=0
    for stage,filename in [('control','plan.json'),('hypothesis','hypothesis-plan.json'),('candidate','candidate-llama-plan.json')]:
        path=root/filename
        frozen=json.loads(path.read_text())
        runs=json.loads((root/(stage+'-runs.json')).read_text())
        assert len(runs)==len(frozen['jobs'][stage])
        for run,job in zip(runs,frozen['jobs'][stage]):
            assert run['id']==job['id']
            assert run['plan_sha256']==hashlib.sha256(path.read_bytes()).hexdigest()
            assert json.loads(run['wire_request_utf8'])==job['request']
            if run.get('valid'):
                content=json.loads(run['raw_response'])['message']['content']
                assert run['score']==score(content,job['units'],job['positive'],job['negative'])
        count+=len(runs)
    assert count==21 and count+2<=24  # two non-generating render-only probes
