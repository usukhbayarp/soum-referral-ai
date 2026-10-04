import json
import pytest
from fastapi.testclient import TestClient
from app.treatment_picker import build_request,resolve
from app.core import ExtractionError
from app.main import create_app

def test_exact_negation_offsets_and_context():
    note='[S01] Ирэв.\n[S02] Эм өгөөгүй. Дараа өгөхөөр төлөвлөсөн.'
    req,units=build_request(note);selected=resolve('{"ids":[2]}',units)
    assert selected[0]['unit']['text']=='[S02] Эм өгөөгүй.'
    assert note[units[1]['start']:units[1]['end']]==units[1]['text']
    assert len(selected[0]['context'])==2
    assert '[S02]' not in req['messages'][1]['content']
    assert resolve('{"ids":[]}',units)==[]

@pytest.mark.parametrize('raw',['{"ids":[1,1]}','{"ids":[99]}','{"ids":[true]}','{"ids":["1"]}','{"ids":[],"quote":"x"}','{"ids":[],"ids":[1]}','not json','[]'])
def test_invalid_picker_output(raw):
    with pytest.raises(ExtractionError):resolve(raw,build_request('Эм өгөөгүй.')[1])

def test_flag_off_and_same_request_boundary(monkeypatch):
    monkeypatch.delenv('TREATMENT_PICKER_ENABLED',raising=False)
    with TestClient(create_app()) as client:
        assert client.get('/api/config').json()['treatment_picker_enabled'] is False
        assert client.post('/api/treatment-suggestions',json={'note':'Эм өгөөгүй.','request_id':'1'}).status_code==404
    monkeypatch.setenv('TREATMENT_PICKER_ENABLED','1')
    async def fake(note):return {'suggestions':resolve('{"ids":[1]}',build_request(note)[1])}
    monkeypatch.setattr('app.treatment_picker.suggest',fake)
    with TestClient(create_app()) as client:
        r=client.post('/api/treatment-suggestions',json={'note':'Эм өгөөгүй.','request_id':'x'});assert r.status_code==200 and r.json()['request_id']=='x'
        assert client.post('/api/treatment-suggestions',json={'note':'x','request_id':'1'},headers={'origin':'http://evil.example'}).status_code==403

def test_context_keeps_complete_original_s_paragraph():
    note='[S06] Эм өгсөн. Дараа нь мэдээлсэн. Өөр эмчилгээ хийгээгүй.\n[S07] Одоогийн байдал.'
    units=build_request(note)[1]
    selection=resolve('{"ids":[3]}',units)[0]
    assert [u['id'] for u in selection['context']]==[1,2,4]
    assert selection['unit']['text']=='Өөр эмчилгээ хийгээгүй.'
