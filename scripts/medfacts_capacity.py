"""Static full-sequence checks, then optionally ONE forward/backward; no optimizer."""
import argparse,hashlib,json,math,time,os
from pathlib import Path
from scripts.medfacts import ROOT,record
from scripts.medfacts_data import validated
from scripts.training_tokens import checked_tokens,completion_loss
OUT=ROOT/'evaluation/medfacts-v1'
BASE=ROOT/'.runtime/pipeline4b/base'


def main(probe):
    os.environ['HF_HUB_OFFLINE']='1'
    rows,_=validated()
    pins=json.loads((ROOT/'evaluation/pipeline4b-smoke/pins.json').read_text())
    from scripts.training_prepare import check_versions
    check_versions(pins['versions'])
    for name,entry in json.loads((ROOT/'evaluation/pipeline4b-smoke/download.json').read_text())['files'].items():
        with (BASE/name).open('rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==entry['sha256']
    from transformers import AutoTokenizer
    tok=AutoTokenizer.from_pretrained(BASE,local_files_only=True,trust_remote_code=False)
    data=[checked_tokens(record(c),tok) for c in rows]
    lengths=[{'case_id':c['case_id'],'full_tokens':len(t),'prompt_tokens':o,'completion_tokens':len(t)-o,'completion_only_mask_verified':True} for c,(t,o) in zip(rows,data)]
    report={'lengths':lengths,'maximum':max(len(t) for t,o in data),'truncated':False,'quality_training_started':False}
    if not probe:
        path=OUT/'token-lengths.json'
        if path.exists():raise FileExistsError(path)
        path.write_text(json.dumps(report,indent=2)+'\n');print(report);return
    path=OUT/'capacity.json'
    if path.exists():raise FileExistsError(path)
    import httpx
    with httpx.Client(trust_env=False,timeout=5) as c:assert c.get('http://127.0.0.1:11434/api/ps').json()['models']==[]
    import mlx.core as mx
    import mlx.nn as nn
    from mlx.utils import tree_flatten
    from mlx_lm.utils import load
    from mlx_lm.tuner.utils import linear_to_lora_layers
    from mlx_lm.tuner.trainer import grad_checkpoint
    mx.set_memory_limit(8*1024**3);mx.set_cache_limit(128*1024**2);mx.random.seed(42);start=time.monotonic()
    report.update(status='started',optimizer_steps=0,batch_size=1,memory_limit_bytes=8*1024**3)
    path.write_text(json.dumps(report,indent=2)+'\n')
    model,_=load(str(BASE));model.freeze();linear_to_lora_layers(model,1,{'rank':2,'scale':4.,'dropout':0.,'keys':['self_attn.q_proj','self_attn.v_proj']});grad_checkpoint(model.layers[0])
    before={k:mx.array(v) for k,v in tree_flatten(model.trainable_parameters())};mx.eval(before)
    tokens,offset=max(data,key=lambda x:len(x[0]));model.train()
    (loss,count),grads=nn.value_and_grad(model,completion_loss)(model,mx.array([tokens]),mx.array([[offset,len(tokens)]]));mx.eval(loss,grads)
    assert math.isfinite(float(loss)) and all(bool(mx.all(mx.isfinite(g))) for _,g in tree_flatten(grads))
    assert all(bool(mx.array_equal(v,before[k])) for k,v in tree_flatten(model.trainable_parameters()))
    report.update(status='observed_success',loss=float(loss),completion_tokens_in_loss=int(count),adapter_parameters_unchanged=True,persistent_weight_updates=False,mlx_peak_memory_bytes=mx.get_peak_memory(),elapsed_seconds=time.monotonic()-start)
    path.write_text(json.dumps(report,indent=2)+'\n')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--probe',action='store_true');a=p.parse_args();main(a.probe)
