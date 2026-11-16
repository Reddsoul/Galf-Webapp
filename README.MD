# Galf — Golf Companion Web App

A self-hosted mobile golf companion that lives on your iPhone. Log rounds, track your official WHS/USGA Handicap Index, analyze your game, and manage your club bag — all from a web app you run on your own hardware.

---

## What It Does

- **Handicap tracking** — Calculates a WHS-style Handicap Index from the best differentials of your last 20 eligible rounds, with net double bogey per-hole caps (adjusted gross score) driven by each course's hole handicaps. Serious 18-hole rounds count, and front and back 9-hole rounds are paired into 18s (not the 2024 expected-score method). Shows a provisional estimate until three rounds count. PCC, caps and exceptional-score reduction aren't implemented. Simulator rounds are excluded unless you opt in under Settings.
- **Round logging** — Quick score entry (one number per hole) or detailed hole-by-hole entry with GIR, putts, club, and penalty tracking. A searchable course picker with a Recent list speeds setup. 9-hole rounds can be extended to 18 mid-round, and 18-hole rounds can be finished early as a 9.
- **Fix it before you save** — Review & Save is editable. Tap the header to change course, tee, date, holes, or round type; tap the scorecard to step back through holes. Entered scores survive the edit — holes are remapped by number, and swapping to a sibling course at the same facility matches nines by par (and yardage) so a shared nine keeps its scores. Holes the edit leaves blank are flagged on the review card and become a short guided fill-in; nothing saves with a silent gap.
- **Simulator rounds** — Tracked separately with their own personal best. Putts are auto-rolled in both entry modes: in Quick mode you enter strokes to green and Galf adds the putts, so sim rounds still feed GIR without polluting putting stats.
- **Practice sessions** — Adaptive drill templates built from your bag. Covers warm-up, putting, chipping, Wedge Matrix (calibrates partial carry distances per wedge), irons, and woods. Saving a session writes updated wedge distances back to your club bag automatically. Sessions saved to history.
- **Stats** — GIR %, scrambling, putts per round, penalty strokes (water / OB / unplayable, plus per-round average), and stroke leak analysis by hole position.
- **Course library** — Store hole pars, per-tee yardages, slope rating, and course rating. Multiple tee colors per course (names are normalized to Title Case so `red` and `Red` never drift apart).
- **Scorecard scanning** — Optional: photograph a scorecard and a **local vision LLM** (Ollama / llama.cpp / LM Studio — nothing leaves your network) fills the Add Course form with pars, yardages, tee ratings, and slopes. Can be switched off in Settings.
- **Club bag** — Track carry distances (and partial-wedge distances) per club; during detailed entry the app suggests the fewest-shots club sequence to reach the pin.
- **Personal bests** — Home screen shows best IRL and simulator scorecards on a single toggle card. A full 18 always outranks a 9-hole round.
- **Activity heatmap** — 18-week calendar on the home screen showing days you played a round, practiced, or both.
- **Settings** — Two themes (Royal Green, Burgundy — each with light and dark variants), a toggle for whether sim rounds count toward the handicap, a home club (pinned first when logging), a hole-handicap row toggle, and an on/off switch for scorecard scanning. Stored server-side so they follow you across devices.
- **Built-in manual** — Full screen-by-screen reference with search, section chips, and prev/next paging, opened from **Settings → Manual** (renders this project's `MANUAL.md` live).

---

## Requirements

- Docker (recommended), **or** Python 3.10+

No accounts, no external services, no telemetry. The app runs fully on your own hardware. The only thing fetched from the internet is the `marked` markdown library (loaded from a CDN to render the in-app manual); the browser caches it, and the rest of the app works offline.

---

## Install — Docker (Recommended)

### 1. Create the env file

Create a `.env` file in the project root and set at minimum:

```
PORT=5003
```

### 2. Build and run

```bash
docker compose up -d
```

The app starts on the port you configured (default `5003`). Your data lives in a Docker volume (`galf-data`) and persists across restarts and container rebuilds.

### 3. Open the app

On your Mac: `http://localhost:5003`  
On your iPhone (same network): `http://<your-mac-ip>:5003`

To find your Mac's local IP: **System Settings → Wi-Fi → Details**.

---

## Install — Python (No Docker)

### 1. Install dependencies

```bash
pip install flask flask-sqlalchemy pillow
```

Scorecard scanning needs a vision LLM on another machine; see the scanning setup section below. Until one is set up in Settings → Scan LLM, Scan Card points you there; every other feature works.

### 2. Configure (optional)

Create a `.env` file with any of the variables below. Defaults work out of the box without one.

The app reads `PORT`, `DATA_PATH`, and `APP_NAME` from environment variables.

### 3. Run

```bash
python app.py
```

The startup banner prints the local and network URLs.

---

## Accessing from iPhone

1. Connect iPhone and Mac to the same Wi-Fi network.
2. Open Safari on iPhone, navigate to `http://<mac-ip>:<port>`.
3. Tap the Share button → **Add to Home Screen** for an app-like icon.

For permanent access without needing your Mac's IP, set up a local reverse proxy (e.g. nginx or Caddy) with a fixed hostname.

---

## First Run

On first launch the app creates an empty SQLite database at `DATA_PATH/galf.db`. No seed data is loaded. Add your first course in the Courses tab, then log a round.

Upgrading an existing database is automatic: on startup the app adds any missing columns (e.g. the `settings` column on `user_prefs`) and normalizes stored tee color names to Title Case. No manual migration step.

---

## Backing Up Your Data

Your entire game history lives in a single file: `data/galf.db` (or the path set by `DATA_PATH`).

**Docker volume backup:**
```bash
docker run --rm -v galf-data:/data -v $(pwd):/backup alpine \
  tar czf /backup/galf-backup-$(date +%Y%m%d).tar.gz /data
```

**Direct path backup:**
```bash
cp data/galf.db galf-backup-$(date +%Y%m%d).db
```

To restore, replace `galf.db` with your backup and restart the app.

---

## Configuration

All config via environment variables (or `.env` file):

| Variable | Default | Description |
|---|---|---|
| `PORT` | `5003` | Port the app listens on (set `PORT=5003` in `.env`) |
| `DATA_PATH` | `./data` | Directory for `galf.db` |
| `APP_NAME` | `Galf` | Name shown in startup banner |
| `OCR_LLM_KEEP_ALIVE` | `0` | Ollama native only: how long the model stays in RAM after a scan |
| `OCR_LLM_TIMEOUT` | `180` | Scan request timeout in seconds |

### Setting up scorecard scanning

The scan engine does **not** run on the box hosting Galf — the app sends the photo to a vision LLM on another machine. Galf itself runs happily on a 1 GB ARM NAS (e.g. Synology DS124), which cannot fit any vision model worth using.

Scanning has **no default server**. In the app, open **Settings → Scan LLM** and enter:

- **Base URL** — an OpenAI-compatible endpoint, e.g. `http://<llm-host>:4000/v1` (vLLM, LiteLLM, llama.cpp, LM Studio), or an Ollama native `http://<host>:11434/api/chat`
- **Model** — a vision-capable model served there
- **API Key** — optional bearer token

Then tap **Test Connection**. The settings are saved only when the test passes (server reachable and the model listed). The API key is stored server-side and never sent back to the browser. Until a test passes, Scan Card sends you to Settings instead of scanning.

The Galf container must be able to reach that host. Over Tailscale, if Docker can't resolve a MagicDNS name, use the machine's Tailscale IP.

For ad-hoc testing outside the app: `OCR_LLM_URL=… OCR_LLM_MODEL=… python ocr_llm.py card.jpg`.

Scanning fills only the Add/Edit Course fields you have not filled yourself — anything you typed before scanning is kept. If the LLM server is unreachable, Scan Card reports it and every other feature keeps working.

---

---

## For a full screen-by-screen reference, see [MANUAL.md](MANUAL.md).
