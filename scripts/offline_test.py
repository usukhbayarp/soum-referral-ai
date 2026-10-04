"""Local-only readiness harness. Never toggles networks or stops Ollama."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import signal
import subprocess
import time
import httpx
from app.core import ROOT, prepare
from scripts.dataset import validate_cases

FIXTURE = ROOT / "readiness/fixtures/offline-new.json"
DEFAULT_RUN = ROOT / ".runtime/offline-readiness"
MANUAL_STEPS = {
    "connections_disconnected": "Wi-Fi, Ethernet, phone tethering and every other internet connection were manually disconnected throughout the test",
    "ollama_restarted": "Quit and reopened Ollama while disconnected, after checking no other application needed it",
    "ui_real_extraction": "Fresh localhost page loaded and the fictional note produced real extraction (record UI elapsed seconds)",
    "evidence_navigation": "Clicked at least one extraction evidence source ID and saw the matching original source text highlighted",
    "first_edit_and_approval": "Edited a clinical field, reviewed all fields/missing values, and approved",
    "approval_revoked": "Edited again after approval; approval was revoked, print disabled and old print content cleared",
    "reapproved_and_pdf_saved": "Reviewed again, reapproved and saved the printed PDF locally",
    "pdf_readable_complete": "Opened every PDF page; Mongolian Ө ө Ү ү and negatives/units are readable; all populated fields and footer appear without clipping",
    "reconnected": "Manually restored normal internet connections after all offline steps",
}


def command(args):
    p = subprocess.run(args, capture_output=True, text=True, timeout=10)
    return p.stdout.strip() if p.returncode == 0 else ""


def listener(port):
    values = command(
        ["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-t"]
    ).splitlines()
    unique = set(values)
    if len(unique) > 1:
        raise ValueError(f"Multiple listeners on port {port}; inspect manually")
    return int(next(iter(unique))) if unique else None


def project_app(pid):
    if pid is None:
        return False
    cwd = command(["lsof", "-a", "-p", str(pid), "-d", "cwd", "-Fn"]).splitlines()
    args = command(["ps", "-p", str(pid), "-o", "command="])
    return (
        f"n{ROOT}" in cwd
        and " -m uvicorn app.main:app " in args
        and "--port 8000" in args
    )


def network_hints():
    # Interface names only: never collect IP addresses, SSIDs or network history.
    result = {}
    for family, args in [
        ("ipv4", ["route", "-n", "get", "default"]),
        ("ipv6", ["route", "-n", "get", "-inet6", "default"]),
    ]:
        text = command(args)
        result[family + "_default_interface"] = next(
            (
                line.split(":", 1)[1].strip()
                for line in text.splitlines()
                if "interface:" in line
            ),
            None,
        )
    result["interpretation"] = (
        "Hints only; neither absence nor presence independently proves internet disconnection. User observation required."
    )
    return result


def snapshot():
    with httpx.Client(trust_env=False, timeout=5) as client:
        config = client.get("http://127.0.0.1:8000/api/config")
        config.raise_for_status()
        runtime = client.get("http://127.0.0.1:11434/api/version")
        runtime.raise_for_status()
        tags = client.get("http://127.0.0.1:11434/api/tags")
        tags.raise_for_status()
        resident = client.get("http://127.0.0.1:11434/api/ps")
        resident.raise_for_status()
    model = config.json()["model"]
    local = next((m for m in tags.json()["models"] if m["name"] == model), None)
    if (
        not local
        or local.get("remote_host")
        or local.get("details", {}).get("format") != "gguf"
    ):
        raise ValueError("Configured local GGUF model is not installed")
    return {
        "utc": datetime.now(timezone.utc).isoformat(),
        "commit": command(["git", "-C", str(ROOT), "rev-parse", "HEAD"]),
        "working_tree_dirty": bool(
            command(["git", "-C", str(ROOT), "status", "--porcelain"])
        ),
        "model": model,
        "model_digest": local["digest"],
        "runtime": runtime.json(),
        "app_pid": listener(8000),
        "ollama_pid": listener(11434),
        "resident_models": [m["name"] for m in resident.json()["models"]],
        "deployment_mode": config.json()["deployment_mode"],
        "inference_timeout": config.json().get("inference_timeout", 120),
        "device": {
            "macos": platform.mac_ver()[0],
            "architecture": platform.machine(),
            "chip": command(["sysctl", "-n", "machdep.cpu.brand_string"]),
            "unified_memory_bytes": command(["sysctl", "-n", "hw.memsize"]),
            "physical_cpu_cores": command(["sysctl", "-n", "hw.physicalcpu"]),
            "logical_cpu_cores": command(["sysctl", "-n", "hw.logicalcpu"]),
        },
        "network_hints": network_hints(),
    }


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def prepare_run(directory):
    cases = validate_cases(json.loads(FIXTURE.read_text()))
    assert (
        len(cases) == 1
        and cases[0].split == "development"
        and cases[0].clinician_review_status == "unreviewed"
    )
    before = snapshot()  # No inference, unload, process stop or network change.
    if before["deployment_mode"] != "local" or not project_app(before["app_pid"]):
        raise ValueError("Expected the local project application on port 8000")
    directory.mkdir(parents=True, exist_ok=False)
    write(directory / "before.json", before)
    (directory / "fictional-note.txt").write_text(cases[0].source_note + "\n")
    (directory / "OFFLINE-TEST.md").write_text(
        (ROOT / "readiness/OFFLINE-TEST.md").read_text()
    )
    write(
        directory / "observations.json",
        {
            key: {"status": "not_run", "observer": "user", "details": ""}
            for key in MANUAL_STEPS
        },
    )
    print(
        f'Prepared {directory}; no inference run. Shared Ollama has {len(before["resident_models"])} resident model(s).'
    )


def stop_app(directory):
    if not (directory / "before.json").exists():
        raise ValueError("Run prepare first")
    pid = listener(8000)
    if not project_app(pid):
        raise ValueError("Refusing to stop a process not verified as this project app")
    os.kill(pid, signal.SIGTERM)
    for _ in range(50):
        if listener(8000) is None:
            write(
                directory / "app-stop.json",
                {"pid": pid, "utc": datetime.now(timezone.utc).isoformat()},
            )
            print(
                "Stopped only the verified project app. Ollama and other processes untouched."
            )
            return
        time.sleep(0.1)
    raise ValueError("App did not release port; no force-kill attempted")


def start_app(directory):
    before = json.loads((directory / "before.json").read_text())
    if listener(8000) is not None:
        raise ValueError("Port 8000 occupied; no process replaced")
    env = {
        **os.environ,
        "REFERRAL_MODEL": before["model"],
        "DEPLOYMENT_MODE": "local",
        "OLLAMA_BASE_URL": "http://127.0.0.1:11434",
        "APP_ALLOWED_HOSTS": "127.0.0.1,localhost,[::1]",
        "INFERENCE_TIMEOUT": str(before["inference_timeout"]),
    }
    process = subprocess.Popen(
        [
            str(ROOT / ".venv/bin/python"),
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8000",
            "--workers",
            "1",
            "--no-access-log",
        ],
        cwd=ROOT,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    write(
        directory / "app-start.json",
        {"pid": process.pid, "utc": datetime.now(timezone.utc).isoformat()},
    )
    print(
        f"Started project app PID {process.pid}; open http://127.0.0.1:8000 after a few seconds. No model loaded by this action."
    )


def check_cold(before, now):
    for key in ("commit", "model", "model_digest", "runtime", "inference_timeout"):
        if before[key] != now[key]:
            raise ValueError(f"{key} changed; prepare a new attempt")
    if now["working_tree_dirty"]:
        raise ValueError(
            "Commit/stash only your intended changes before the recorded run"
        )
    if now["deployment_mode"] != "local":
        raise ValueError("Expected local-mode disclosure")
    if now["resident_models"]:
        raise ValueError(
            "A model is already resident; do not interrupt unrelated work. Reschedule cold test."
        )
    if before["app_pid"] == now["app_pid"] or before["ollama_pid"] == now["ollama_pid"]:
        raise ValueError("Both app and Ollama must have restarted since prepare")


def capture(directory, confirmed):
    if not confirmed:
        raise ValueError(
            "Manual disconnection is required; supply --disconnected-confirmed only after doing it"
        )
    before = json.loads((directory / "before.json").read_text())
    path = (
        directory
        / f'capture-{datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")}.json'
    )
    result = {
        "offline_status": "user_reports_disconnected; not independently proven",
        "clinical_status": "unreviewed development-only mechanics",
        "status": "failed",
        "error": None,
    }
    started = None
    try:
        now = snapshot()
        result["before_inference"] = now
        check_cold(before, now)
        case = json.loads(FIXTURE.read_text())[0]
        result["fixture_sha256"] = hashlib.sha256(FIXTURE.read_bytes()).hexdigest()
        started = time.perf_counter()
        with httpx.Client(trust_env=False, timeout=150) as client:
            response = client.post(
                "http://127.0.0.1:8000/api/extract",
                json={
                    "note": case["source_note"],
                    "request_id": "offline-readiness-01",
                },
            )
        result["elapsed_seconds"] = round(time.perf_counter() - started, 3)
        result["http_status"] = response.status_code
        result["response"] = (
            response.json()
        )  # Only the fixed fictional note; never accepts patient input.
        response.raise_for_status()
        if result["response"].get("model_digest") != now["model_digest"]:
            raise ValueError("Response model digest mismatch")
        units, _, _ = prepare(case["source_note"])
        if result["response"].get("units") != units:
            raise ValueError("Returned source units differ")
        metrics = result["response"].get("metrics", {})
        if not all(
            isinstance(metrics.get(k), (int, float)) and metrics[k] > 0
            for k in ("load_duration", "eval_count", "prompt_eval_count")
        ):
            raise ValueError("Missing/nonpositive real-generation metrics")
        result["status"] = "pass"
        result["cold_model_start"] = (
            "empty /api/ps before real extraction; inspect returned load_duration too"
        )
    except (ValueError, OSError, httpx.HTTPError) as error:
        result["error"] = str(error)
        if started is not None:
            result["elapsed_seconds"] = round(time.perf_counter() - started, 3)
    write(path, result)
    print(f'{result["status"].upper()}: {path}')
    if result["error"]:
        print(result["error"])
    print(
        "Browser review, PDF and actual network-disconnection observations still require a person."
    )
    if result["status"] != "pass":
        raise ValueError("Extraction capture failed; see the preserved error artifact")


def observe(directory):
    path = directory / "observations.json"
    data = json.loads(path.read_text())
    for key, description in MANUAL_STEPS.items():
        print("\n" + description)
        answer = (
            input("Observed result [pass/fail/not_run; Enter keeps existing]: ")
            .strip()
            .lower()
        )
        if not answer:
            continue
        if answer not in ("pass", "fail", "not_run"):
            raise ValueError(
                "Use pass, fail or not_run; prior answers have already been saved"
            )
        detail = input(
            "What did you actually see? Include error text/timing if applicable; no personal data: "
        )
        data[key] = {
            "status": answer,
            "observer": "user",
            "details": detail,
            "utc": datetime.now(timezone.utc).isoformat(),
        }
        write(path, data)
    pdf = directory / "offline-referral.pdf"
    if pdf.exists():
        with pdf.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        write(
            directory / "pdf-metadata.json",
            {
                "filename": pdf.name,
                "bytes": pdf.stat().st_size,
                "sha256": digest,
                "visual_quality": "user observation required",
            },
        )
    print(
        "Saved user observations separately from automated captures. Reconnect internet if you have not already."
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action", choices=["prepare", "stop-app", "start-app", "capture", "observe"]
    )
    parser.add_argument("--run", type=Path, default=DEFAULT_RUN)
    parser.add_argument("--disconnected-confirmed", action="store_true")
    args = parser.parse_args()
    directory = args.run.resolve()
    if not directory.is_relative_to(ROOT / ".runtime"):
        parser.error(
            "Evidence must stay inside ignored .runtime, not the public repository"
        )
    try:
        if args.action == "capture":
            capture(directory, args.disconnected_confirmed)
        else:
            {
                "prepare": prepare_run,
                "stop-app": stop_app,
                "start-app": start_app,
                "observe": observe,
            }[args.action](directory)
    except (ValueError, OSError, httpx.HTTPError) as error:
        parser.exit(1, f"Blocked: {error}\n")


if __name__ == "__main__":
    main()
