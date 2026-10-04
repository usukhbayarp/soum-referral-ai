import json
import pytest
from scripts.export_reviewed_adapter import sha
import scripts.run_quality_exports as run

def setup(monkeypatch,tmp_path):
    monkeypatch.setattr(run,'ROOT',tmp_path);monkeypatch.setattr(run,'OUT',tmp_path/'reports');run.OUT.mkdir()
    work=tmp_path/'.runtime/quality-medfacts-v1-step2';(work/'candidate-hf').mkdir(parents=True)
    downstream=work/'candidate-F16.gguf';downstream.write_bytes(b'verified downstream')
    source=work/'candidate-hf/model-1.safetensors';source.write_bytes(b'new shard')
    return source,{'path':str(downstream),'sha256':sha(downstream)}, {'files':{source.name:{'sha256':sha(source)}}}

def test_cleanup_only_verified_new_intermediate(monkeypatch,tmp_path):
    source,downstream,manifest=setup(monkeypatch,tmp_path)
    run.cleanup(2,[source],downstream,manifest)
    assert not source.exists()
    report=json.loads((run.OUT/'step2-cleanup-hf.json').read_text());assert report['status']=='completed' and report['deleted'][0]['sha256']==manifest['files'][source.name]['sha256']

def test_cleanup_rejects_unrelated_path(monkeypatch,tmp_path):
    source,downstream,manifest=setup(monkeypatch,tmp_path);other=tmp_path/'old.safetensors';other.write_bytes(b'preserve')
    with pytest.raises(ValueError):run.cleanup(2,[other],downstream,manifest)
    assert source.exists() and other.exists()

def test_cleanup_rejects_hash_mismatch(monkeypatch,tmp_path):
    source,downstream,manifest=setup(monkeypatch,tmp_path);downstream['sha256']='wrong'
    with pytest.raises(AssertionError):run.cleanup(2,[source],downstream,manifest)
    assert source.exists()
