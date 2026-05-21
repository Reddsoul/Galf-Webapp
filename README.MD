# Galf — Golf Companion Web App

A self-hosted mobile golf companion that lives on your iPhone. Log rounds, track your official WHS/USGA Handicap Index, analyze your game, and manage your club bag — all from a web app you run on your own hardware.

---

## What It Does

- **Handicap tracking** — Calculates a real WHS/USGA Handicap Index per 2024 rules (18-hole and 9-hole rounds both handled correctly). Requires 54 logged holes to establish.
- **Round logging** — Quick score entry (just total score) or detailed hole-by-hole entry with GIR, putts, and club tracking.
- **Practice sessions** — Adaptive drill templates built from your bag. Covers warm-up, putting, chipping, Wedge Matrix (calibrates partial carry distances per wedge), irons, and woods. Saving a session writes updated wedge distances back to your club bag automatically. Sessions saved to history.
- **Stats** — GIR %, scrambling, putts per round, stroke leak analysis by hole position.
- **Course library** — Store hole pars, per-tee yardages, slope rating, and course rating. Multiple tee colors per course.
- **Club bag** — Track carry distances per club; the app suggests clubs during detailed entry.
- **Simulator rounds** — Tracked separately, excluded from real handicap.
- **Personal bests** — Home screen shows best IRL and simulator scorecards on a single toggle card.
- **Activity heatmap** — 18-week calendar on the home screen showing days you played a round, practiced, or both.

---

## Requirements

- Docker (recommended), **or** Python 3.10+

No external services, no internet connection required after install.

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
| `PORT` | `5003` | Port the app listens on |
| `SECRET_KEY` | `change-me-in-production` | Flask session secret — change this |
| `DATA_PATH` | `./data` | Directory for `galf.db` |
| `APP_NAME` | `Galf` | Name shown in startup banner |

---

## For a full screen-by-screen reference, see [MANUAL.md](MANUAL.md).
