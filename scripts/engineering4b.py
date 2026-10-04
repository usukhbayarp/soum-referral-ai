"""Three-step, fictional PIPELINE TEST ONLY. Bypasses no clinical review gate.
Separate directory and manifest, never eligible for clinical candidate promotion.
"""
import argparse, hashlib, json, math, os, subprocess, time
from pathlib import Path
from scripts.medication_experiment import ROOT, request, model_view, validate_output
from scripts.training_tokens import checked_tokens, completion_loss, NonThinkingTokenizer

OUT=ROOT/'evaluation/pipeline4b-smoke'

def run():
    os.environ['HF_HUB_OFFLINE']='1'
    import mlx.core as mx
    import mlx.nn as nn
    import mlx.optimizers as optim
    from mlx.utils import tree_flatten, tree_unflatten
    from mlx_lm.utils import load
    from mlx_lm.tuner.utils import linear_to_lora_layers
    from mlx_lm import generate
    from mlx_lm.sample_utils import make_sampler
    base=ROOT/'.runtime/pipeline4b/base';out=ROOT/'.runtime/pipeline4b/smoke'
    if out.exists(): raise ValueError('Never overwrite a smoke run')
    manifest=json.loads((OUT/'download.json').read_text());assert manifest['status']=='verified'
    for name,entry in manifest['files'].items():
        with (base/name).open('rb') as f: assert hashlib.file_digest(f,'sha256').hexdigest()==entry['sha256']
    assert json.loads(subprocess.check_output(['curl','-fsS','http://127.0.0.1:11434/api/ps']))['models']==[], 'Defer while an Ollama model is resident; do not stop user work'
    out.mkdir();start=time.monotonic();mx.set_memory_limit(8*1024**3);mx.set_cache_limit(128*1024**2);mx.random.seed(42)
    report={'purpose':'engineering-smoke-only','clinical_candidate_eligible':False,'clinician_review_status':'unreviewed','steps':[],'source':manifest,'stages':{},'limits':{'steps':3,'batch_size':1,'rank':2,'last_layers':1,'keys':['self_attn.q_proj','self_attn.v_proj'],'mlx_memory_limit_bytes':8*1024**3,'max_output_tokens':32},'training_quality_claim':None}
    def save(stage):
        report['last_stage']=stage;report['elapsed_seconds']=time.monotonic()-start;report['mlx_peak_memory_bytes']=mx.get_peak_memory();(OUT/'smoke-result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    try:
        model,tok=load(str(base),tokenizer_config={'trust_remote_code':False});mx.eval(model.parameters());report['stages']['load']='observed_success';save('load')
        fixture=json.loads((ROOT/'training/engineering4b-fixture.json').read_text());req,mapping=request('A',fixture['source_note'],2);validate_output('A',json.dumps(fixture['labels']),mapping)
        record={'messages':req['messages']+[{'role':'assistant','content':json.dumps(fixture['labels'],ensure_ascii=False,separators=(',',':'))}]}
        tokens,offset=checked_tokens(record,tok,4096);report['sequence']={'full_tokens':len(tokens),'prompt_tokens':offset,'completion_tokens':len(tokens)-offset,'truncated':False,'completion_mask_verified':True};report['fixture_sha256']=hashlib.sha256((ROOT/'training/engineering4b-fixture.json').read_bytes()).hexdigest()
        model.freeze();config={'num_layers':1,'fine_tune_type':'lora','lora_parameters':{'rank':2,'scale':4.0,'dropout':0.0,'keys':['self_attn.q_proj','self_attn.v_proj']}}
        linear_to_lora_layers(model,1,config['lora_parameters']);mx.eval(model.parameters())
        initial={k:mx.array(v) for k,v in tree_flatten(model.trainable_parameters())};mx.eval(initial)
        mx.save_safetensors(str(out/'initial.safetensors'),initial)
        opt=optim.Adam(learning_rate=1e-5);loss_fn=nn.value_and_grad(model,completion_loss);batch=mx.array([tokens]);lengths=mx.array([[offset,len(tokens)]])
        model.train()
        for step in range(1,4):
            (loss,count),grad=loss_fn(model,batch,lengths);opt.update(model,grad);mx.eval(model.parameters(),opt.state,loss)
            value=float(loss);assert math.isfinite(value)
            changed={k:float(mx.max(mx.abs(v-initial[k]))) for k,v in tree_flatten(model.trainable_parameters())}
            report['steps'].append({'optimizer_step':step,'loss':value,'completion_tokens_in_loss':int(count),'adapter_max_abs_delta':changed})
            assert any(v>0 for v in changed.values());save('optimizer_step_'+str(step));mx.clear_cache()
            pressure=subprocess.check_output(['memory_pressure'],text=True).split('System-wide memory free percentage:')[-1].strip().rstrip('%')
            if int(pressure)<10:raise RuntimeError('Stopping safely: system free-memory metric below 10%')
        model.eval();trained=dict(tree_flatten(model.trainable_parameters()));mx.eval(trained);mx.save_safetensors(str(out/'adapters.safetensors'),trained);(out/'adapter_config.json').write_text(json.dumps(config,indent=2));report['stages']['optimizer']='observed_success_3_steps';save('saved_nonzero_adapter')
        # Release the first base before reloading. Preserve only small trained tensors.
        del model,opt,grad,loss_fn,batch;mx.clear_cache()
        model,tok=load(str(base),adapter_path=str(out),tokenizer_config={'trust_remote_code':False});mx.eval(model.parameters())
        loaded=dict(tree_flatten(model.parameters()));assert set(trained)<=set(loaded)
        assert all(bool(mx.array_equal(loaded[k],trained[k])) for k in trained);report['stages']['reload']='observed_success';save('reload')
        prompt=NonThinkingTokenizer(tok).apply_chat_template(req['messages'],add_generation_prompt=True,tokenize=False)
        answer=generate(model,tok,prompt=prompt,max_tokens=32,sampler=make_sampler(temp=0),verbose=False)
        report['adapter_inference']={'output':answer,'max_tokens':32,'note':'Execution test only; may be incomplete JSON, not a clinical extraction score'};report['stages']['adapter_inference']='observed_success';save('adapter_inference')
        # Apply the installed fusion implementation to actual trained modules.
        fused=[];checks=[]
        for name,module in model.named_modules():
            if not hasattr(module,'fuse'):continue
            original=module.linear
            w=mx.dequantize(original.weight,original.scales,original.biases,group_size=original.group_size,bits=original.bits,mode=original.mode)
            target=module.fuse(dequantize=True);mx.eval(target.parameters());delta=float(mx.max(mx.abs(target.weight-w)));assert delta>0
            expected=w+((module.scale*module.lora_b.T)@module.lora_a.T).astype(w.dtype)
            assert bool(mx.array_equal(expected,target.weight));checks.append({'module':name,'max_abs_weight_delta':delta,'fusion_formula_equal':True});fused.append((name,target))
        assert checks;model.update_modules(tree_unflatten(fused));report['fusion_checks']=checks;report['stages']['adapter_layer_fusion']='observed_success';save('adapter_layer_fusion')
        # Full HF/F16 artifacts are separately disk-gated; no unsupported MLX GGUF exporter.
        report['stages']['full_dequantized_export']='not_attempted_disk_budget';report['adapter_bytes']=(out/'adapters.safetensors').stat().st_size;report['adapter_sha256']=hashlib.sha256((out/'adapters.safetensors').read_bytes()).hexdigest();save('completed_bounded_smoke')
    except Exception as exc:
        report['failure']={'type':type(exc).__name__,'message':str(exc)};save('failed');raise

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--engineering-smoke-only',action='store_true',required=True);p.parse_args();run()
