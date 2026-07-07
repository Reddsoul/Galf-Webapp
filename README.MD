# Galf — Golf Companion Web App

A self-hosted mobile golf companion that lives on your iPhone. Log rounds, track your official WHS/USGA Handicap Index, analyze your game, and manage your club bag — all from a web app you run on your own hardware.

---

## What It Does

- **Handicap tracking** — Calculates a real WHS/USGA Handicap Index per 2024 rules. 18-hole and 9-hole rounds are both handled: a front 9 + back 9 from the same course/tee are paired into a virtual 18-hole differential automatically. Requires 54 logged holes to establish.
- **Round logging** — Quick score entry (just total score) or detailed hole-by-hole entry with GIR, putts, club, and penalty tracking. A searchable course picker with a Recent list speeds setup. 9-hole rounds can be extended to 18 mid-round, and 18-hole rounds can be finished early as a 9.
- **Practice sessions** — Adaptive drill templates built from your bag. Covers warm-up, putting, chipping, Wedge Matrix (calibrates partial carry distances per wedge), irons, and woods. Saving a session writes updated wedge distances back to your club bag automatically. Sessions saved to history.
- **Stats** — GIR %, scrambling, putts per round, penalty strokes (water / OB / unplayable, plus per-round average), and stroke leak analysis by hole position.
- **Course library** — Store hole pars, per-tee yardages, slope rating, and course rating. Multiple tee colors per course.
- **Scorecard scanning** — Photograph a scorecard and the app extracts course name, pars, handicaps, tees, ratings, and yardages using a **local vision LLM** (Ollama / llama.cpp / LM Studio — nothing leaves your network). Falls back to a Tesseract pipeline if no LLM endpoint is configured.
- **Club bag** — Track carry distances (and partial-wedge distances) per club. Mark clubs **Out of Bag** without deleting them — they're hidden from entry, suggestions, and the wedge matrix but kept for history. During detailed entry the app suggests the fewest-shots club sequence to reach the pin, preferring full swings over partial swings when both reach in the same number of shots.
- **Simulator rounds** — Tracked separately, excluded from real handicap.
- **Personal bests** — Home screen shows best IRL and simulator scorecards on a single toggle card.
- **Activity heatmap** — 18-week calendar on the home screen showing days you played a round, practiced, or both.
- **Built-in manual** — Full screen-by-screen reference, opened in-app from the **Manual** button on the home screen (renders this project's `MANUAL.md`).

---

## Requirements

- Docker (recommended), **or** Python 3.10+

No accounts, no external services, no telemetry. The app runs fully on your own hardware. The only thing fetched from the internet is the `marked` markdown library (loaded from a CDN to render the in-app manual); the browser caches it, and the rest of the app works offline.

---

## Install — Docker (Recommended)

### 1. Create the env file

Create a `.env` file in the project root and set at minimum:

```
SECRET_KEY=some-random-string-here
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

### 2. Configure (optional)

Create a `.env` file with any of the variables below. Defaults work out of the box without one.

The app reads `PORT`, `SECRET_KEY`, `DATA_PATH`, and `APP_NAME` from environment variables.

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
| `SECRET_KEY` | `change-me-in-production` | Flask session secret — change this |
| `DATA_PATH` | `./data` | Directory for `galf.db` |
| `APP_NAME` | `Galf` | Name shown in startup banner |
| `OCR_LLM_URL` | `http://127.0.0.1:11434/api/chat` | Vision-LLM endpoint. Ollama native API (`/api/chat`, recommended) or any OpenAI-compatible `/v1/chat/completions` (llama.cpp, LM Studio). Use a LAN IP when the app runs on a NAS |
| `OCR_LLM_MODEL` | `qwen2.5vl:3b` | Vision model name on that server (`moondream` is a lighter option) |
| `OCR_LLM_KEEP_ALIVE` | `0` | Ollama only: how long the model stays in RAM after a scan. `0` = unload immediately (recommended for helper boxes you also use for other things) |
| `OCR_LLM_TIMEOUT` | `180` | Scan request timeout in seconds. Includes cold model load when `KEEP_ALIVE=0` |

### Setting up scorecard scanning

The scan engine does **not** run on the box hosting Galf — the app just sends the photo to a vision LLM elsewhere on your LAN. This is deliberate: Galf itself runs happily on a 1 GB ARM NAS (e.g. Synology DS124), which cannot fit any vision model worth using. Any Mac or PC with ~4 GB free RAM can be the scan helper:

```bash
# on the helper box (e.g. a Mac Mini)
brew install ollama && brew services start ollama
ollama pull qwen2.5vl:3b
```

Then set on the Galf side (e.g. in DSM Container Manager env):

```
OCR_LLM_URL=http://<helper-box-ip>:11434/api/chat
```

With `OCR_LLM_KEEP_ALIVE=0` (the default) the model is loaded from disk when a scan arrives and unloaded seconds after — the helper box's RAM is only occupied during the scan itself, and nothing needs to run "always on". A scan takes roughly 15–60 s including the cold load. If the helper box is asleep or off, Scan Card reports it's unavailable (or falls back to the optional Tesseract pipeline if installed); every other feature keeps working.

To make Ollama reachable from the NAS, ensure it listens on the LAN: `launchctl setenv OLLAMA_HOST 0.0.0.0` (or `OLLAMA_HOST=0.0.0.0` in the service env), then restart Ollama.

---

---

## For a full screen-by-screen reference, see [MANUAL.md](MANUAL.md).
