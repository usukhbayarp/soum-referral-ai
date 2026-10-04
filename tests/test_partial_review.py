import copy,json,struct
import pytest
from scripts.partial_review import OUT,validate
from scripts.score_partial_review import score,oral
from scripts.sparse_adapter_export import header,replace_tensor,tensor_hash
from scripts.role_review import validate as clinical_validate


def test_partial_source_and_family_immutability():
    b=json.loads((OUT/'annotations.json').read_text());validate(b)
    row=next(r for r in b['cases'] if r['case_id']=='dev-003')
    assert row['source_mapping']['U4']['text']=='Уушгинд шуугиан сонсогдоогүй.'
    assert row['reviewed_A_v2_labels']['U4']=='other'
    row['source_note']+=' added'
    with pytest.raises(ValueError,match='source'):validate(b)


def test_partial_annotations_cannot_enter_whole_note_export():
    b=json.loads((OUT/'annotations.json').read_text())
    assert b['whole_note_training_eligible'] is False
    with pytest.raises(ValueError):clinical_validate(b['cases'],[])
    d=json.loads((OUT/'dev004-clarified-draft.json').read_text())
    assert d['split']=='development' and d['underlying_case_id']=='fictional-004'
    assert d['clinician_review_status']=='awaiting confirmation' and not d['evaluate_original_predictions']


def test_rescore_retains_denominators_and_excludes_clarified_facts():
    r=score();a=r['medication_A_v2']
    for model in ['1.7B','original-4B','converted-control']:
        rows=[x for x in a if x['model']==model]
        assert sum(x['counts']['denominator'] for x in rows)==14
        assert next(x for x in rows if x['case_id']=='probe-med-001')['counts']['denominator']==0
        assert {i['unit'] for i in next(x for x in rows if x['case_id']=='dev-004')['items']}=={'U3','U4'}
    assert r==json.loads((OUT/'reviewed-subset-results.json').read_text())


def test_oral_normalization_requires_correct_linked_phrase():
    unit={'uid':'U11','text':'Амлодипин 5 мг уудаг.'}
    evidence=[{'source_unit':'U11','quote':unit['text']}]
    assert oral('уудаг',evidence,unit) and oral('oral',evidence,unit)
    assert not oral('өдөрт 1 удаа',evidence,unit)
    assert not oral('oral',[{'source_unit':'U12','quote':unit['text']}],unit)
    assert not oral('oral',[{'source_unit':'U11','quote':'уусан'}],unit)


def write_tensor(path,values):
    h={};data=b''
    for key,value in values.items():
        blob=struct.pack('<HH',*value);h[key]={'dtype':'BF16','shape':[2],'data_offsets':[len(data),len(data)+len(blob)]};data+=blob
    encoded=json.dumps(h).encode();encoded+=b' '*((-len(encoded))%8)
    path.write_bytes(struct.pack('<Q',len(encoded))+encoded+data)


def test_sparse_replacement_preserves_headers_and_unaffected_tensor(tmp_path):
    dst=tmp_path/'base';patch=tmp_path/'patch';write_tensor(dst,{'q':[1,2],'v':[3,4]});write_tensor(patch,{'q':[5,6]})
    off,h=header(dst);before=tensor_hash(dst,off,h['v']);replace_tensor(dst,'q',patch)
    assert header(dst)==(off,h) and tensor_hash(dst,off,h['v'])==before
    po,ph=header(patch);assert tensor_hash(dst,off,h['q'])==tensor_hash(patch,po,ph['q'])
