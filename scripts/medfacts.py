"""Frozen compact source-linked fact contract; no clinical prose generation."""
import hashlib,json
from pathlib import Path
from pydantic import BaseModel,ConfigDict,Field
from scripts.medication_experiment import ROOT,model_view,strict_json
DIR=ROOT/'experiments/medfacts-v1'
CONTRACT=json.loads((DIR/'contract.json').read_text())
MODEL='soum-qwen3-4b-control:mlx128-52a5ab34'

class Strict(BaseModel):model_config=ConfigDict(extra='forbid',strict=True)
class Evidence(Strict):
    unit_id:str
    quote:str=Field(min_length=1,max_length=500)
class Fact(Strict):
    topic:str
    attributes:list[str]=Field(max_length=12)
    evidence:list[Evidence]=Field(min_length=1,max_length=4)
    context:list[str]=Field(max_length=6)
class Result(Strict):facts:list[Fact]=Field(max_length=24)


def request(note,scope,model=MODEL):
    view,mapping=model_view(note)
    schema=Result.model_json_schema()
    schema['$defs']['Fact']['properties']['topic']['enum']=CONTRACT['topics']
    schema['$defs']['Fact']['properties']['attributes']['items']['enum']=list(CONTRACT['attributes'])
    schema['$defs']['Evidence']['properties']['unit_id']['enum']=list(mapping)
    schema['$defs']['Fact']['properties']['context']['items']['enum']=list(mapping)
    payload={'scope':scope,'topics':CONTRACT['topics'],'attribute_definitions':CONTRACT['attributes'],**view}
    return {'model':model,'stream':False,'think':False,'keep_alive':'5m','options':{'temperature':0,'seed':42,'num_ctx':16384,'num_predict':3200},'format':schema,'messages':[{'role':'system','content':(DIR/'prompt.txt').read_text().strip()},{'role':'user','content':json.dumps(payload,ensure_ascii=False,separators=(',',':'))}]},mapping


def validate(raw,note,scope):
    value=Result.model_validate(strict_json(raw)).model_dump();mapping=model_view(note)[1];resolved=[]
    for fact in value['facts']:
        if fact['topic'] not in CONTRACT['topics'] or len(set(fact['attributes']))!=len(fact['attributes']) or any(a not in CONTRACT['attributes'] for a in fact['attributes']):raise ValueError('Unknown/duplicate topic or attribute')
        if len(set(fact['attributes'])&{'not_asked','unknown','not_documented','not_clarified','explicit_absence'})>1:raise ValueError('Do not collapse distinct uncertainty/absence facts')
        if any(u not in mapping for u in fact['context']):raise ValueError('Invalid context ID')
        spans=[]
        for e in fact['evidence']:
            if e['unit_id'] not in mapping:raise ValueError('Invalid evidence ID')
            unit=mapping[e['unit_id']];q=e['quote']
            if unit['text'].count(q)!=1:raise ValueError('Quote must resolve exactly once in original unit')
            if not any(e['unit_id'] in s['units'] and fact['topic'] in s['topics'] for s in scope):raise ValueError('Outside requested scope')
            start=unit['start']+unit['text'].index(q);spans.append({'unit_id':e['unit_id'],'start':start,'end':start+len(q),'quote':q})
        resolved.append(spans)
    return {'output':value,'resolved_evidence':resolved,'structural_valid':True,'lexical_valid':True,'clinical_correctness':'not inferred'}


def record(case):
    req,_=request(case['source_note'],case['scope'])
    validate(json.dumps(case['target'],ensure_ascii=False),case['source_note'],case['scope'])
    return {'messages':req['messages']+[{'role':'assistant','content':json.dumps(case['target'],ensure_ascii=False,separators=(',',':'))}]}


def hashes():return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [DIR/'contract.json',DIR/'prompt.txt']}
