# Publish Chess with Coolify

The repository contains two deployment choices:

- **Coolify:** `compose.coolify.yaml`. Coolify provides the public proxy and HTTPS.
- **Standalone Docker:** `compose.yaml`. Caddy owns public ports and certificates.

Use the Coolify file on a Coolify server. It exposes only internal container ports, so it does not compete with Coolify for host ports 80/443. The web container serves Svelte and forwards `/api` to `api:8000`.

## Setup

1. Push the completed project to your Git repository, including `web/bun.lock` and deployment files.
2. In Coolify, create an Application from that repository and choose the **Docker Compose** build strategy. Use the repository root as Base Directory (`/`) and `/compose.coolify.yaml` as Docker Compose Location.
3. Load/save the Compose definition. Assign **web** the domain `https://chess.aaryandehade.com:80`. The `:80` selects the internal web container port; visitors still use normal HTTPS. Leave **api** without a public domain. Do not enable raw Compose mode: Coolify must generate the proxy configuration.
4. Point the `chess` DNS A record to the hosting server. Add AAAA only if that server has working IPv6. Ensure Coolify's public proxy can receive ports 80/443.
5. Deploy and wait for both services to become healthy.
6. Open the domain; confirm `/api/health` returns `{"status":"ok"}` and `/api/engine` returns `{"available":true}`. Play a Stockfish game to verify the executable actually runs. Create a friend match and refresh it to check persistence.

No app secrets, API keys, hosted database, or separate Stockfish installation are needed. `STOCKFISH_PATH=/usr/games/stockfish` is already set in the API image. Docker installs a Linux Stockfish package for the image architecture; the Mac executable under `.tools` is not shipped.

Coolify may use slightly different names for the build strategy controls across versions. The required values remain: Compose build, root context, `compose.coolify.yaml`, web port 80, API private.

## Persistent data

`chess_data` mounts at `/data` and stores the SQLite database for friend matches and replay links. Keep this volume across deployments and back it up. For a simple consistent backup, stop the API briefly and copy the database, then restart it; alternatively use SQLite's backup API while running. Browser-local games stay in the player's browser. Run one stack on one host; multiple API replicas on different hosts require shared database storage.

## Capacity and Stockfish

The default runs **one API worker**, allowing **one active Stockfish process at a time**, with short bounded requests. Each process uses **one CPU thread** and a **16 MiB hash table**. The hash table is only part of total memory: neural-network data and process/Python overhead also use RAM.

- API container limit: **1 GiB RAM / 1 CPU**.
- Static web/proxy container limit: **128 MiB RAM / 0.5 CPU**.
- Planning recommendation for a server also running Coolify: **2 vCPU, 4 GB RAM** for this small site and build headroom. This is a starting estimate, not a measured Linux minimum or a guarantee for other hosted apps.
- No GPU is required. Stockfish uses the CPU. More simultaneous engine requests increase queueing; raise capacity only with additional CPU and RAM, then benchmark.

Coolify's own documented baseline is 2 CPU cores, 2 GB RAM and 10 GB disk, before accounting for application workloads. Builds can briefly need more memory than the running site. Keep enough free disk for Docker images, build cache, and backups.

Local engine use: install `stockfish` on PATH or set `STOCKFISH_PATH` to an executable matching your machine. The current Mac setup already has a working local binary. If unavailable, inspect the API logs and `/api/engine`; if busy, wait/retry. Basic local/friend games and puzzles work without Stockfish; computer games and engine analysis require it.

## Validation

CI validates both Compose files, builds the Coolify stack, waits for health checks, and requests a real Stockfish move through the web proxy. Docker is not installed in the current local workspace, so container execution must be verified in CI or on your Coolify server before treating deployment as proven.

References: [Coolify Compose deployment](https://coolify.io/docs/applications/builds/docker-compose), [Coolify server requirements](https://coolify.io/docs/start-with-self-hosted), [Stockfish settings](https://official-stockfish.github.io/docs/stockfish-wiki/Stockfish-FAQ.html).
