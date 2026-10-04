"""Future explicit quality pilot: 2 approved families x 2 passes, 4 steps maximum.
No automatic deployment or checkpoint promotion. Semantic Ollama selection follows export.
"""
import argparse,hashlib,json,math,os,time
from pathlib import Path
from scripts.medfacts import ROOT,record,hashes
from scripts.medfacts_data import validated
from scripts.training_tokens import checked_tokens,completion_loss


def preflight(directory):
    train,dev=validated();manifest=json.loads((directory/'manifest.json').read_text())
    if manifest['contract_hashes']!=hashes():raise ValueError('Contract changed')
    records=[json.loads(x) for x in (directory/'train.jsonl').read_text().splitlines()]
    if records!=[record(c) for c in train]:raise ValueError('Export differs from approved mappings')
    if hashlib.sha256((directory/'train.jsonl').read_bytes()).hexdigest()!=manifest['training_record_sha256']:raise ValueError('Export hash changed')
    if (directory/'valid.jsonl').exists() or (directory/'test.jsonl').exists():raise ValueError('No fabricated partial-dev targets or test contents')
    capacity=json.loads((ROOT/'evaluation/medfacts-v1/capacity.json').read_text())
    if capacity.get('status')!='observed_success' or capacity.get('optimizer_steps')!=0:raise ValueError('Actual-length capacity probe must pass first')
    baseline=json.loads((ROOT/'evaluation/medfacts-v1/untuned-baseline.json').read_text())
    from scripts.medfacts import MODEL
    if baseline['model']!=MODEL or baseline['contract_hashes']!=hashes() or not baseline['finished']:raise ValueError('Frozen untuned baseline must finish first')
    if len(records)!=2:raise ValueError('This bounded pilot is pinned to two approved families')
    return records,capacity


def run(directory,output):
    records,capacity=preflight(directory)
    if output.exists() or not any(output.resolve().is_relative_to(ROOT/p) for p in ['private','.runtime']):raise ValueError('Fresh private/runtime output required')
    os.environ['HF_HUB_OFFLINE']='1'
    import httpx
    with httpx.Client(trust_env=False,timeout=5) as c:assert c.get('http://127.0.0.1:11434/api/ps').json()['models']==[],'Defer until inference idle/unloaded'
    base=ROOT/'.runtime/pipeline4b/base';pins=json.loads((ROOT/'evaluation/pipeline4b-smoke/pins.json').read_text())
    from scripts.training_prepare import check_versions
    check_versions(pins['versions'])
    for n,e in json.loads((ROOT/'evaluation/pipeline4b-smoke/download.json').read_text())['files'].items():
        with (base/n).open('rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==e['sha256']
    import mlx.core as mx
    import mlx.nn as nn
    import mlx.optimizers as optim
    from mlx.utils import tree_flatten
    from mlx_lm.utils import load
    from mlx_lm.tuner.utils import linear_to_lora_layers
    from mlx_lm.tuner.trainer import grad_checkpoint
    from transformers import AutoTokenizer
    tok=AutoTokenizer.from_pretrained(base,local_files_only=True,trust_remote_code=False)
    data=[checked_tokens(r,tok,capacity['maximum']) for r in records]
    mx.set_memory_limit(8*1024**3);mx.set_cache_limit(128*1024**2);mx.random.seed(42)
    output.mkdir(parents=True);model,_=load(str(base));model.freeze()
    config={'num_layers':1,'fine_tune_type':'lora','lora_parameters':{'rank':2,'scale':4.,'dropout':0.,'keys':['self_attn.q_proj','self_attn.v_proj']}}
    linear_to_lora_layers(model,1,config['lora_parameters']);grad_checkpoint(model.layers[0]);optimizer=optim.Adam(learning_rate=1e-5);loss_fn=nn.value_and_grad(model,completion_loss);model.train()
    report={'base_revision':pins['training_revision'],'export_manifest':json.loads((directory/'manifest.json').read_text()),'versions':pins['versions'],'lora_config':config,'learning_rate':1e-5,'batch_size':1,'seed':42,'capacity_maximum':capacity['maximum'],'purpose':'diagnostic quality pilot, not validation','contract_hashes':hashes(),'max_steps':4,'passes':2,'steps':[],'checkpoints':[0],'development_loss_available':False,'selection':'untuned step zero retained; candidate selection pending matched semantic reports','clinical_candidate_eligible':False}
    for step in range(1,5):
        tokens,offset=data[(step-1)%len(data)];(loss,count),grad=loss_fn(model,mx.array([tokens]),mx.array([[offset,len(tokens)]]))
        mx.eval(loss,grad)
        if not math.isfinite(float(loss)) or not all(bool(mx.all(mx.isfinite(g))) for _,g in tree_flatten(grad)):raise RuntimeError('Nonfinite loss/gradient; no update applied')
        optimizer.update(model,grad);mx.eval(model.parameters(),optimizer.state)
        report['steps'].append({'step':step,'loss':float(loss),'full_tokens':len(tokens),'completion_tokens':int(count)})
        if step in [2,4]:
            checkpoint=output/f'step-{step}';checkpoint.mkdir();mx.save_safetensors(str(checkpoint/'adapters.safetensors'),dict(tree_flatten(model.trainable_parameters())));(checkpoint/'adapter_config.json').write_text(json.dumps(config,indent=2)+'\n');report['checkpoints'].append(step);report.setdefault('adapter_sha256',{})[str(step)]=hashlib.sha256((checkpoint/'adapters.safetensors').read_bytes()).hexdigest()
        (output/'pilot.json').write_text(json.dumps(report,indent=2)+'\n');mx.clear_cache()
    report['mlx_peak_memory_bytes']=mx.get_peak_memory();report['completed_steps']=4;(output/'pilot.json').write_text(json.dumps(report,indent=2)+'\n')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('directory',type=Path);p.add_argument('--output',type=Path,required=True);p.add_argument('--run-quality-pilot',action='store_true',required=True);a=p.parse_args();run(a.directory,a.output)
