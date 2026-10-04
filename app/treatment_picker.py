"""Experimental ID-only picker. Exact source resolution; never generated clinical text."""
import asyncio,copy,hashlib,json,re
import httpx
from .adapter import OllamaAdapter
from .core import ROOT,MAX_CHARS,segment,ExtractionError
DIRECTORY=ROOT/'experiments/treatment-picker-v1'
CONTRACT=json.loads((DIRECTORY/'contract.json').read_text())
PROMPT=(DIRECTORY/'prompt.txt').read_text().strip()

def build_request(note):
    if not note.strip() or len(note)>MAX_CHARS:raise ExtractionError('input_limit',413)
    units=segment(note);schema=copy.deepcopy(CONTRACT['schema']);schema['properties']['ids']['items']['enum']=[u['id'] for u in units]
    view=[{'id':u['id'],'text':re.sub(r'^\[S\d+\]\s*','',u['text'])} for u in units]
    return {'model':CONTRACT['model'],'stream':False,'think':False,'keep_alive':0,'options':CONTRACT['settings'],'format':schema,'messages':[{'role':'system','content':PROMPT},{'role':'user','content':json.dumps({'units':view},ensure_ascii=False,separators=(',',':'))}]},units

def resolve(raw,units):
    def pairs(items):
        d={}
        for k,v in items:
            if k in d:raise ValueError('Duplicate key')
            d[k]=v
        return d
    try:
        value=json.loads(raw,object_pairs_hook=pairs)
        if type(value)!=dict or set(value)!={'ids'} or type(value['ids'])!=list:raise ValueError()
        ids=value['ids'];known={u['id']:u for u in units}
        if any(type(i)!=int or i not in known for i in ids) or len(set(ids))!=len(ids):raise ValueError()
        paragraphs={};paragraph=None
        for u in units:
            if re.match(r'^\[S\d+\]',u['text']):paragraph=u['id']
            paragraphs[u['id']]=paragraph
        return [{'unit':known[i],'context':[u for u in units if u['id']!=i and (abs(u['id']-i)==1 or (paragraphs[i] is not None and paragraphs[u['id']]==paragraphs[i]))]} for i in sorted(ids)]
    except (ValueError,TypeError):raise ExtractionError('invalid_evidence') from None

async def suggest(note,capture=None):
    request,units=build_request(note);adapter=OllamaAdapter(model=CONTRACT['model']);capture=capture if capture is not None else {}
    capture.update(request=request,units=units)
    try:
        ready=await adapter.readiness()
        if ready['model_digest']!=CONTRACT['model_digest']:raise ExtractionError('model_identity_changed',503)
        async with asyncio.timeout(120):
            async with httpx.AsyncClient(base_url=adapter.base_url,timeout=120,trust_env=False) as client:
                async with client.stream('POST','/api/chat',json=request) as response:
                    response.raise_for_status();body=bytearray()
                    async for chunk in response.aiter_bytes():
                        body.extend(chunk)
                        if len(body)>65536:raise ExtractionError('output_limit')
                capture['raw_response']=body.decode();data=json.loads(body)
        if data.get('done') is not True or data.get('done_reason')!='stop':raise ExtractionError('incomplete_output')
        if data.get('message',{}).get('thinking'):raise ExtractionError('unexpected_thinking')
        selected=resolve(data['message']['content'],units)
        return {'suggestions':selected,'units':units,'model':CONTRACT['model'],'model_digest':ready['model_digest'],'prompt_version':CONTRACT['prompt_version'],'contract_version':CONTRACT['version'],'settings':request['options']}
    except (TimeoutError,httpx.TimeoutException):raise ExtractionError('inference_timeout',504) from None
    except httpx.HTTPError:raise ExtractionError('runtime_unavailable',503) from None
    except (ValueError,TypeError,KeyError,AttributeError):raise ExtractionError('invalid_response') from None
