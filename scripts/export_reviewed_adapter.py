"""Future adapter export: enumerate ALL LoRA targets against the pinned control HF.
No full-model dequantization or alternate serializer. Existing safetensors headers,
shapes/dtypes/index are preserved and every tensor is verified after byte replacement.
"""
import argparse, hashlib, json, os, shutil, struct, time
from pathlib import Path
from scripts.medication_experiment import ROOT

OLD=ROOT/'evaluation/pipeline4b-smoke'
OUT=ROOT/'evaluation/clinician-partial-v08'
RUNTIME=ROOT/'.runtime/recovery-v08'
CONTROL=ROOT/'.runtime/pipeline4b/control-temporary-60llz6wf/hf'


def sha(path):
    with Path(path).open('rb') as f: return hashlib.file_digest(f,'sha256').hexdigest()


def header(path):
    with Path(path).open('rb') as f:
        n=struct.unpack('<Q',f.read(8))[0]
        if n>100*1024**2: raise ValueError('Unexpected header size')
        h=json.loads(f.read(n))
    return n+8,{k:v for k,v in h.items() if k!='__metadata__'}


def tensor_hash(path,offset,entry):
    a,b=entry['data_offsets'];h=hashlib.sha256()
    with Path(path).open('rb') as f:
        f.seek(offset+a);left=b-a
        while left:
            data=f.read(min(left,1024**2))
            if not data: raise ValueError('Truncated tensor')
            h.update(data);left-=len(data)
    return h.hexdigest()


def replace_tensor(destination,name,patch):
    offset,h=header(destination);po,ph=header(patch)
    a,b=h[name]['data_offsets'];pa,pb=ph[name]['data_offsets']
    if h[name]['shape']!=ph[name]['shape'] or h[name]['dtype']!=ph[name]['dtype'] or b-a!=pb-pa:
        raise ValueError('Tensor shape/dtype/size mismatch')
    with Path(patch).open('rb') as src,Path(destination).open('r+b') as dst:
        src.seek(po+pa);dst.seek(offset+a);left=b-a
        while left:
            chunk=src.read(min(left,1024**2))
            if not chunk: raise ValueError('Truncated replacement')
            dst.write(chunk);left-=len(chunk)


def patches():
    os.environ['HF_HUB_OFFLINE']='1'
    import mlx.core as mx
    import mlx.nn as nn
    from mlx_lm.tuner.lora import LoRALinear
    mx.set_memory_limit(8*1024**3);mx.set_cache_limit(128*1024**2)
    RUNTIME.mkdir(exist_ok=True)
    target=RUNTIME/'fused-adapter-tensors.safetensors'
    if target.exists():raise FileExistsError(target)
    from scripts.training_prepare import check_versions
    check_versions(json.loads((OLD/'pins.json').read_text())['versions'])
    if (OUT/'targeted-fusion.json').exists():raise FileExistsError(OUT/'targeted-fusion.json')
    start=time.monotonic();base=ROOT/'.runtime/pipeline4b/base';adapter=ADAPTER
    assert sha(adapter/'adapters.safetensors')==ADAPTER_SHA
    for n,e in json.loads((OLD/'download.json').read_text())['files'].items():assert sha(base/n)==e['sha256']
    # Extract every adapted quantized layer, never initialize/load the full 4B model.
    config=json.loads((adapter/'adapter_config.json').read_text())['lora_parameters']
    adapter_weights=mx.load(str(adapter/'adapters.safetensors'))
    names=adapter_modules(adapter_weights)
    selected=[n+'.'+k for n in names for k in ('weight','scales','biases')]
    off,entries=header(base/'model.safetensors');new_header={};position=0
    dense_bytes=sum(entries[n+'.weight']['shape'][0]*entries[n+'.weight']['shape'][1]*8*2 for n in names)
    if dense_bytes>256*1024**2:raise ValueError('All adapter targets enumerated; BF16 patch set exceeds conservative 256 MiB buffer budget. Extend streaming export before this adapter.')
    for key in selected:
        e=entries[key];size=e['data_offsets'][1]-e['data_offsets'][0]
        new_header[key]={**e,'data_offsets':[position,position+size]};position+=size
    encoded=json.dumps(new_header,separators=(',',':')).encode();encoded+=b' '*((-len(encoded))%8)
    small=RUNTIME/'adapted-base-layers.safetensors'
    with small.open('xb') as dst,(base/'model.safetensors').open('rb') as src:
        dst.write(struct.pack('<Q',len(encoded)));dst.write(encoded)
        for key in selected:
            a,b=entries[key]['data_offsets'];src.seek(off+a);dst.write(src.read(b-a))
    tensors=mx.load(str(small));weights={};checks=[]
    index=json.loads((CONTROL/'model.safetensors.index.json').read_text())['weight_map']
    for name in names:
        packed=tensors[name+'.weight'];output_dims,input_dims=packed.shape[0],packed.shape[1]*8
        linear=nn.QuantizedLinear(input_dims,output_dims,bias=False,group_size=128,bits=4,mode='affine')
        for key in ('weight','scales','biases'):linear[key]=tensors[name+'.'+key]
        module=LoRALinear.from_base(linear,r=config['rank'],scale=config['scale'],dropout=config['dropout'])
        module.lora_a=adapter_weights[name+'.lora_a'];module.lora_b=adapter_weights[name+'.lora_b']
        original=module.linear
        w=mx.dequantize(original.weight,original.scales,original.biases,group_size=original.group_size,bits=original.bits,mode=original.mode)
        fused=module.fuse(dequantize=True).weight
        expected=w+((module.scale*module.lora_b.T)@module.lora_a.T).astype(w.dtype)
        mx.eval(w,fused,expected)
        assert bool(mx.array_equal(expected,fused))
        key=name+'.weight';weights[key]=fused
        # Verify the existing BF16 control tensor really is this same base dequantization.
        proof=RUNTIME/(key+'.base.safetensors');mx.save_safetensors(str(proof),{key:w})
        off,h=header(CONTROL/index[key]);po,ph=header(proof)
        assert h[key]['dtype']==ph[key]['dtype']=='BF16' and h[key]['shape']==ph[key]['shape']
        assert tensor_hash(CONTROL/index[key],off,h[key])==tensor_hash(proof,po,ph[key])
        checks.append({'name':key,'shape':list(fused.shape),'dtype':str(fused.dtype),'max_abs_delta':float(mx.max(mx.abs(fused-w))),'fusion_formula_equal':True,'control_base_tensor_equal':True})
    assert len(weights)==len(names)
    mx.save_safetensors(str(target),weights)
    (OUT/'targeted-fusion.json').write_text(json.dumps({'checks':checks,'patch_sha256':sha(target),'mlx_peak_memory_bytes':mx.get_peak_memory(),'elapsed_seconds':time.monotonic()-start,'adapter_sha256':sha(adapter/'adapters.safetensors'),'clinical_candidate_eligible':False},indent=2)+'\n')


def export():
    start=time.monotonic();destination=RUNTIME/'candidate-hf'
    if (OUT/'sparse-hf-export.json').exists():raise FileExistsError(OUT/'sparse-hf-export.json')
    if destination.exists():raise FileExistsError(destination)
    manifest=json.loads((OLD/'control-hf.json').read_text())
    for n,e in manifest['files'].items():assert sha(CONTROL/n)==e['sha256']
    patch=RUNTIME/'fused-adapter-tensors.safetensors';targeted=json.loads((OUT/'targeted-fusion.json').read_text());assert sha(patch)==targeted['patch_sha256']
    assert targeted['adapter_sha256']==ADAPTER_SHA==sha(ADAPTER/'adapters.safetensors')
    # Existing control GGUF/HF/base/adapter are reused: one new HF + F16 + Q4 +
    # conservative Ollama blob copy + 2 GiB reserve, no second control pipeline.
    required=2*8044936192+2*2497280320+2*1024**3
    free=shutil.disk_usage(ROOT).free
    if free<required:raise RuntimeError(f'Need {required} free bytes; have {free}')
    destination.mkdir()
    for path in CONTROL.iterdir():
        if path.is_file():shutil.copyfile(path,destination/path.name)
    index=json.loads((destination/'model.safetensors.index.json').read_text())['weight_map']
    _,ph=header(patch)
    for name in ph:replace_tensor(destination/index[name],name,patch)
    seen=set();changes=[]
    for shard in sorted(set(index.values())):
        co,ch=header(CONTROL/shard);so,sh=header(destination/shard)
        assert ch==sh and co==so
        for name,entry in sh.items():
            assert index[name]==shard and name not in seen;seen.add(name)
            a=tensor_hash(CONTROL/shard,co,entry);b=tensor_hash(destination/shard,so,entry)
            if name in ph:
                po,_=header(patch);assert b==tensor_hash(patch,po,ph[name]);
                if a!=b:changes.append(name)
            else:assert a==b
    assert seen==set(index) and set(changes)<=set(ph)
    files={p.name:{'sha256':sha(p),'bytes':p.stat().st_size} for p in destination.iterdir() if p.is_file()}
    (OUT/'sparse-hf-export.json').write_text(json.dumps({'status':'observed_success','clinical_candidate_eligible':False,'required_free_bytes_estimate':required,'free_bytes_before':free,'free_bytes_after':shutil.disk_usage(ROOT).free,'elapsed_seconds':time.monotonic()-start,'tensor_count':len(seen),'adapted_tensors':list(ph),'changed_tensors':changes,'all_unchanged_tensors_byte_identical':True,'shapes_dtypes_headers_index_preserved':True,'files':files},indent=2)+'\n')


def adapter_modules(weights):
    names={}
    for key in weights:
        name,suffix=key.rsplit('.',1)
        if suffix not in ['lora_a','lora_b']:raise ValueError('Unsupported adapter parameter; do not silently skip: '+key)
        names.setdefault(name,set()).add(suffix)
    if not names or any(v!={'lora_a','lora_b'} for v in names.values()):raise ValueError('Every adapter module needs both A and B')
    return sorted(names)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('stage',choices=['patches','export']);p.add_argument('--adapter',required=True,type=Path);p.add_argument('--adapter-sha256',required=True);p.add_argument('--work',required=True,type=Path);p.add_argument('--reports',required=True,type=Path);a=p.parse_args()
    ADAPTER=a.adapter.resolve();ADAPTER_SHA=a.adapter_sha256;RUNTIME=a.work.resolve();OUT=a.reports.resolve()
    if any(not any(path.is_relative_to(ROOT/x) for x in ['.runtime','private']) for path in [ADAPTER,RUNTIME,OUT]):raise ValueError('Use private/runtime paths for future adapters')
    OUT.mkdir(parents=True,exist_ok=True);RUNTIME.parent.mkdir(parents=True,exist_ok=True)
    (patches if a.stage=='patches' else export)()
