import asyncio,json
import httpx
from scripts import pipeline4b_compare as compare

def exercise(monkeypatch,tmp_path,timeout=False):
 models=[{'tag':'official','digest':'a'},{'tag':'control','digest':'b'},{'tag':'pipeline-test','digest':'c'}];p=tmp_path/'pins.json';p.write_text(json.dumps({'comparison_models':models}));calls=[]
 def respond(request):
  if request.url.path=='/api/tags':return httpx.Response(200,json={'models':[{'name':m['tag'],'digest':m['digest']} for m in models]})
  if request.url.path=='/api/ps':return httpx.Response(200,json={'models':[{'name':'official'}]})
  body=json.loads(request.content);calls.append(body)
  if timeout:raise httpx.ReadTimeout('fixture timeout')
  output={k:'other' for k in body['format']['properties']}
  return httpx.Response(200,json={'done':True,'done_reason':'stop','message':{'content':json.dumps(output)}})
 factory=httpx.AsyncClient
 monkeypatch.setattr(compare.httpx,'AsyncClient',lambda **kw:factory(transport=httpx.MockTransport(respond),**kw))
 out=tmp_path/'out';asyncio.run(compare.run(p,out));return calls,json.loads((out/'report.json').read_text())

def test_twelve_frozen_requests_and_pairwise_agreement(monkeypatch,tmp_path):
 calls,r=exercise(monkeypatch,tmp_path);assert len(calls)==12 and r['finished'];assert len(r['agreements'])==8
 assert all(c['think'] is False and c['options']['num_predict']==1600 and c['options']['num_ctx']==16384 for c in calls)
 assert all(x['exact_output_agreement'] is True for x in r['agreements'])

def test_timeout_stops_before_second_request_when_idleness_unproven(monkeypatch,tmp_path):
 calls,r=exercise(monkeypatch,tmp_path,True);assert len(calls)==1 and not r['finished'];assert r['runs'][0]['error']=='timeout';assert not r['runs'][0]['idle_proven'];assert 'stop' in r['stop_reason'].lower()
