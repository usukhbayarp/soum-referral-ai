"""Supervise only our smoke child; stop for contention, critical pressure or a time bound."""
import json,os,subprocess,time
from pathlib import Path
import httpx
from scripts.medication_experiment import ROOT

def main():
 out=ROOT/'evaluation/pipeline4b-smoke/watchdog.json'
 if out.exists():raise FileExistsError(out)
 start=time.monotonic();samples=[];reason=None
 with (ROOT/'.runtime/pipeline4b/smoke.log').open('w') as log:
  child=subprocess.Popen(['/opt/anaconda3/bin/python','-m','scripts.mlx_python','scripts.engineering4b','--engineering-smoke-only'],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,env={**os.environ,'PYTHONUNBUFFERED':'1'})
  with httpx.Client(base_url='http://127.0.0.1:11434',trust_env=False,timeout=3) as client:
   while child.poll() is None:
    time.sleep(2)
    if child.poll() is not None:break
    rss=subprocess.run(['ps','-p',str(child.pid),'-o','rss='],capture_output=True,text=True).stdout.strip()
    pressure=subprocess.run(['sysctl','-n','kern.memorystatus_vm_pressure_level'],capture_output=True,text=True).stdout.strip()
    free=subprocess.check_output(['memory_pressure'],text=True).split('System-wide memory free percentage:')[-1].strip().rstrip('%')
    try: loaded=client.get('/api/ps').json()['models']
    except (httpx.HTTPError,ValueError,KeyError):
     reason='Cannot verify Ollama residency; safely stop owned child';loaded=[{}]
    samples.append({'seconds':round(time.monotonic()-start,2),'child_rss_kib':int(rss or 0),'pressure_level':pressure,'system_free_percentage':int(free),'ollama_resident_count':len(loaded)})
    if loaded:reason='Ollama residency detected; defer to user inference'
    elif pressure=='4' or int(free)<8:reason='Critical system memory pressure/free metric'
    elif int(rss or 0)>9*1024**2:reason='Child RSS exceeded 9 GiB'
    elif time.monotonic()-start>600:reason='600-second engineering-job limit'
    if reason:
     child.terminate()
     try:child.wait(timeout=15)
     except subprocess.TimeoutExpired:child.kill();child.wait()
     break
  code=child.wait()
 out.write_text(json.dumps({'exit_code':code,'stop_reason':reason,'elapsed_seconds':time.monotonic()-start,'samples':samples,'method':'2s ps RSS of owned child + macOS pressure level/free metric; Ollama residency guard; never terminates another process'},indent=2)+'\n')
 print('Smoke exit',code,'stop reason',reason)
 raise SystemExit(code or (1 if reason else 0))

if __name__=='__main__':main()
