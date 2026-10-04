"""Measure all reviewed A-v2 chat sequences using installed MLX-LM; no training."""
import argparse,hashlib,json
from pathlib import Path
from transformers import AutoTokenizer
from scripts.training_tokens import checked_tokens
from scripts.role_review import validate
from scripts.medication_experiment import ROOT

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('directory',type=Path);p.add_argument('--model',type=Path,default=ROOT/'.runtime/pipeline4b/base');a=p.parse_args();d=a.directory.resolve()
 if not any(d.is_relative_to(ROOT/x) for x in ['private','.runtime']):p.error('Use private staged data')
 manifest=json.loads((d/'manifest.json').read_text());rows=validate(json.loads((d/'corrections.json').read_text()),json.loads((d/'families.json').read_text()))
 if not all(manifest['export_counts'].get(s,0)>0 for s in ['train','development']):p.error('Reviewed train/development export required')
 for path,digest in manifest['contract_sha256'].items():assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==digest,'Frozen prompt changed'
 tok=AutoTokenizer.from_pretrained(a.model,local_files_only=True,trust_remote_code=False);lengths=[]
 from scripts.medication_experiment import request
 for split,name in [('train','train.jsonl'),('development','valid.jsonl')]:
  expected=[]
  for row in rows:
   if row['split']==split and row['review_status']=='reviewed':
    req,_=request('A',row['source_note'],2);expected.append({'messages':req['messages']+[{'role':'assistant','content':json.dumps(row['labels'],ensure_ascii=False,separators=(',',':'))}]})
  records=[json.loads(x) for x in (d/name).read_text().splitlines()];assert records==expected,'Export differs from reviewed corrections'
  for i,record in enumerate(records):
   tokens,offset=checked_tokens(record,tok);lengths.append({'split':split,'index':i,'full_tokens':len(tokens),'prompt_tokens':offset,'completion_tokens':len(tokens)-offset})
 out=d/'token-preflight.json'
 if out.exists():raise FileExistsError(out)
 out.write_text(json.dumps({'lengths':lengths,'measured_max_seq_length':max(x['full_tokens'] for x in lengths),'truncation':False,'training_started':False,'capacity_test_required':True},indent=2)+'\n');print('Completion masking and full sequence lengths verified. No training started.')

if __name__=='__main__':main()
