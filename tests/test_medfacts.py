import copy,json
import pytest
from scripts.medfacts import validate,record,ROOT
from scripts.medfacts_data import validated
from scripts.medfacts_baseline import score


def test_authoritative_revised_approval_exact_source_and_history():
    train,dev=validated();assert len(train)==2 and all(c['split']=='train' for c in train)
    b=train[1];assert '[S03] Одоо өөр эм тогтмол хэрэглэдэг эсэх нь тодорхойгүй.' in b['source_note']
    assert b['history']['earlier_full_source_available'] is False
    assert 'асуугаагүй' in train[0]['source_note']
    assert all(c['whole_target_loss_available'] is False for c in dev)
    assert {c['underlying_case_id'] for c in train}.isdisjoint(c['underlying_case_id'] for c in dev)


def test_scoped_targets_preserve_evidence_and_exclude_unreviewed_exam():
    for c in validated()[0]:
        result=validate(json.dumps(c['target'],ensure_ascii=False),c['source_note'],c['scope'])
        for spans in result['resolved_evidence']:
            for e in spans:assert c['source_note'][e['start']:e['end']]==e['quote']
        assert not any(e['unit_id'] in c['unrequested_units'] for f in c['target']['facts'] for e in f['evidence'])
        record(c)


def test_overlapping_use_attributes_and_distinct_uncertainty():
    c=validated()[0][0];value=copy.deepcopy(c['target']);value['facts'][1]['attributes']+=['home_preencounter']
    # Structure permits independent regular/home attributes; semantics still need source review.
    validate(json.dumps(value,ensure_ascii=False),c['source_note'],c['scope'])
    value['facts'][2]['attributes']=['unknown','not_asked']
    with pytest.raises(ValueError,match='collapse'):validate(json.dumps(value),c['source_note'],c['scope'])
    value=copy.deepcopy(c['target']);value['facts'][0]['evidence'][0]['quote']='invented diagnosis'
    with pytest.raises(ValueError,match='Quote'):validate(json.dumps(value),c['source_note'],c['scope'])


def test_quantity_time_and_scope_remain_original_text():
    a,b=validated()[0]
    text=json.dumps(a['target'],ensure_ascii=False);assert '50 мкг' in text and '50 мг' not in text and 'өөр эм өгөөгүй' in text and 'өөр эмчилгээ' not in text
    text=json.dumps(b['target'],ensure_ascii=False);assert '14:30-ын тэмдэглэл' in text and 'сорьц хараахан аваагүй' in text
    assert not any('encounter_administered' in f['attributes'] for f in b['target']['facts'])
    assert not any('pending_result' in f['attributes'] for f in b['target']['facts'])


def test_semantic_scoring_does_not_fill_unreviewed_positions():
    _,dev=validated();c=dev[0];good=score(c['target'],c);assert good['correct']==5
    wrong=copy.deepcopy(c['target']);wrong['facts'][0]['attributes']=['encounter_administered']
    assert score(wrong,c)['incorrect']==1
    assert score(None,c)['unscorable']==5
    assert score({'facts':[]},c)['incorrect']==5
