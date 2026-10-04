"""Disk-bounded export. Only this run's newly created temporary HF/F16 files are removed.
Pinned base, adapters, final GGUFs, imports and every prior artifact are preserved.
"""
import argparse,hashlib,json,os,shutil,subprocess,tempfile,time
from pathlib import Path
import httpx
from scripts.medication_experiment import ROOT

OUT=ROOT/'evaluation/pipeline4b-smoke'
RUNTIME=ROOT/'.runtime/pipeline4b'

def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--resume-control-hf',type=Path,help='Reuse and preserve verified HF output of an interrupted control export')
 parser.add_argument('--report-name',default='staged-export.json')
 args=parser.parse_args()
 if Path(args.report_name).name!=args.report_name:raise ValueError('Report name must be a filename')
 report_path=OUT/args.report_name
 if report_path.exists():raise FileExistsError(report_path)
 pins=json.loads((OUT/'pins.json').read_text());assert subprocess.check_output(['git','-C',str(ROOT/'.runtime/preparation/llama.cpp'),'rev-parse','HEAD'],text=True).strip()==pins['llama_cpp_revision']
 required=json.loads((OUT/'disk-budget.json').read_text())['sequential_intermediate_cleanup_peak_additional_bytes_estimate']-2137326367
 if shutil.disk_usage(ROOT).free<required:raise RuntimeError('Staged export disk budget not met')
 report={'purpose':'engineering-only','stages':[],'started_epoch':time.time(),'free_bytes_before':shutil.disk_usage(ROOT).free,'temporary_cleanup_policy':'Only freshly created HF/F16 intermediates, after hashes and successful Q4 verification; preserve failed intermediates.'}
 def save():report_path.write_text(json.dumps(report,indent=2)+'\n')
 def command(stage,args):
  record={'stage':stage,'command':args,'samples':[]};report['stages'].append(record);start=time.monotonic();save()
  with (RUNTIME/(report_path.stem+'-'+stage+'.log')).open('x') as log, httpx.Client(base_url='http://127.0.0.1:11434',trust_env=False,timeout=3) as c:
   assert not c.get('/api/ps').json()['models'],'Defer to other model work'
   child=subprocess.Popen(args,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,env={**os.environ,'PYTHONUNBUFFERED':'1'})
   try:
    while child.poll() is None:
     time.sleep(2)
     if child.poll() is not None:break
     pressure=subprocess.check_output(['sysctl','-n','kern.memorystatus_vm_pressure_level'],text=True).strip();rss=subprocess.check_output(['ps','-p',str(child.pid),'-o','rss='],text=True).strip()
     record['samples'].append({'seconds':round(time.monotonic()-start,2),'rss_kib':int(rss or 0),'pressure_level':pressure,'free_disk_bytes':shutil.disk_usage(ROOT).free})
     if pressure=='4' or int(rss or 0)>12*1024**2 or time.monotonic()-start>600 or c.get('/api/ps').json()['models']:
      record['guard_stop']=record['samples'][-1]
      raise RuntimeError('Pressure/contention/time guard stopped owned child')
    record['exit_code']=child.wait();assert record['exit_code']==0,stage+' failed; preserve logs/intermediates'
   finally:
    if child.poll() is None:
     child.terminate()
     try:child.wait(timeout=15)
     except subprocess.TimeoutExpired:child.kill();child.wait()
    record['exit_code']=child.returncode
    record['elapsed_seconds']=time.monotonic()-start;save()
 for kind in ['control','smoke']:
  final=RUNTIME/(kind+'-Q4_K_M.gguf')
  if final.exists():raise FileExistsError(final)
  scratch=Path(tempfile.mkdtemp(prefix=kind+'-temporary-',dir=RUNTIME));hf=scratch/'hf';gguf=scratch/'f16.gguf'
  report[kind]={'scratch':str(scratch),'temporary':True};save()
  if kind=='control' and args.resume_control_hf:
   hf=args.resume_control_hf.resolve(strict=True)
   manifest=json.loads((OUT/'control-hf.json').read_text())
   for name,entry in manifest['files'].items():
    with (hf/name).open('rb') as f:
     if hashlib.file_digest(f,'sha256').hexdigest()!=entry['sha256']:raise ValueError('Recovered HF hash mismatch')
   report[kind]['reused_hf_preserved']=str(hf);save()
  else:
   command(kind+'-hf',['/opt/anaconda3/bin/python','-m','scripts.mlx_python','scripts.mlx_export4b','--kind',kind,'--output',str(hf),'--report',str(OUT/(kind+'-hf.json'))])
  command(kind+'-f16',[str(ROOT/'.runtime/preparation/converter-env/bin/python'),'-m','scripts.mlx_python','--script',str(ROOT/'.runtime/preparation/llama.cpp/convert_hf_to_gguf.py'),str(hf),'--outfile',str(gguf),'--outtype','f16'])
  with gguf.open('rb') as f:report[kind]['f16_sha256']=hashlib.file_digest(f,'sha256').hexdigest()
  report[kind]['f16_bytes']=gguf.stat().st_size;save()
  command(kind+'-q4',[str(ROOT/'.runtime/preparation/llama.cpp/build/bin/llama-quantize'),str(gguf),str(final),'Q4_K_M','4'])
  with final.open('rb') as f:
   assert f.read(4)==b'GGUF';f.seek(0);report[kind]['q4_sha256']=hashlib.file_digest(f,'sha256').hexdigest()
  report[kind]['q4_bytes']=final.stat().st_size;save()
  # This directory was created above, contains no pre-existing file, and is expressly temporary.
  shutil.rmtree(scratch);report[kind]['temporary_intermediates_removed_after_verification']=True;save()
 report['finished_epoch']=time.time();report['free_bytes_after']=shutil.disk_usage(ROOT).free;save()
 print('Both staged exports complete; imports remain separate.')

if __name__=='__main__':main()
