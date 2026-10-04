import copy,hashlib,json
import pytest
from scripts import role_review as rr

def case(note='Эмийн харшлыг асуугаагүй.',split='train',family='train-family'):
 return {'annotation_version':rr.VERSION,'case_id':family+'-001','underlying_case_id':family,'source_note':note,'source_sha256':hashlib.sha256(note.encode()).hexdigest(),'source_units':rr.source_units(note),'labels':{k:'mixed_or_unclear' for k in rr.source_units(note)},'prompt_version':'medication-A-2','extraction_contract':'medication-representation-1','segmentation_version':'sentence-lines-1','split':split,'review_status':'reviewed','reviewer':'Fictional test reviewer','review_date':'2026-10-04','provenance':{'fictional':True,'origin':'unit-test-only','correction_basis':'test gate, not clinician approval'},'correction_version':'test-v1','supersedes':'test-provisional'}

def registry(rows):return [{'underlying_case_id':r['underlying_case_id'],'split':r['split']} for r in rows]+[{'underlying_case_id':'reserved-family','split':'test'}]

def test_exact_source_offsets_roles_and_review_provenance():
 r=case();rr.validate([r],registry([r]));r['source_note']+=' '; 
 with pytest.raises(ValueError,match='Source hash'):rr.validate([r],registry([r]))
 r=case();r['labels']={}
 with pytest.raises(ValueError,match='every source unit'):rr.validate([r],registry([r]))
 r=case();r['reviewer']=''
 with pytest.raises(ValueError,match='reviewer'):rr.validate([r],registry([r]))

def test_no_reserved_test_contents_or_family_overlap_or_development_laundering():
 r=case(split='test')
 with pytest.raises(ValueError,match='test contents'):rr.validate([r],registry([r])[:1])
 r=case();reg=registry([r])+[{'underlying_case_id':'train-family','split':'development'}]
 with pytest.raises(ValueError,match='overlapping'):rr.validate([r],reg)
 old=rr.load_cases()[0];r=case(old['source_note'])
 with pytest.raises(ValueError,match='Development source reuse'):rr.validate([r],registry([r]))

def test_private_versioned_export_preserves_mixed_excludes_unreviewed_and_tests(monkeypatch,tmp_path):
 # Redirect workspace restriction only; frozen contracts and request builder still real.
 root=rr.ROOT
 a=case();b=case('Энэ үзлэгээр эмчилгээ хийгээгүй.','development','dev-family');u=case('Тодорхойгүй.','train','unreviewed-family');u['review_status']='unreviewed';rows=[a,b,u]
 output=root/'.runtime/test-role-review';import tempfile
 output=root/'.runtime'/next(tempfile._get_candidate_names())
 try:
  rr.stage(rows,registry(rows),output,True)
  train=[json.loads(x) for x in (output/'train.jsonl').read_text().splitlines()];assert len(train)==1
  assert json.loads(train[0]['messages'][-1]['content'])==a['labels'];assert 'mixed_or_unclear' in train[0]['messages'][-1]['content']
  assert not (output/'test.jsonl').exists()
  with pytest.raises(ValueError,match='overwrite'):rr.stage(rows,registry(rows),output,True)
 finally:
  import shutil
  if output.exists():shutil.rmtree(output) # only this test's freshly created temporary directory
 with pytest.raises(ValueError,match='ignored'):rr.stage(rows,registry(rows),tmp_path/'public',True)

def test_smoke_fixture_cannot_pass_clinical_gate():
 note=json.loads((rr.ROOT/'training/engineering4b-fixture.json').read_text())['source_note'];r=case(note)
 with pytest.raises(ValueError,match='Engineering'):rr.validate([r],registry([r]))
