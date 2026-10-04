"""No model loads: overwrite and report-path guards must run before allocation."""
import sys
import pytest
from scripts import staged_export4b, mlx_export4b


def test_staged_export_preserves_existing_report(monkeypatch, tmp_path):
    report = tmp_path / 'staged-export.json'
    report.write_text('prior evidence')
    monkeypatch.setattr(staged_export4b, 'OUT', tmp_path)
    monkeypatch.setattr(sys, 'argv', ['staged_export4b'])
    with pytest.raises(FileExistsError):
        staged_export4b.main()
    assert report.read_text() == 'prior evidence'


def test_staged_report_cannot_escape_evidence_directory(monkeypatch):
    monkeypatch.setattr(sys, 'argv', ['staged_export4b', '--report-name', '../outside.json'])
    with pytest.raises(ValueError, match='filename'):
        staged_export4b.main()


def test_hf_export_refuses_existing_artifact_before_importing_mlx(monkeypatch, tmp_path):
    target = tmp_path / 'hf'
    target.mkdir()
    existing = target / 'original'
    existing.write_text('preserve')
    monkeypatch.setattr(sys, 'argv', ['mlx_export4b', '--kind', 'smoke', '--output', str(target), '--report', str(tmp_path / 'report.json')])
    with pytest.raises(FileExistsError):
        mlx_export4b.main()
    assert existing.read_text() == 'preserve'
