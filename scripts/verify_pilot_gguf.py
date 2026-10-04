"""Bounded verification of this pilot's F16 conversion or Q4 tensor changes."""
import argparse,hashlib,json,sys
from pathlib import Path
from scripts.export_reviewed_adapter import header,sha

def verify(stage,work,report):
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'.runtime/preparation/llama.cpp/gguf-py'))
    import numpy as np
    from gguf import GGUFReader,MODEL_ARCH,get_tensor_name_map
    if report.exists():raise FileExistsError(report)
    path=work/('candidate-F16.gguf' if stage=='f16' else 'candidate-Q4_K_M.gguf')
    reader=GGUFReader(str(path));right={t.name:t for t in reader.tensors};changes=[]
    if stage=='f16':
        hf=work/'candidate-hf';index=json.loads((hf/'model.safetensors.index.json').read_text())['weight_map'];names=get_tensor_name_map(MODEL_ARCH.QWEN3,36);seen=set()
        for name,shard in index.items():
            target=names.get_name(name,try_suffixes=('.weight','.bias'));assert target in right and target not in seen;seen.add(target)
            offset,entries=header(hf/shard);entry=entries[name];tensor=right[target]
            assert list(tensor.shape)==list(reversed(entry['shape'])) and entry['dtype']=='BF16'
            a,b=entry['data_offsets'];actual=tensor.data.reshape(-1);position=0
            with (hf/shard).open('rb') as src:
                src.seek(offset+a);left=b-a
                while left:
                    raw=src.read(min(left,2*1024**2));assert raw
                    floats=(np.frombuffer(raw,dtype='<u2').astype(np.uint32)<<16).view(np.float32).astype(actual.dtype)
                    assert np.array_equal(floats,actual[position:position+len(floats)]),name
                    left-=len(raw);position+=len(floats)
            assert position==actual.size
        assert seen==set(right)
    else:
        control=Path('.runtime/pipeline4b/control-Q4_K_M.gguf')
        pin=json.loads(Path('evaluation/clinician-partial-v08/quantized-delta.json').read_text())['files'][0]
        assert str(control)==pin['path'] and sha(control)==pin['sha256']
        left={t.name:t for t in GGUFReader(str(control)).tensors}
        assert left.keys()==right.keys()
        for name,a in left.items():
            b=right[name];assert a.tensor_type==b.tensor_type and np.array_equal(a.shape,b.shape)
            ah,bh=hashlib.sha256(a.data).hexdigest(),hashlib.sha256(b.data).hexdigest()
            if ah!=bh:changes.append({'name':name,'control_sha256':ah,'candidate_sha256':bh})
    if stage=='q4':
        _,adapted=header(work/'fused-adapter-tensors.safetensors');names=get_tensor_name_map(MODEL_ARCH.QWEN3,36)
        allowed={names.get_name(n,try_suffixes=('.weight',)) for n in adapted}
        assert {c['name'] for c in changes}<=allowed,'Unexpected changes outside adapted tensors'
    result={'stage':stage,'tensor_count':len(right),'all_f16_values_match_hf':stage=='f16','changed_tensors_vs_control':changes,'path':str(path),'sha256':sha(path),'bytes':path.stat().st_size,'clinical_quality_inferred':False}
    report.write_text(json.dumps(result,indent=2)+'\n');print(stage,'verified',len(right),'tensors;',len(changes),'quantized changes')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['f16','q4']);p.add_argument('--work',required=True,type=Path);p.add_argument('--report',required=True,type=Path);a=p.parse_args();verify(a.stage,a.work,a.report)
