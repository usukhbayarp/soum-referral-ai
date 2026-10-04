# Hosted packaging — prepared, not deployed

**Observed:** the ARM64 web image built successfully; an offline, read-only container imported the application. Compose configuration validates. **Untested:** a complete web+Ollama hosted stack, public routing, TLS/access controls, model loading in Linux containers, overload behavior on hosting hardware, and amd64 image execution. Provider, region, budget and target concurrency are pending. No infrastructure was provisioned and the current local demo was not restarted.

`deployment/compose.yaml` uses Docker's documented [`network_mode: service:ollama`](https://docs.docker.com/reference/compose-file/services/#network_mode). The web process shares Ollama's network namespace, so it can reach `127.0.0.1:11434` while the adapter's strict loopback check remains intact. Ollama binds only that loopback address. **Do not replace it with a service hostname, `0.0.0.0:11434`, or a published inference port.** Only web port 8000 is published, on the host's `127.0.0.1`; an eventual host reverse proxy can terminate TLS and forward to it. Container recreation must recreate the shared-namespace pair together.

The image runs as a non-root user with a read-only filesystem. Runtime uses one Uvicorn worker; one active inference, two waiting requests, 15-second queue timeout and 120-second inference timeout remain unchanged. Do not scale workers/replicas without a shared bounded queue. Hosted disclosure is explicit (`DEPLOYMENT_MODE=hosted`). The user must supply an explicit hostname allowlist; never use `*`. Include `127.0.0.1` for health probes. Model selection is fixed by operator configuration, not user requests.

Access logging is disabled, Docker log persistence is disabled for both services, no request bodies are written by the app, and Ollama debug logging is off. Do not enable proxy body/debug logging. The browser state remains per-tab and the server stores no referral/session contents. These settings do not constitute a complete hosting retention/privacy review; use fictional data until the operational review is complete.

## Validate/build now; deploy only after hosting decisions

From the repository root (these checks were performed):

```sh
APP_ALLOWED_HOSTS=127.0.0.1,localhost,demo.example.org \
  docker compose -f deployment/compose.yaml config --quiet
docker build -f deployment/Dockerfile -t soum-referral-web:preparation-20261004 .
docker run --rm --network none --read-only --cap-drop ALL \
  --security-opt no-new-privileges:true --entrypoint python \
  soum-referral-web:preparation-20261004 \
  -c 'from app.main import app; print("Application import OK")'
```

The Docker build context allowlist excludes weights, caches, evaluation notes, credentials and all files other than application/configuration/dependency inputs. Images are version-tagged; pin registry digests during the eventual deployment release. The tested web image digest is recorded in the preparation report. The Ollama image is version-pinned to 0.34.0, but was not pulled or started here.

## Later operator sequence — NOT executed

After choosing and reviewing a host, set `APP_ALLOWED_HOSTS` to the real explicit hosts including `127.0.0.1`, and keep `REFERRAL_MODEL=qwen3:1.7b` initially. An empty container volume does not inherit the Mac's model cache. Seed that volume deliberately; pulling or copying model weights is a separate operator action.

```sh
export APP_ALLOWED_HOSTS=127.0.0.1,localhost,YOUR_REAL_DEMO_HOST
export REFERRAL_MODEL=qwen3:1.7b
docker compose -f deployment/compose.yaml up -d --build
# Later, explicitly seed the dedicated container model volume:
docker compose -f deployment/compose.yaml exec ollama ollama pull qwen3:1.7b
curl --fail http://127.0.0.1:8000/api/health
curl --fail http://127.0.0.1:8000/api/ready
```

Do not run this on port 8000 while the existing demo uses that port; use `WEB_PORT=8001` for an explicitly scheduled local packaging test. A model pull requires network access during provisioning; inference is local to the server after provisioning. Browser submission in hosted mode sends text to that server, not to the user's own computer. CPU-only Linux containers on Docker Desktop do not inherit Apple MLX/Metal acceleration; no acceptable latency claim is made for this packaging or for every macOS/Windows/Linux computer.

## Health and acceptance checks

- `/api/health`: **application liveness** only, no Ollama request or model load. Compose uses this as its web health check.
- `/api/ready`: **dependency/model availability**. Returns 200 only when loopback Ollama responds and the configured model is an installed local GGUF; otherwise 503 with a content-free reason. It explicitly reports `inference_verified:false`. It does not prove weights can load or meet latency/memory requirements. Its runtime probe times out after three seconds.
- After seeding, run a fictional extraction using the deployed hostname and confirm completed, non-thinking structured output, then doctor edit/approval/print. This is a separate **inference readiness smoke check**, not the liveness probe. Do not use clinical text for probes.
- Before exposing the demo, test allowed-host rejection, HTTPS proxy Host/Origin preservation, access controls, independent browser drafts, timeout/queue-full responses, resource limits and container restarts. No request-content logging at the proxy. Use a single web instance until a shared queue exists.

Changing configuration/files in this repository does not update the currently running demo; schedule a deliberate restart to use new readiness endpoints.
