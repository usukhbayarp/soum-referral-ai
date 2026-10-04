import asyncio,json
import httpx
from scripts import pipeline4b_compare as compare

def exercise(monkeypatch,tmp_path,timeout=False,missing_smoke=False):
 models=[{'tag':'official','digest':'a'},{'tag':'control','digest':'b'},{'tag':'pipeline-test','digest':'c'}];models[2]['digest']=None if missing_smoke else 'c';p=tmp_path/'pins.json';p.write_text(json.dumps({'comparison_models':models}));calls=[]
 def respond(request):
  if request.url.path=='/api/tags':return httpx.Response(200,json={'models':[{'name':m['tag'],'digest':m['digest']} for m in models]})
  if request.url.path=='/api/ps':return httpx.Response(200,json={'models':[{'name':'official'}]})
  body=json.loads(request.content);calls.append(body)
  if timeout:raise httpx.ReadTimeout('fixture timeout')
  output={k:'other' for k in body['format']['properties']}
  return httpx.Response(200,json={'done':True,'done_reason':'stop','message':{'content':json.dumps(output)}})
 factory=httpx.AsyncClient
 monkeypatch.setattr(compare.httpx,'AsyncClient',lambda **kw:factory(transport=httpx.MockTransport(respond),**kw))
 out=tmp_path/'out';asyncio.run(compare.run(p,out,allow_missing_smoke=missing_smoke));return calls,json.loads((out/'report.json').read_text())

def test_twelve_frozen_requests_and_pairwise_agreement(monkeypatch,tmp_path):
 calls,r=exercise(monkeypatch,tmp_path);assert len(calls)==12 and r['finished'];assert len(r['agreements'])==8
 assert all(c['think'] is False and c['options']['num_predict']==1600 and c['options']['num_ctx']==16384 for c in calls)
 assert all(x['exact_output_agreement'] is True for x in r['agreements'])

def test_timeout_stops_before_second_request_when_idleness_unproven(monkeypatch,tmp_path):
 calls,r=exercise(monkeypatch,tmp_path,True);assert len(calls)==1 and not r['finished'];assert r['runs'][0]['error']=='timeout';assert not r['runs'][0]['idle_proven'];assert 'stop' in r['stop_reason'].lower()


def test_summary_retains_failures_and_separates_missing_extra():
 from scripts.pipeline4b_summary import summarize
 roles={'U1':'allergy_statement','U2':'other','U3':'other','U4':'other','U5':'other','U6':'regular_medication','U7':'other'}
 base={'case_id':'dev-003','model':{'tag':'fixture'},'wall_seconds':2}
 report={'runs':[{**base,'validation':{'output':roles}},{**base,'error':'timeout'}]}
 result=summarize(report)
 a,b=result['runs']
 assert a['missing_relevant_units']==['U5'] and a['extra_relevant_units']==['U1']
 assert set(a['allergy_or_negation_confusions'])=={'U1','U5','U6'}
 assert b['error']=='timeout' and b['structurally_valid'] is False
 assert result['clinical_candidate_eligible'] is False


def test_explicit_missing_smoke_runs_only_predeclared_eight(monkeypatch,tmp_path):
 calls,r=exercise(monkeypatch,tmp_path,missing_smoke=True)
 assert len(calls)==8 and r['finished'] and not r['all_three_models_available']
 assert len(r['agreements'])==4 and r['not_attempted_models'][0]['tag']=='pipeline-test'
 assert all(c['model']!='pipeline-test' for c in calls)
