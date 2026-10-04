"""Compare actual GGUF tensor bytes, ignoring metadata differences."""
import hashlib,json
from scripts.medication_experiment import ROOT
from gguf import GGUFReader

out=ROOT/'evaluation/clinician-partial-v08/quantized-delta.json'
if out.exists():raise FileExistsError(out)
paths=[ROOT/'.runtime/pipeline4b/control-Q4_K_M.gguf',ROOT/'.runtime/recovery-v08/smoke-Q4_K_M.gguf']
readers=[GGUFReader(str(p)) for p in paths]
left,right=[{t.name:t for t in r.tensors} for r in readers]
assert left.keys()==right.keys();changes=[]
for name,a in left.items():
    b=right[name];assert a.tensor_type==b.tensor_type and (a.shape==b.shape).all()
    ha,hb=hashlib.sha256(a.data).hexdigest(),hashlib.sha256(b.data).hexdigest()
    if ha!=hb:changes.append({'name':name,'control_sha256':ha,'smoke_sha256':hb,'tensor_type':str(a.tensor_type)})
files=[]
for p in paths:
    with p.open('rb') as f:files.append({'path':str(p.relative_to(ROOT)),'bytes':p.stat().st_size,'sha256':hashlib.file_digest(f,'sha256').hexdigest()})
out.write_text(json.dumps({'tensor_count':len(left),'changed_tensor_count':len(changes),'changed_tensors':changes,'files':files,'interpretation':'Quantized weight bytes only; not an answer change or clinical-quality claim'},indent=2)+'\n')
