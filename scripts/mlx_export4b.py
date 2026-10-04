"""Same BF16 export path for pinned untuned control and engineering-only step-3 adapter."""
import argparse,hashlib,json,os,time
from pathlib import Path
from scripts.medication_experiment import ROOT

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--kind',choices=['control','smoke'],required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
 if a.output.exists() or a.report.exists():raise FileExistsError('Preserve existing outputs')
 os.environ['HF_HUB_OFFLINE']='1'
 import mlx.core as mx
 from mlx.utils import tree_unflatten
 from mlx_lm.utils import load,dequantize_model,save
 mx.set_memory_limit(12*1024**3);mx.set_cache_limit(128*1024**2)
 base=ROOT/'.runtime/pipeline4b/base';start=time.monotonic()
 source=json.loads((ROOT/'evaluation/pipeline4b-smoke/download.json').read_text())
 for n,e in source['files'].items():
  with (base/n).open('rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==e['sha256']
 adapter=ROOT/'.runtime/pipeline4b/smoke' if a.kind=='smoke' else None
 if adapter:
  result=json.loads((ROOT/'evaluation/pipeline4b-smoke/smoke-result.json').read_text())
  with (adapter/'adapters.safetensors').open('rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==result['adapter_sha256']
 model,tok,config=load(str(base),adapter_path=str(adapter) if adapter else None,return_config=True)
 fused=[(n,m.fuse(dequantize=True)) for n,m in model.named_modules() if hasattr(m,'fuse')]
 assert len(fused)==(2 if adapter else 0)
 model.update_modules(tree_unflatten(fused));model=dequantize_model(model);config.pop('quantization',None);config.pop('quantization_config',None)
 save(a.output,base,model,tok,config,donate_model=True)
 files={}
 for path in a.output.iterdir():
  if path.is_file():
   with path.open('rb') as f:files[path.name]={'sha256':hashlib.file_digest(f,'sha256').hexdigest(),'bytes':path.stat().st_size}
 a.report.write_text(json.dumps({'kind':a.kind,'clinical_candidate_eligible':False,'source_revision':source['revision'],'adapter_applied':bool(adapter),'fused_modules':[n for n,m in fused],'output_precision':'BF16','mlx_peak_memory_bytes':mx.get_peak_memory(),'elapsed_seconds':time.monotonic()-start,'files':files},indent=2)+'\n')

if __name__=='__main__':main()
