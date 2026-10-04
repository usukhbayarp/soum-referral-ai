#!/bin/sh
# PREPARED, NOT YET EXECUTED. Explicit pipeline-test exports only; never production.
set -eu
cd "$(dirname "$0")/.."
.venv/bin/python - <<'PY'
import hashlib,json,shutil,subprocess
from pathlib import Path
p=Path('evaluation/pipeline4b-smoke');r=json.loads((p/'smoke-result.json').read_text());pins=json.loads((p/'pins.json').read_text());budget=json.loads((p/'disk-budget.json').read_text())
assert r['clinical_candidate_eligible'] is False and len(r['steps'])==3 and r['stages']['reload']=='observed_success'
assert subprocess.check_output(['git','-C','.runtime/preparation/llama.cpp','rev-parse','HEAD'],text=True).strip()==pins['llama_cpp_revision']
# Retain intermediates; no implicit cleanup. The already-present base is excluded.
required=budget['retained_intermediates_peak_additional_bytes_estimate']-budget['mlx_download_bytes']
free=shutil.disk_usage('.').free
if free<required:raise SystemExit(f'Disk gate: need {required/1024**3:.2f} GiB free; have {free/1024**3:.2f}; add {(required-free)/1024**3:.2f} GiB. No export started.')
assert not json.loads(subprocess.check_output(['curl','-fsS','http://127.0.0.1:11434/api/ps']))['models'], 'Defer while Ollama is resident; do not unload user work'
for name,entry in json.loads((p/'download.json').read_text())['files'].items():
 with (Path('.runtime/pipeline4b/base')/name).open('rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==entry['sha256']
with Path('.runtime/pipeline4b/smoke/adapters.safetensors').open('rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==r['adapter_sha256']
for n in ['control-hf','smoke-hf','control-f16.gguf','smoke-f16.gguf','control-Q4_K_M.gguf','smoke-Q4_K_M.gguf','control-import','smoke-import']:
 assert not (Path('.runtime/pipeline4b')/n).exists(), 'Never overwrite prior exports; preserve and use a new explicitly versioned run'
PY
/opt/anaconda3/bin/python -m scripts.mlx_python mlx_lm convert --hf-path .runtime/pipeline4b/base --mlx-path .runtime/pipeline4b/control-hf --dequantize --dtype bfloat16
/opt/anaconda3/bin/python -m scripts.mlx_python mlx_lm fuse --model .runtime/pipeline4b/base --adapter-path .runtime/pipeline4b/smoke --save-path .runtime/pipeline4b/smoke-hf --dequantize
for name in control smoke; do
  .runtime/preparation/converter-env/bin/python -m scripts.mlx_python --script .runtime/preparation/llama.cpp/convert_hf_to_gguf.py ".runtime/pipeline4b/$name-hf" --outfile ".runtime/pipeline4b/$name-f16.gguf" --outtype f16
  .runtime/preparation/llama.cpp/build/bin/llama-quantize ".runtime/pipeline4b/$name-f16.gguf" ".runtime/pipeline4b/$name-Q4_K_M.gguf" Q4_K_M 4
done
.venv/bin/python -m scripts.import_candidate --gguf .runtime/pipeline4b/control-Q4_K_M.gguf --tag soum-qwen3-4b-control:mlx128-52a5ab34 --output .runtime/pipeline4b/control-import
.venv/bin/python -m scripts.import_candidate --gguf .runtime/pipeline4b/smoke-Q4_K_M.gguf --tag soum-qwen3-4b-pipeline-test:step3-52a5ab34 --output .runtime/pipeline4b/smoke-import
.venv/bin/python - <<'PY'
import json
from pathlib import Path
p=Path('evaluation/pipeline4b-smoke/pins.json');pins=json.loads(p.read_text())
for index,name in [(1,'control'),(2,'smoke')]:
 meta=json.loads((Path('.runtime/pipeline4b')/(name+'-import')/'import.json').read_text());assert meta['tag']==pins['comparison_models'][index]['tag'];pins['comparison_models'][index]['digest']=meta['candidate_digest']
Path('.runtime/pipeline4b/imported-pins.json').write_text(json.dumps(pins,indent=2))
PY
# Comparison is separate and bounded; do not automatically promote the smoke tag.
printf '%s\n' 'Exports imported. Next: .venv/bin/python -m scripts.pipeline4b_compare --pins .runtime/pipeline4b/imported-pins.json --output .runtime/pipeline4b/comparison'
