"""Later explicit opt-in: bounded reviewed A-v2 experiment. Not used by this milestone."""
import argparse,hashlib,json,math,os
from pathlib import Path
from scripts.role_review import validate
from scripts.medication_experiment import ROOT,request
from scripts.training_tokens import checked_tokens,completion_loss

def run(directory,output):
 os.environ['HF_HUB_OFFLINE']='1'
 if output.exists() or not any(output.resolve().is_relative_to(ROOT/x) for x in ['private','.runtime']):raise ValueError('Fresh private/runtime output required')
 registry=json.loads((directory/'families.json').read_text());rows=validate(json.loads((directory/'corrections.json').read_text()),registry)
 if not any(r['split']=='test' for r in registry):raise ValueError('Reserved-test family metadata required')
 if any(not any(r['split']==s and r['review_status']=='reviewed' for r in rows) for s in ['train','development']):raise ValueError('Reviewed train and development required')
 if (directory/'test.jsonl').exists():raise ValueError('No held-out test file in training directory')
 pins=json.loads((ROOT/'evaluation/pipeline4b-smoke/pins.json').read_text());download=json.loads((ROOT/'evaluation/pipeline4b-smoke/download.json').read_text());base=ROOT/'.runtime/pipeline4b/base'
 assert download['revision']==pins['training_revision']
 for name,entry in download['files'].items():
  with (base/name).open('rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==entry['sha256']
 from scripts.training_prepare import check_versions
 check_versions(pins['versions'])
 import mlx.core as mx
 import mlx.optimizers as optim
 from mlx.utils import tree_flatten
 from mlx_lm.utils import load
 from mlx_lm.tuner.utils import linear_to_lora_layers
 from mlx_lm.tuner.trainer import train,evaluate,TrainingArgs
 from transformers import AutoTokenizer
 tok=AutoTokenizer.from_pretrained(base,local_files_only=True,trust_remote_code=False);datasets=[];lengths=[]
 for split,name in [('train','train.jsonl'),('development','valid.jsonl')]:
  expected=[]
  for row in rows:
   if row['split']==split and row['review_status']=='reviewed':
    req,_=request('A',row['source_note'],2);expected.append({'messages':req['messages']+[{'role':'assistant','content':json.dumps(row['labels'],ensure_ascii=False,separators=(',',':'))}]})
  records=[json.loads(x) for x in (directory/name).read_text().splitlines()];assert records==expected,'Export changed since review'
  data=[checked_tokens(r,tok) for r in records];lengths += [len(t) for t,o in data];datasets.append(data)
 # This is a deliberate capacity bound, never a truncation rule.
 if max(lengths)>4096:raise ValueError('Full sequence exceeds verified preparation range; re-budget memory, never truncate')
 import httpx
 with httpx.Client(trust_env=False,timeout=5) as c:
  assert not c.get('http://127.0.0.1:11434/api/ps').json()['models'],'Defer while another model is resident'
 mx.set_memory_limit(8*1024**3);mx.set_cache_limit(128*1024**2);mx.random.seed(42)
 output.mkdir(parents=True);model,_=load(str(base));model.freeze();config={'num_layers':1,'fine_tune_type':'lora','lora_parameters':{'rank':2,'scale':4.0,'dropout':0.0,'keys':['self_attn.q_proj','self_attn.v_proj']}}
 linear_to_lora_layers(model,1,config['lora_parameters']);(output/'adapter_config.json').write_text(json.dumps(config,indent=2))
 best=output/'development-selected';best.mkdir();(best/'adapter_config.json').write_text(json.dumps(config,indent=2))
 class Selection:
  best_loss=float('inf')
  def on_train_loss_report(self,info):self.record('train',info)
  def record(self,kind,info):
   with (output/'metrics.jsonl').open('a') as f:f.write(json.dumps({'kind':kind,**info})+'\n')
  def on_val_loss_report(self,info):
   self.record('development',info);value=info['val_loss'];assert math.isfinite(value)
   if value<self.best_loss:
    self.best_loss=value;mx.save_safetensors(str(best/'adapters.safetensors'),dict(tree_flatten(model.trainable_parameters())));(best/'selection.json').write_text(json.dumps({**info,'criterion':'reviewed development completion loss','clinical_quality_claim':None},indent=2))
 select=Selection();args=TrainingArgs(batch_size=1,iters=5,val_batches=-1,steps_per_report=1,steps_per_eval=1,steps_per_save=1,max_seq_length=((max(lengths)+31)//32)*32,grad_checkpoint=True,adapter_file=output/'adapters.safetensors')
 (output/'provenance.json').write_text(json.dumps({'pins':pins,'lengths':lengths,'steps':5,'clinical_candidate_eligible':False,'reviewed_input_sha256':hashlib.sha256((directory/'corrections.json').read_bytes()).hexdigest()},indent=2))
 train(model,optim.Adam(learning_rate=1e-5),datasets[0],datasets[1],args=args,loss=completion_loss,training_callback=select)
 model.eval();loss=evaluate(model,datasets[1],batch_size=1,num_batches=-1,max_seq_length=args.max_seq_length,loss=completion_loss);select.on_val_loss_report({'iteration':5,'val_loss':loss})
 (output/'complete.json').write_text(json.dumps({'steps':5,'peak_memory_bytes':mx.get_peak_memory(),'selection':'development-selected; iteration zero may win','clinical_quality_claim':None},indent=2))

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('directory',type=Path);p.add_argument('--output',type=Path,required=True);p.add_argument('--run-reviewed-experiment',action='store_true',required=True);a=p.parse_args();run(a.directory.resolve(),a.output.resolve())
