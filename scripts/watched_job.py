"""Run one owned subprocess with the existing conservative memory/contention limits."""
import argparse, json, os, subprocess, time
from pathlib import Path
import httpx
from scripts.medication_experiment import ROOT


def run(command, report_path):
    if report_path.exists():
        raise FileExistsError(report_path)
    start = time.monotonic()
    report = {'command': command, 'samples': [], 'stop_reason': None}
    with httpx.Client(base_url='http://127.0.0.1:11434', trust_env=False, timeout=3) as client:
        if client.get('/api/ps').json()['models']:
            raise RuntimeError('Defer: Ollama resident; do not stop user work')
        with (ROOT / '.runtime' / (report_path.stem + '.log')).open('x') as log:
            child = subprocess.Popen(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, env={**os.environ, 'PYTHONUNBUFFERED':'1'})
            try:
                while child.poll() is None:
                    time.sleep(2)
                    if child.poll() is not None:
                        break
                    pressure = subprocess.check_output(['sysctl','-n','kern.memorystatus_vm_pressure_level'],text=True).strip()
                    rss = subprocess.run(['ps','-p',str(child.pid),'-o','rss='],capture_output=True,text=True).stdout.strip()
                    free = int(subprocess.check_output(['memory_pressure'],text=True).split('System-wide memory free percentage:')[-1].strip().rstrip('%'))
                    sample = {'seconds':time.monotonic()-start,'rss_kib':int(rss or 0),'pressure_level':pressure,'system_free_percent':free}
                    report['samples'].append(sample)
                    if pressure == '4' or free < 8 or sample['rss_kib'] > 9*1024**2:
                        raise RuntimeError('Critical pressure/free-memory/RSS guard')
                    if time.monotonic()-start > 600:
                        raise RuntimeError('600-second bound')
                    if client.get('/api/ps').json()['models']:
                        raise RuntimeError('Ollama contention')
            except BaseException as exc:
                report['stop_reason'] = str(exc)
            finally:
                if child.poll() is None:
                    child.terminate()
                    try: child.wait(timeout=15)
                    except subprocess.TimeoutExpired: child.kill(); child.wait()
                report['exit_code'] = child.wait()
                report['elapsed_seconds'] = time.monotonic()-start
                report_path.write_text(json.dumps(report,indent=2)+'\n')
    if report['stop_reason'] or report['exit_code']:
        raise RuntimeError('Owned job stopped/failed; inspect '+str(report_path))


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);p.add_argument('command',nargs=argparse.REMAINDER);a=p.parse_args()
    run(a.command,a.report)
