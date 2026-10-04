import asyncio,hashlib,json
import httpx
from scripts import recovered_compare as c


def test_matched_eight_request_cap_and_identical_contract(monkeypatch,tmp_path):
    models=[{'tag':'control','digest':'a'},{'tag':'pipeline-test','digest':'b'}]
    plan={'models':models,'case_ids':['DEV-002','dev-003','dev-004','probe-med-001'],'serving_template_sha256':hashlib.sha256(b'fixed').hexdigest()}
    path=tmp_path/'plan.json';path.write_text(json.dumps(plan));calls=[]
    def respond(req):
        if req.url.path=='/api/tags':return httpx.Response(200,json={'models':[{'name':m['tag'],'digest':m['digest']} for m in models]})
        if req.url.path=='/api/show':return httpx.Response(200,json={'template':'fixed'})
        body=json.loads(req.content);calls.append(body)
        return httpx.Response(200,json={'done':True,'done_reason':'stop','message':{'content':json.dumps({k:'other' for k in body['format']['properties']})}})
    original=httpx.AsyncClient
    monkeypatch.setattr(c.httpx,'AsyncClient',lambda **kw:original(transport=httpx.MockTransport(respond),**kw));monkeypatch.setattr(c,'OUT',tmp_path)
    asyncio.run(c.run(path));r=json.loads((tmp_path/'matched-comparison.json').read_text())
    assert len(calls)==8 and r['finished'] and all(x['exact_agreement'] for x in r['agreements'])
    for a,b in zip(calls[::2],calls[1::2]):
        assert a['messages']==b['messages'] and a['options']==b['options'] and a['format']==b['format']
    assert all(x['empty_selections'] for x in r['runs'])
