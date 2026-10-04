# Cold offline test — save this guide before disconnecting

Status: PREPARED, NOT YET PASSED. This test requires your observations. Automated online tests, mocks, cached results and container checks do not demonstrate offline operation. The new note is fictional, unreviewed and development-only; this is a mechanics check, not clinical evaluation.

## Before disconnecting

Ollama is a shared desktop service: quitting it interrupts any other application using it. Reserve a quiet test window. If another application needs Ollama, defer this test. Do not stop unrelated processes, downloads or conversions. Save any current referral first. The preparation inspection found no project download/conversion and no resident Ollama model; check again immediately before testing.

In Terminal:

```sh
cd /Users/usukhbayar.purevdorj/Documents/hackathon
open -a TextEdit readiness/OFFLINE-TEST.md
# Already prepared by the readiness task; only run this if before.json is absent:
.venv/bin/python -m scripts.offline_test prepare
cat .runtime/offline-readiness/before.json
ollama ps
```

The bundle includes this guide, a never-inferred fictional note, commit/model digest/runtime/device metadata, and observations initialized to `not_run`. Keep this Terminal and guide open. If a new attempt is necessary, preserve the old directory and pass `--run .runtime/offline-readiness-2` to EVERY command instead.

If only the project's `qwen3:1.7b` is resident and no other application needs it, unload it with `ollama stop qwen3:1.7b`. Do not unload other models. Then:

```sh
.venv/bin/python -m scripts.offline_test stop-app
```

This verifies the listener belongs to this project before sending SIGTERM; it does not stop Ollama. Quit **Ollama** from its macOS menu. Verify there is no listener:

```sh
lsof -nP -iTCP:11434 -sTCP:LISTEN
```

Empty output is expected. If it remains or restarts automatically, do not kill arbitrary processes; reconnect if needed and report the blocker.

## Disconnect and cold-start

Manually turn off Wi-Fi, unplug Ethernet, and disconnect phone/USB/Bluetooth tethering and any other internet uplink. Record what you disconnected. No script changes networking. The assistant may become unavailable now; continue from this saved guide.

While still disconnected:

```sh
open -a Ollama
.venv/bin/python -m scripts.offline_test start-app
# Wait a few seconds, then:
curl --fail http://127.0.0.1:8000/api/health
ollama ps
.venv/bin/python -m scripts.offline_test capture --disconnected-confirmed
```

`ollama ps` must show no loaded models before capture. Capture checks changed app/Ollama PIDs, identical commit/model digest/runtime, clean working tree, local disclosure, empty model residency; it then makes a REAL extraction request using the new note. It records elapsed time, returned runtime settings and errors in a timestamped JSON. An error is a failed attempt, not an offline success. Do not install/download anything while disconnected. Internet absence is a user observation, not proven by route metadata.

## Browser and PDF checks, still disconnected

```sh
pbcopy < .runtime/offline-readiness/fictional-note.txt
open http://127.0.0.1:8000
```

1. Reload the localhost page. Start **New referral** and confirm replacement if asked. Paste the copied fictional note; do not load an existing example. Run extraction and time it. Record success/error and elapsed seconds separately from the API capture.
2. Click at least one source/evidence ID. Verify the corresponding original note text highlights. Check negative statements and dose/unit text remain visible. Empty/incorrect assignments must be recorded, not treated as clinical correctness.
3. Edit a clinical field. Verify evidence is labeled as original extraction evidence, not proof of the edit. Use fictional administrative values only, e.g. `ОФЛАЙН-47`; do not enter real identities.
4. Review every populated/missing field, acknowledge unresolved information as appropriate for this fictional test, check the doctor-review acknowledgement and click **Хянаж батлах**. Verify print becomes available.
5. Edit again. Verify approval is revoked, printing is disabled and the previous approved print content is cleared.
6. Review and approve again. Click **Хэвлэх / PDF**. In macOS print dialog choose PDF → Save as PDF. Save to:
   `/Users/usukhbayar.purevdorj/Documents/hackathon/.runtime/offline-readiness/offline-referral.pdf`
7. Open EVERY PDF page. Confirm all populated sections/footer are present, no text is clipped, Mongolian letters (especially Ө/ө/Ү/ү), negatives and units are legible. Confirm doctor-entered text is not presented as source-verified. Record any defect and page number. The script only hashes the PDF; it cannot certify visual quality.

If any step fails, record the actual error and leave it failed/not_run; do not substitute an online run. Restore internet manually after the offline steps, including your normal Wi-Fi/Ethernet/tethering setup. Then record observations:

```sh
.venv/bin/python -m scripts.offline_test observe
```

Enter `pass`, `fail` or `not_run` for each step, with what you actually saw and timing/errors. Answers are saved after each entry; rerun to update them. Return to the assistant after reconnecting and say the observations are ready in `.runtime/offline-readiness`. Only after both automated captures and user observations are reviewed can the overall offline result be reported. Keep this evidence local; no patient data, personal media or PDFs belong in Git.
