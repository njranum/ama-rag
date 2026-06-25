# Deploy Runbook — Layer 2 query service to the cloud (M4.1)

Phase-3 deployment of the FastAPI `/v1/ask` SSE service to an always-warm AWS Lightsail VPS,
fronted by Cloudflare. Mirrors the design in `docs/L2_Query_Pipeline.md` (Hosting; Abuse & cost
control; Deployment Phases). Manual cloud actions are Nic's; the repo-side artifacts
(`deploy/rag-api.service`, the Caddyfile snippet below) are committed for reproducibility.

> **Store note:** this runbook deploys the app on its current **Chroma** store (re-ingested on the
> box). The switch to the hosted **Pinecone** index is a separate, isolated step (`M4.2-01`).
> Pinecone *Inference* (embeddings) is used throughout regardless — it is not the store.

---

## Target

- **Instance:** Lightsail nano, Ubuntu 24.04 LTS, **eu-west-2** (London), dual-stack (public IPv4).
  `$5/mo` plan (512 MB / 2 vCPU / 20 GB). Public IP recorded in Cloudflare DNS (below), not here.
- **Process:** `uvicorn query.api:app` on `127.0.0.1:8000` under `systemd` (`deploy/rag-api.service`).
- **Edge:** Cloudflare proxied `ama-api.nicjranum.uk` → Caddy (443, origin cert) → uvicorn.

---

## M4.1-01 — Provision + deploy the query service  ✅

1. **Create the instance** (Lightsail console): Linux/Unix → OS Only → Ubuntu 24.04 LTS;
   networking **Dual-stack** (gives public IPv4); `$5/mo` plan; name `rag-api`.

2. **Swap** (the 512 MB box needs headroom for the `chromadb`/`onnxruntime` install):
   ```bash
   sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile
   sudo mkswap /swapfile && sudo swapon /swapfile
   echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
   ```

3. **Base tools + uv:**
   ```bash
   sudo apt-get update -y && sudo apt-get install -y git curl
   curl -LsSf https://astral.sh/uv/install.sh | sh && source $HOME/.local/bin/env
   ```

4. **Code:** `git clone https://github.com/njranum/ama-rag.git && cd ama-rag` (repo is public).

5. **Secrets:** create `.env` with `PINECONE_API_KEY`, `ANTHROPIC_API_KEY`, `NOTION_TOKEN`,
   `PORTFOLIO_PARENT_PAGE_ID` (server-side only; never in git). Verify names with
   `cut -d= -f1 .env | sort`.

6. **Deps** (query = serve, ingest = build the store; no dev tooling):
   ```bash
   uv venv && source .venv/bin/activate
   uv pip install -e ".[ingest,query]"
   ```

7. **Build the store** (fetch from Notion → embed via Pinecone Inference → store in Chroma):
   ```bash
   python -m ingest.embed_store     # prints "Stored N chunks", a 384-dim check, and a sanity query
   ```

8. **Service:** install `deploy/rag-api.service`, then:
   ```bash
   sudo cp deploy/rag-api.service /etc/systemd/system/rag-api.service
   sudo systemctl daemon-reload && sudo systemctl enable --now rag-api
   ```

9. **Verify:**
   - `systemctl status rag-api` → `active (running)`, `enabled`.
   - Streams locally:
     ```bash
     curl -sN -X POST http://127.0.0.1:8000/v1/ask -H 'Content-Type: application/json' \
       -d '{"question":"What is the Tideline project?"}' | grep -E '^event:' | sort | uniq -c
     ```
     → `sources` 1, `delta` N, `done` 1.
   - **Reboot survival:** `sudo reboot`; after reconnecting, `systemctl status rag-api` is
     `active (running)` with a fresh PID and low `uptime` (systemd auto-started it).

**Verify met:** survives reboot ✓ · streams an answer from the server ✓ · secrets only in `.env` ✓.

---

## M4.1-02 — Cloudflare in front + edge rate-limit  ✅

Domain: `nicjranum.uk` (already on Cloudflare). API host: `ama-api.nicjranum.uk`.

1. **DNS:** add a **proxied** (orange-cloud) `A` record `ama-api` → the Lightsail public IPv4.
   Verify it resolves to Cloudflare IPs (`dig +short ama-api.nicjranum.uk`), not the raw origin.
2. **Origin cert:** Cloudflare → SSL/TLS → Origin Server → Create Certificate (covers
   `*.nicjranum.uk`); save the cert + key onto the box.
3. **Firewall:** open **HTTPS (443)** on the Lightsail instance.
4. **Reverse proxy:** install Caddy; `/etc/caddy/Caddyfile`:
   ```
   ama-api.nicjranum.uk {
       tls /etc/caddy/origin.crt /etc/caddy/origin.key
       reverse_proxy 127.0.0.1:8000
   }
   ```
5. **SSL mode:** Cloudflare → SSL/TLS → set to **Full (strict)**.
6. **Edge rate-limit:** Cloudflare WAF rate-limiting rule — URI Path equals `/v1/ask`, **10 requests
   / 10 s per IP**, action **Block**. (10 s is the free-plan period; this coarse edge guard sits above
   the app's finer `30/min` `429` backstop from M2.4.)

**Verify met:** `https://ama-api.nicjranum.uk/v1/ask` returns `HTTP/2 200` with
`content-type: text/event-stream` via Cloudflare (`cf-ray … -LHR`) and streams `sources`→`delta`→
`done` ✓. A **sequential** 30-request burst showed the first 10 → `200` then 11–30 → `429`
(edge-blocked, never reached origin/Anthropic); a normal request recovers after the 10 s window ✓.
*(Note: a **concurrent** 15-burst did NOT trip it — simultaneous requests race Cloudflare's per-IP
counter; sequential is the reliable test.)* Cloudflare-buffering / unbuffered `text/event-stream`
pass-through is formally checked at `M4.4-01`.
