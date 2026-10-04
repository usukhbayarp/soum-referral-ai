"""Harness regressions only: never run the new fixture through a model."""

import copy
import json
from unittest.mock import Mock

import pytest
from scripts import offline_test as audit


def snapshots():
    before = dict(
        commit="abc",
        model="qwen3:1.7b",
        model_digest="digest",
        runtime={"version": "test"},
        inference_timeout=120,
        working_tree_dirty=False,
        deployment_mode="local",
        resident_models=[],
        app_pid=1,
        ollama_pid=2,
    )
    now = {**copy.deepcopy(before), "app_pid": 3, "ollama_pid": 4}
    return before, now


def test_cold_checks_accept_matching_restarted_empty_runtime():
    audit.check_cold(*snapshots())


@pytest.mark.parametrize(
    "change",
    [
        {"resident_models": ["another-project"]},
        {"app_pid": 1},
        {"ollama_pid": 2},
        {"working_tree_dirty": True},
        {"deployment_mode": "hosted"},
        {"model_digest": "changed"},
        {"commit": "changed"},
        {"runtime": {"version": "changed"}},
        {"inference_timeout": 5},
    ],
)
def test_cold_checks_refuse_invalid_attempt(change):
    before, now = snapshots()
    now.update(change)
    with pytest.raises(ValueError):
        audit.check_cold(before, now)


def test_project_scope_requires_cwd_and_exact_server_command(monkeypatch):
    monkeypatch.setattr(
        audit,
        "command",
        lambda args: (
            f"n{audit.ROOT}"
            if args[0] == "lsof"
            else "/python -m uvicorn app.main:app --port 8000 --workers 1"
        ),
    )
    assert audit.project_app(123)
    monkeypatch.setattr(
        audit,
        "command",
        lambda args: (
            "nunrelated"
            if args[0] == "lsof"
            else "/python -m uvicorn app.main:app --port 8000"
        ),
    )
    assert not audit.project_app(123)


def test_stop_never_kills_unrelated_listener(monkeypatch, tmp_path):
    (tmp_path / "before.json").write_text("{}")
    monkeypatch.setattr(audit, "listener", lambda port: 99)
    monkeypatch.setattr(audit, "project_app", lambda pid: False)
    kill = Mock()
    monkeypatch.setattr(audit.os, "kill", kill)
    with pytest.raises(ValueError):
        audit.stop_app(tmp_path)
    kill.assert_not_called()


def test_disconnection_confirmation_required_before_any_request(monkeypatch, tmp_path):
    snapshot = Mock()
    monkeypatch.setattr(audit, "snapshot", snapshot)
    with pytest.raises(ValueError, match="Manual disconnection"):
        audit.capture(tmp_path, False)
    snapshot.assert_not_called()


def test_failure_is_preserved_and_not_reported_as_pass(monkeypatch, tmp_path):
    before, now = snapshots()
    now["resident_models"] = ["unrelated"]
    (tmp_path / "before.json").write_text(json.dumps(before))
    monkeypatch.setattr(audit, "snapshot", lambda: now)
    with pytest.raises(ValueError, match="capture failed"):
        audit.capture(tmp_path, True)
    result = json.loads(next(tmp_path.glob("capture-*.json")).read_text())
    assert result["status"] == "failed"
    assert "resident" in result["error"]
    assert "response" not in result
    assert "not independently proven" in result["offline_status"]


def test_preparation_does_not_infer_or_invent_observations(monkeypatch, tmp_path):
    before, _ = snapshots()
    monkeypatch.setattr(audit, "snapshot", lambda: before)
    monkeypatch.setattr(audit, "project_app", lambda pid: True)
    run = tmp_path / "run"
    audit.prepare_run(run)
    observations = json.loads((run / "observations.json").read_text())
    assert all(
        v["status"] == "not_run" and v["observer"] == "user"
        for v in observations.values()
    )
    cases = audit.validate_cases(json.loads(audit.FIXTURE.read_text()))
    assert cases[0].expected_assignments is None
    assert cases[0].split == "development"
    assert cases[0].clinician_review_status == "unreviewed"
    assert not list(run.glob("capture-*"))
    with pytest.raises(FileExistsError):
        audit.prepare_run(run)


def test_v07_restart_uses_extraction_contract_not_form_version(monkeypatch,tmp_path):
    before,_=snapshots();before['contract']=dict(version='experimental-0.7',extraction_schema_version='experimental-0.6',prompt_version='source-id-v06-1')
    (tmp_path/'before.json').write_text(json.dumps(before))
    monkeypatch.setattr(audit,'listener',lambda port:None)
    observed={}
    class Child:pid=999
    def launch(args,**kwargs):observed.update(kwargs['env']);return Child()
    monkeypatch.setattr(audit.subprocess,'Popen',launch)
    audit.start_app(tmp_path)
    assert observed['REFERRAL_SCHEMA_VERSION']=='experimental-0.6'
    assert observed['EXTRACTION_PROMPT_VERSION']==before['contract']['prompt_version']
