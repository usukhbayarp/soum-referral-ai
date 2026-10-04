import copy,json
from pathlib import Path
import pytest
from scripts.export_reviewed_adapter import adapter_modules
from scripts.medfacts_pilot import preflight
from scripts.medfacts_data import export
from scripts.medfacts_select import compare
from scripts.medfacts import ROOT


def test_all_adapter_modules_are_enumerated():
    pairs={f'model.layers.{i}.self_attn.q_proj.lora_{s}':None for i in range(3) for s in ['a','b']}
    assert len(adapter_modules(pairs))==3
    del pairs['model.layers.2.self_attn.q_proj.lora_b']
    with pytest.raises(ValueError):adapter_modules(pairs)
    with pytest.raises(ValueError):adapter_modules({'unsupported.weight':None})


def test_pilot_preflight_rejects_invented_dev_targets(monkeypatch,tmp_path):
    import scripts.medfacts_data as data
    # Exercise export in a fresh permitted sandbox without leaving repository artifacts.
    rows,dev=data.validated();monkeypatch.setattr(data,'validated',lambda:(rows,dev));monkeypatch.setattr(data,'ROOT',tmp_path)
    out=tmp_path/'.runtime'/'export';export(out);monkeypatch.undo()
    records,capacity=preflight(out)
    assert len(records)==2 and capacity['maximum']==2727
    (out/'valid.jsonl').write_text('{}\n')
    with pytest.raises(ValueError,match='partial-dev'):preflight(out)


def test_matched_selection_keeps_failures_and_baseline_on_tie():
    base=json.loads((ROOT/'evaluation/medfacts-v1/untuned-baseline.json').read_text())
    result=compare([base]);assert result['reports'][0]['correct']==1
    assert result['reports'][0]['incorrect']==4 and result['reports'][0]['unscorable']==4
    candidate=copy.deepcopy(base);candidate['model']='soum-quality:checkpoint2'
    assert compare([base,candidate])['diagnostic_preference']==base['model']
    candidate['runs'][0]['request']['options']['seed']=43
    with pytest.raises(ValueError,match='settings'):compare([base,candidate])
