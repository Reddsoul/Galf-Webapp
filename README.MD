# Galf — Golf Companion Web App

A self-hosted mobile golf companion that lives on your iPhone. Log rounds, track your official WHS/USGA Handicap Index, analyze your game, and manage your club bag — all from a web app you run on your own hardware.

---

## What It Does

- **Handicap tracking** — Calculates a real WHS/USGA Handicap Index from your serious 18-hole rounds. Establishes after three of them. 9-hole rounds are logged and ranked in stats (scaled to an 18-hole differential) but never feed the index. Serious simulator rounds count by default — a Settings toggle limits it to real rounds.
- **Round logging** — Quick score entry (one number per hole) or detailed hole-by-hole entry with GIR, putts, club, and penalty tracking. A searchable course picker with a Recent list speeds setup. 9-hole rounds can be extended to 18 mid-round, and 18-hole rounds can be finished early as a 9.
- **Fix it before you save** — Review & Save is editable. Tap the header to change course, tee, date, holes, or round type; tap the scorecard to step back through holes. Entered scores survive the edit — holes are remapped by number, and swapping to a sibling course at the same facility matches nines by par (and yardage) so a shared nine keeps its scores. Holes the edit leaves blank are flagged on the review card and become a short guided fill-in; nothing saves with a silent gap.
- **Simulator rounds** — Tracked separately with their own personal best. Putts are auto-rolled in both entry modes: in Quick mode you enter strokes to green and Galf adds the putts, so sim rounds still feed GIR without polluting putting stats.
- **Practice sessions** — Adaptive drill templates built from your bag. Covers warm-up, putting, chipping, Wedge Matrix (calibrates partial carry distances per wedge), irons, and woods. Saving a session writes updated wedge distances back to your club bag automatically. Sessions saved to history.
- **Stats** — GIR %, scrambling, putts per round, penalty strokes (water / OB / unplayable, plus per-round average), and stroke leak analysis by hole position.
- **Course library** — Store hole pars, per-tee yardages, slope rating, and course rating. Multiple tee colors per course (names are normalized to Title Case so `red` and `Red` never drift apart).
- **Scorecard scanning** — Optional: photograph a paper scorecard and let server-side OCR (Tesseract + OpenCV) extract pars, yardages, and tee ratings into the course editor. Degrades cleanly if the OCR deps aren't installed.
- **Club bag** — Track carry distances (and partial-wedge distances) per club; during detailed entry the app suggests the fewest-shots club sequence to reach the pin.
- **Personal bests** — Home screen shows best IRL and simulator scorecards on a single toggle card. A full 18 always outranks a 9-hole round.
- **Activity heatmap** — 18-week calendar on the home screen showing days you played a round, practiced, or both.
- **Settings** — Two themes (Royal Green, Burgundy — each with light and dark variants), a toggle for whether sim rounds count toward the handicap, and an on/off switch for scorecard scanning. Stored server-side so they follow you across devices.
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
pip install flask flask-sqlalchemy
```

Optional — only if you want scorecard scanning:

```bash
pip install opencv-python-headless pytesseract Pillow
brew install tesseract   # or apt install tesseract-ocr
```

Without these the app runs normally; the Scan Card button is hidden and `/api/courses/scan` returns 503.

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
| `PORT` | `5003` | Port the app listens on |
| `SECRET_KEY` | `change-me-in-production` | Flask session secret — change this |
| `DATA_PATH` | `./data` | Directory for `galf.db` |
| `APP_NAME` | `Galf` | Name shown in startup banner |

---

## For a full screen-by-screen reference, see [MANUAL.md](MANUAL.md).
