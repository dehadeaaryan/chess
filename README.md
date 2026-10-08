# Aaryan Chess

A modern Svelte 5 + TypeScript chess website and a Python terminal game sharing one rules service. Intended domain: **chess.aaryandehade.com**.

## Architecture

- `src/chess_game/game.py`: UI-independent rules facade over `chess`, including legal moves, castling, en passant, all promotions, checkmate, stalemate, automatic draws, SAN/UCI notation, and PGN export.
- `src/chess_game/cli.py`: Python terminal client, using that facade directly.
- `src/chess_game/api.py`: FastAPI adapter. Local/computer requests replay bounded history to preserve repetition. Friend games use server-owned SQLite records, opaque player keys and atomic revision checks.
- `src/chess_game/social.py`: durable friend games, authoritative clocks and immutable replay records. SQLite supports multiple API workers on one host. Set `CHESS_DB` to change the database path (default `data/chess.sqlite3`).
- `web/`: Svelte client. The browser handles presentation and saves the move journal locally; Python decides which moves are legal. Vite proxies `/api` during development; Caddy serves the compiled site and proxies the same path in production.

Supports local two-player chess, Stockfish computer play, invitation-based friend matches, optional clocks, immutable replays, daily puzzles and Stockfish analysis. The Python service owns chess rules for all modes. Friend matches synchronize by one-second polling; player keys stay in browser storage, outside invitation URLs. There are no accounts or public matchmaking.

## Run locally

Python 3.12+ and Bun 1.3.11 are required.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[test]'
.venv/bin/aaryan-chess
```

For the website, start both servers together and leave the terminal open:

```sh
python3 dev.py
```

Alternatively, run these in separate terminals:

```sh
.venv/bin/uvicorn chess_game.api:app --reload
```

```sh
cd web
bun install --frozen-lockfile
bun run dev
```

Open `http://localhost:5173`. API documentation is at `http://localhost:8000/docs`.

## Verify

```sh
.venv/bin/python -m pytest
cd web
bun run check
bun run build
bunx playwright install chromium
bun run test:ui
```

## Publish with Coolify

Use [`compose.coolify.yaml`](compose.coolify.yaml), with domain `https://chess.aaryandehade.com:80` assigned to **web** only. Stockfish installs automatically; SQLite data persists in `chess_data`. Follow [the complete Coolify setup and resource guide](deploy/COOLIFY.md). This profile lets Coolify handle public HTTPS; no host port mappings are required.

## Standalone deployment

The supplied Docker Compose deployment uses Caddy for automatic HTTPS and serves both the Svelte site and Python API on one origin.

1. Provision a Linux server with Docker Compose and allow inbound TCP 80/443 (UDP 443 is optional for HTTP/3).
2. Point the `chess` DNS A record to the server's public IPv4 address. Add AAAA only if IPv6 is configured and reachable.
3. Copy this repository to the server and run `docker compose up -d --build`.
4. Visit `https://chess.aaryandehade.com` and check `/api/health`. Caddy obtains certificates after DNS resolves to the server.

Only Caddy is exposed publicly. Its certificate data and the SQLite game database persist in named volumes. Back up the `chess_data` volume to preserve invitations and replays. Set `CHESS_DOMAIN` to another hostname to use a different domain, or `:80` for a local HTTP smoke test. If an existing reverse proxy already owns ports 80/443, integrate the site there instead of starting a competing proxy. DNS and hosting credentials are not included; this repository alone does not publish the site.

Local games, results, and computer-game preferences remain in the browser's local storage; exporting PGN provides a portable backup. Refresh recovery validates the saved game through Python. Requests are bounded to 1,200 plies and 64 KB at the public proxy; add host-level rate limiting if deploying to a high-traffic public service.

## Dependency licensing

The original project code remains MIT licensed (see LICENSE). The `chess` dependency is GPL-3.0-or-later. Distribution of a combined application must comply with its license; include the dependency license and corresponding source when distributing deployment images. This repository's source is provided openly. Do not treat the complete distribution as MIT-only.

## Visual style and UI tests

Uses the app family's Figtree font, AD logo, orange accent (`#ff7a30`), ambient background, glass cards, pill controls, and dark/sage light themes. Font files and their OFL license are served locally. Theme selection persists independently of the game. Reduced motion and visible keyboard focus are supported.

Playwright runs against the real Python API in isolated servers on ports 8101/5179, with desktop and mobile Chromium projects. Tests cover legal hints, moves, undo, board orientation, reload persistence, invalid moves, underpromotion, checkmate, PGN content, reset, network recovery, themes, keyboard play, and horizontal overflow. The layout test captures dark and light screenshots in `web/test-results/`. No Safari is used. CI runs the same suite.

## Playing and reviewing

Select Game settings to choose local play or Stockfish, your color, and difficulty. Changing opponent or color starts a new game after confirmation. Undo takes back a human move and its computer reply together. If an engine request fails, the human move is preserved and Retry requests the reply again.

The board uses orange (`#ff7a30`) and white squares. Last-move and checked-king highlights, captures, and material advantage update with the position. Move journal buttons and first/previous/next controls review history without changing or saving over the live game; Live returns to play. Export always exports the complete game.

Import PGN accepts a pasted game or a file up to 60 KB. One standard-chess game is imported, including a custom FEN starting position. Only the main line is played; comments and variations are not retained. Imported decisive results without a terminal board position are represented as resignation; drawn results as agreement. Invalid PGNs leave the current game intact. Resign requires confirmation; Claim draw is enabled when repetition or the fifty-move rule permits it. Results survive refresh and appear in exported PGN.

## Stockfish setup

The current local setup has Stockfish 18 under `.tools/stockfish/` (ignored by Git), downloaded from the official release. On another machine, install Stockfish and add it to PATH, or set `STOCKFISH_PATH` to its executable before starting the API. Linux `/usr/games/stockfish` is detected automatically. Docker installs Stockfish. Stockfish is optional for local two-player games; the computer option is disabled when no engine is found.

Engine requests run one engine at a time per API worker with one CPU thread, 16 MB hash, a bounded search duration, and a short queue timeout. Stockfish is GPLv3; its local download includes license and source. Keep its license and corresponding source available when distributing it.

Terminal computer play: `.venv/bin/aaryan-chess --computer --color black --difficulty easy`. Terminal commands also support `resign`, `draw`, `review N` (without changing the live game), `import PATH`, and `save PATH`.

Stockfish availability is rechecked when opening Game settings, when the window regains focus, and every five seconds. To test an already running local instance with isolated browser storage: `cd web && CHESS_BASE_URL=http://127.0.0.1:5173 bun run test:ui`.

## Added play tools

- Drag pieces with a mouse or touch, or keep using click-to-move and keyboard notation. Moves animate unless reduced motion is enabled. Enable/mute subtle move, capture and check sounds in Game settings; the preference persists.
- Explore & share → Explain this position runs short Stockfish MultiPV analysis, displays three candidate lines with a board arrow, and identifies attacked, undefended pieces. Explanations are rule-based descriptions, not generated coaching. Engine hints are disabled during ongoing friend matches and unsolved puzzles, and on the live board of a computer game.
- Analyse finished game evaluates every position incrementally. The graph shows White’s evaluation, capped visually at ±10 pawns. Mistakes (≥1 pawn loss) and blunders (≥3) link back to the position before the move with a recommended line. These are approximate short searches, not tournament-grade annotations. Stop analysis cancels further requests.
- Daily puzzle is a small rotating collection of original mate-in-one compositions. The puzzle changes at UTC midnight; any legal checkmate is accepted. Hints and daily streaks live in this browser. It does not overwrite the saved local game.
- Share replay stores an immutable game and produces a read-only link with history controls. Replay and invitation links last 30 days. This local implementation caps stored records at 10,000.
- Game settings → Invite a friend creates a match; send the displayed link. The creator plays White, the first joiner plays Black; other visitors can watch. Choose no clock or 3/5/10 minutes per side. Clocks start when Black joins, run on the server, and have no increment. Moves are authenticated and version-checked atomically; reconnect/reload restores the player role from this browser’s key. Losing browser storage loses that seat’s key.

For another device to open local invitations, use your computer’s LAN hostname/IP rather than `localhost` and ensure both Vite and the API are reachable through the proxy. Public Internet play becomes available after you host the app. Clipboard copying on insecure LAN HTTP may be blocked by the browser; the selectable link remains available.

Deployment remains single-host SQLite. To scale across hosts, replace the storage adapter with a shared database. No external services are required for local use. Hosting has not been performed.
