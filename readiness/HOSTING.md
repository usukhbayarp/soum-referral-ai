# Hosting decision — approval pending

Prices checked 2026-10-04 in USD. Prepared configuration is not a tested hosted deployment. No infrastructure purchased, tunnel started, or Mac exposed. Target: five people browsing/editing independently; **one active inference plus two waiting requests**, queue wait 15 seconds, inference timeout 120 seconds, excess requests rejected. This is not five simultaneous generations or a latency guarantee. CPU inference latency remains untested on these hosts. Use fictional notes only in the hosted demo.

| Option | Region and configuration | 48 hours | 7 days / 168 hours | Practical limits |
|---|---|---:|---:|---|
| **Primary: DigitalOcean CPU-Optimized Regular c-4** | Singapore SGP1; 4 dedicated vCPU, 8 GiB RAM, 50 GiB SSD, no GPU; Ubuntu 24.04 | **$6.00** | **$21.00** | $0.125/hour, $84 monthly cap; exact regional stock/account quota must be checked at purchase. Dedicated CPU preferred for predictable scheduling; no measured throughput yet. |
| Fallback: AWS Lightsail Linux public-IPv4 8GB bundle | Singapore ap-southeast-1; 2 burstable vCPU, 8 GB RAM, 160 GB SSD, no GPU | **$2.84** | **$9.94** | $0.05913/hour, $44 monthly cap; CPU credits/baseline may slow sustained inference. Account activation/quota and current availability pending. |
| Temporary only: Cloudflare Quick Tunnel to this Mac | Existing Apple M4, 10 CPU cores, 16 GiB unified RAM, local disk/Metal GPU shared with other work | $0 service fee | $0 service fee | Existing internet/electricity excluded. No uptime guarantee; Mac sleep, home uplink and changing URL make it unsuitable as the primary submission host. No tunnel launched. |

Estimates assume one instance for the entire period, existing domain, under 10 GiB demo outbound traffic, bundled disk, no backups/snapshots/load balancer/extra IP/GPU/storage. Taxes, domain registration, exchange rates and unexpected traffic excluded. 8 GB is an estimated fit for the 1.7B quantized model, not a measured guarantee. Model download is inbound. DO's 5,000 GiB monthly outbound allowance accrues with uptime; Lightsail bundles 5 TB transfer with Singapore outbound overage $0.12/GB (inbound counts toward its allowance). Region-specific pricing must be checked before creation.

DO bills per second with a minimum 60 seconds or $0.01, whichever is higher. This recommendation is the capped Regular bundle, not uncapped per-resource v5 plans. AWS hourly rate verified in its current Singapore price-list API; sub-hour rounding/minimum was not independently verified, so budget whole hours. **Stopped instances still bill on both providers; destroy/delete to stop compute charges.** Detached Lightsail static IPs can incur separate charges; snapshots/block storage can survive instance deletion. Do not create extras. Cloudflare Quick Tunnel has a 200-in-flight-request limit and no SLA; the app's much smaller inference limit still applies.

The Lightsail fallback uses the same Linux Docker/Compose files and loopback namespace arrangement; select its Linux bundle, restrict SSH, attach a stable public IP, configure DNS and follow the same deployment/check commands. Its console/account setup and burstable CPU behavior are the main additional obstacles. A Mac tunnel instead uses the native Ollama/app arrangement: an approved hostname must be explicitly allowed and the application restarted in hosted mode before any tunnel is opened. Avoid simultaneous local/hosted app processes bypassing the single-process inference gate. Named tunnels require verified account/domain access; a Quick Tunnel has an unstable URL. Neither tunnel route has been configured or tested. The Mac provides shared existing disk and Metal GPU resources, with no dedicated allocation or new storage.

## Decision and real cost controls

Recommend seven days on DO for estimated $21 compute, proposed **maximum authorized spend $30**, subject to account/domain approval and confirmation of how long judges need the URL. This is a planning limit, NOT a guaranteed provider hard cap. Set spend alerts at $10/$20/$25; DO alerts can be delayed and do not block spending. Real controls: exactly one fixed-size VM, no autoscaling or optional paid features, inspect billing daily, schedule owner teardown at 168 hours unless a new budget is approved, and verify deletion plus remaining billable resources in the console. Powering off, `docker compose down`, or stopping inference does not stop VM billing. A real billing ceiling cannot be guaranteed without a provider-enforced cap; none has been verified here. Do not buy before approval.

Observed tools: Docker/Compose, GitHub CLI and cloudflared available; GitHub API authentication works. cloudflared account access unverified. No DO/AWS/Fly/Railway/Render/GCP/Azure CLI on PATH. No cloud account or billing credentials inspected. Needed: approved DO account/payment access, exact budget/duration, SSH public key provided by owner, owned DNS hostname and ability to point its A record to the VM. Do not paste private keys or tokens. Existing Mac demo continues running.

## Prepared deployment, after explicit approval only

The existing two containers share a network namespace: web calls Ollama only at `127.0.0.1:11434`. The new override adds Caddy to that namespace, exposes only 80/443 publicly and retains web's loopback-only host mapping. Ollama stays private; the strict application loopback restriction is unchanged. One Uvicorn worker, hosted disclosure, exact allowed hostname, bounded inference and no request/content logs remain in force. Caddy provides automatic HTTPS once DNS and ports are correct. No patient records or personal media may be submitted. A public fictional-only demo has no user authentication; confirm whether judges require unrestricted access before launch, and monitor misuse. Per-user persistent storage is absent; browser state is separate, while inference admission is shared.

1. After approval, create the specified VM in the console (verify price/region/stock); do not enable paid extras. Set cloud firewall inbound TCP 22 only from the operator's IP, 80/443 publicly. Never expose 8000 or 11434. Point the approved DNS name to the VM. Install Docker Engine + Compose on Ubuntu following [Docker's official instructions](https://docs.docker.com/engine/install/ubuntu/); no local installation is required.
2. On that VM, clone this public repository and check out the reviewed immutable commit:

```sh
git clone https://github.com/usukhbayarp/soum-referral-ai.git
cd soum-referral-ai
git checkout <APPROVED_COMMIT_SHA>
export DEMO_HOST=<YOUR_ACTUAL_DNS_HOSTNAME>
export APP_ALLOWED_HOSTS="127.0.0.1,localhost,$DEMO_HOST"
export REFERRAL_MODEL=qwen3:1.7b
# Validate before starting; the values above must be replaced.
docker compose -f deployment/compose.yaml -f deployment/compose.hosted.yaml config --quiet
docker compose -f deployment/compose.yaml -f deployment/compose.hosted.yaml up -d --build ollama
docker compose -f deployment/compose.yaml -f deployment/compose.hosted.yaml exec ollama ollama pull qwen3:1.7b
# Record digest; compare with local before.json. A changed upstream tag must not be silently accepted.
docker compose -f deployment/compose.yaml -f deployment/compose.hosted.yaml exec ollama ollama list
docker compose -f deployment/compose.yaml -f deployment/compose.hosted.yaml up -d --build
curl --fail "https://$DEMO_HOST/api/health"
curl --fail "https://$DEMO_HOST/api/ready"
```

Liveness `/api/health` means application responding. Readiness `/api/ready` means the configured local model is installed/reachable, not that a generation has succeeded. Before sharing, run a fictional extraction, inspect disclosure/evidence/edit/approval/PDF, verify exact model digest/settings, test five browser sessions with one active inference and overflow rejection, and check outside the VM that ports 8000/11434 are inaccessible. These hosted checks are **not run**. Do not use the new offline-test note for online checks. CPU latency/queue timeouts may be unacceptable; measure before committing to a judging URL.

Rollback application: check out the previous known-good commit and rebuild the web container with the same baseline model. Retain `qwen3:1.7b` and `qwen3:4b`; do not overwrite tags. No training or model conversion is part of deployment. At the approved end time, retain only fictional artifacts needed for handoff, destroy the VM and verify no independently billed resources remain.

## Primary sources

Accessed 2026-10-04: [DO rates](https://www.digitalocean.com/pricing/droplets), [billing/minimums](https://docs.digitalocean.com/products/droplets/details/pricing/), [regions](https://docs.digitalocean.com/platform/regional-availability/), [bandwidth](https://docs.digitalocean.com/platform/billing/bandwidth/), [alerts are not caps](https://docs.digitalocean.com/platform/billing/spend-alerts/); [Lightsail prices](https://aws.amazon.com/lightsail/pricing/), [FAQ: billing/regions/transfer](https://aws.amazon.com/lightsail/faq/), [Singapore price-list JSON](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonLightsail/current/ap-southeast-1/index.json) (published 2026-09-15; SKU MY73GG9BDFTPCK2E); [Quick Tunnel limits](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/); [Caddy request limit](https://caddyserver.com/docs/caddyfile/directives/request_body), [reverse proxy](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy), [HTTPS](https://caddyserver.com/docs/automatic-https).
