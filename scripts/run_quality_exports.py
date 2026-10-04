"""Execute this authorized four-step pilot's two sequential exports/evaluations once.
Only new candidate HF shards/F16 intermediates may be removed after verification.
"""
import hashlib,json,shutil,subprocess,time
from pathlib import Path
import httpx
from scripts.export_reviewed_adapter import sha
from scripts.watched_job import run as watched
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'evaluation/quality-medfacts-pilot1'
VENV=str(ROOT/'.venv/bin/python')
MLX='/opt/anaconda3/bin/python'
CONVERTER=str(ROOT/'.runtime/preparation/converter-env/bin/python')
LLAMA=ROOT/'.runtime/preparation/llama.cpp'

def disk(required):
    free=shutil.disk_usage(ROOT).free
    if free<required:raise RuntimeError(f'Disk guard: {free} < {required}')
    return free

def stage(step,name,command,required=2*1024**3):
    record={'command':command,'disk_free_before':disk(required),'start_unix':time.time()}
    dest=OUT/f'step{step}-{name}-watch.json'
    (OUT/f'step{step}-{name}-command.json').write_text(json.dumps(record,indent=2)+'\n')
    print(f'Step {step}: {name}',flush=True);watched(command,dest)

def cleanup(step,paths,downstream,manifest):
    # Exact allowlist, no directory deletion, no historical paths.
    work=ROOT/f'.runtime/quality-medfacts-v1-step{step}'
    allowed={work/'candidate-hf'/n for n in manifest.get('files',{}) if n.endswith('.safetensors')}
    allowed.add(work/'candidate-F16.gguf')
    if any(p not in allowed or p.is_symlink() for p in paths):raise ValueError('Cleanup outside explicit new pilot intermediates')
    assert sha(Path(downstream['path']))==downstream['sha256']
    entries=[]
    for p in paths:
        digest=sha(p)
        expected=manifest['files'][p.name]['sha256'] if p.suffix=='.safetensors' else manifest['sha256']
        assert digest==expected
        entries.append({'path':str(p.relative_to(ROOT)),'sha256':digest,'bytes':p.stat().st_size})
    report={'downstream_verified':downstream,'deleted':entries,'disk_free_before':disk(0),'status':'authorized_pending'}
    dest=OUT/f'step{step}-cleanup-{"hf" if paths[0].suffix==".safetensors" else "f16"}.json'
    if dest.exists():raise FileExistsError(dest)
    dest.write_text(json.dumps(report,indent=2)+'\n')
    for p in paths:p.unlink()
    report.update(status='completed',disk_free_after=disk(0));dest.write_text(json.dumps(report,indent=2)+'\n')

def main(resume_step2=False):
    plan=json.loads((OUT/'preflight.json').read_text());pilot=ROOT/'.runtime/quality-medfacts-v1-pilot';training=json.loads((pilot/'pilot.json').read_text())
    assert training['completed_steps']==4 and training['checkpoint_reload_verified']==[2,4]
    assert subprocess.check_output(['git','-C',str(LLAMA),'rev-parse','HEAD'],text=True).strip()==plan['converter_revision']
    for step in [2,4]:
        adapter=pilot/f'step-{step}';digest=sha(adapter/'adapters.safetensors');assert digest==training['adapter_sha256'][str(step)]
        work=ROOT/f'.runtime/quality-medfacts-v1-step{step}';reports=ROOT/f'.runtime/quality-medfacts-v1-step{step}-reports'
        resume=resume_step2 and step==2
        if not resume and (work.exists() or reports.exists()):raise FileExistsError('Fresh checkpoint paths required')
        if resume:
            assert json.loads((OUT/'step2-convert-watch.json').read_text())['exit_code']==0
            assert (work/'candidate-F16.gguf').exists() and not (reports/'f16.json').exists()
        common=['--adapter',str(adapter),'--adapter-sha256',digest,'--work',str(work),'--reports',str(reports)]
        if not resume:
            stage(step,'fusion',[MLX,'-m','scripts.mlx_python','scripts.export_reviewed_adapter','patches',*common])
            stage(step,'hf',[VENV,'-m','scripts.export_reviewed_adapter','export',*common],23*1024**3)
            stage(step,'convert',[CONVERTER,'-m','scripts.mlx_python','--script',str(LLAMA/'convert_hf_to_gguf.py'),str(work/'candidate-hf'),'--outfile',str(work/'candidate-F16.gguf'),'--outtype','f16'],11*1024**3)
        stage(step,'verify-f16-recovery' if resume else 'verify-f16',[CONVERTER,'-m','scripts.mlx_python','scripts.verify_pilot_gguf','f16','--work',str(work),'--report',str(reports/'f16.json')])
        hf=json.loads((reports/'sparse-hf-export.json').read_text());f16=json.loads((reports/'f16.json').read_text())
        cleanup(step,[work/'candidate-hf'/n for n in hf['files'] if n.endswith('.safetensors')],f16,hf)
        stage(step,'quantize',[str(LLAMA/'build/bin/llama-quantize'),str(work/'candidate-F16.gguf'),str(work/'candidate-Q4_K_M.gguf'),'Q4_K_M'],5*1024**3)
        stage(step,'verify-q4',[CONVERTER,'-m','scripts.mlx_python','scripts.verify_pilot_gguf','q4','--work',str(work),'--report',str(reports/'q4.json')])
        q4=json.loads((reports/'q4.json').read_text());cleanup(step,[work/'candidate-F16.gguf'],q4,f16)
        disk(5*1024**3);tag=f'soum-qwen3-4b-medfacts:pilot1-step{step}'
        subprocess.run([VENV,'-m','scripts.import_candidate','--gguf',str(work/'candidate-Q4_K_M.gguf'),'--tag',tag,'--output',str(reports/'import')],check=True)
        print(f'Step {step}: three development requests, one attempt each',flush=True)
        subprocess.run([VENV,'-m','scripts.medfacts_baseline','--model',tag,'--output',str(reports/'development.json')],check=True)
        evaluation=json.loads((reports/'development.json').read_text())
        for p in reports.glob('*.json'):shutil.copyfile(p,OUT/f'step{step}-{p.name}')
        shutil.copyfile(reports/'import/import.json',OUT/f'step{step}-import.json')
        if not evaluation['finished']:raise RuntimeError('Incomplete/timeout: do not start another heavy stage until owned request idle confirmed')
        # All owned requests completed; unload only this experimental tag via supported API.
        with httpx.Client(trust_env=False,timeout=30) as c:
            response=c.post('http://127.0.0.1:11434/api/generate',json={'model':tag,'keep_alive':0});response.raise_for_status()
            assert c.get('http://127.0.0.1:11434/api/ps').json()['models']==[]
        print(f'Step {step} complete, experimental model unloaded',flush=True)

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--resume-step2-after-convert',action='store_true');a=p.parse_args();main(a.resume_step2_after_convert)
