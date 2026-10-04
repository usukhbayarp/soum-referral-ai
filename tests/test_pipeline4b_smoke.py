import json
from pathlib import Path
from scripts.medication_experiment import request,validate_output

ROOT=Path(__file__).resolve().parents[1]
def test_engineering_fixture_remains_separate_unreviewed_and_contract_compatible():
 f=json.loads((ROOT/'training/engineering4b-fixture.json').read_text());assert f['clinician_review_status']=='unreviewed';assert 'pipeline-test-only' in f['purpose']
 req,mapping=request('A',f['source_note'],2);r=validate_output('A',json.dumps(f['labels']),mapping)
 assert r['output']['U4']=='mixed_or_unclear';assert req['think'] is False

def test_observed_smoke_proves_nonzero_steps_and_fusion_without_claiming_export():
 r=json.loads((ROOT/'evaluation/pipeline4b-smoke/smoke-result.json').read_text())
 assert [x['optimizer_step'] for x in r['steps']]==[1,2,3]
 assert any(v>0 for v in r['steps'][-1]['adapter_max_abs_delta'].values())
 assert r['stages']['reload']=='observed_success';assert r['stages']['adapter_inference']=='observed_success'
 assert all(x['max_abs_weight_delta']>0 and x['fusion_formula_equal'] for x in r['fusion_checks'])
 assert r['stages']['full_dequantized_export']=='not_attempted_disk_budget';assert r['clinical_candidate_eligible'] is False
 assert r['sequence']['completion_mask_verified'] and not r['sequence']['truncated']
