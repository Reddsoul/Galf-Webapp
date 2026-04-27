<h1>
  <span style="display:inline-flex;align-items:center;justify-content:center;background:#1B6B3A;border-radius:12px;padding:6px;line-height:0;vertical-align:middle"><img src="static/Favicon-96.png" width="32" height="32"></span>
  Galf — Web App
</h1>

A personal golf companion that lives on your iPhone. Log rounds, track your WHS handicap, analyze your game, and manage your club bag — all from a mobile-friendly web app you self-host.

For a full screen-by-screen reference, see [MANUAL.md](MANUAL.md).

---

## The Three Tabs

The app has exactly three tabs at the bottom of the screen:

<table>
<tr>
<td align="center" width="80"><span style="display:inline-flex;align-items:center;justify-content:center;background:#1B6B3A;border-radius:14px;padding:10px;line-height:0"><img src="static/Favicon-96.png" width="40" height="40"></span></td>
<td><strong>Home</strong><br>Your live WHS/USGA Handicap Index (requires 54 logged holes to establish), personal best scorecard for IRL and simulator rounds, and quick access to Stats. Tapping any stat cell opens the full Stats screen.</td>
</tr>
<tr>
<td align="center"><span style="display:inline-flex;align-items:center;justify-content:center;background:#1B6B3A;border-radius:14px;padding:10px;line-height:0"><img src="static/golf-cart-96.png" width="40" height="40"></span></td>
<td><strong>Rounds</strong><br>Full history of every round you've played, sorted most-recent first. Filter by Solo or Scramble. Tap any round to view its scorecard.</td>
</tr>
<tr>
<td align="center"><span style="display:inline-flex;align-items:center;justify-content:center;background:#1B6B3A;border-radius:14px;padding:10px;line-height:0"><img src="static/golf-course-96.png" width="40" height="40"></span></td>
<td><strong>Courses</strong><br>Your personal course library. Store hole pars, per-tee yardages, slope rating, and course rating. Supports multiple tee colors per course.</td>
</tr>
</table>

---

## How to Use It

### <span style="display:inline-flex;align-items:center;justify-content:center;background:#1B6B3A;border-radius:8px;padding:3px;line-height:0;vertical-align:middle"><img src="static/golf-ball-96.png" width="20" height="20"></span> Logging a Round

The **Log New Round** button — marked with the golf ball icon — sits above the tab bar on the Home screen.

1. Tap **Log New Round**
2. Pick your course, tee color, and hole count (18 Holes / Front 9 / Back 9)
3. Set the date, round type (Solo or Scramble), and whether it counts toward your handicap (Serious vs. Casual)
4. Optionally mark as a **Simulator** round — these are tracked separately and never affect your real handicap
5. Choose an entry mode:
   - **Quick** — score only, one number per hole
   - **Detailed** — tap clubs using the Nokia-style keypad; score = clubs tapped (including putts). Clubs are grouped by category in a fixed 3×4 grid — cells with multiple clubs cycle through them on repeated taps (multi-tap). GIR and putting stats are derived automatically. Powers the Stats screen.
6. Tap through each hole and enter your score
7. On the last hole tap **Finish** — a review screen shows the full scorecard. Add optional notes, then tap **Save Round**. Your handicap updates immediately.

> In Detailed mode, if your course has yardages and you have clubs in your bag, Galf suggests a club sequence for each hole's distance. If no full club fits the remaining distance, it falls back to the nearest partial wedge swing (e.g. `SW ¾`) — but only if you have entered partial distances for that wedge. For simulator rounds, putts are auto-rolled (with realistic distribution) and applied if you don't tap the Putter yourself.

---

### <span style="display:inline-flex;align-items:center;justify-content:center;background:#1B6B3A;border-radius:8px;padding:3px;line-height:0;vertical-align:middle"><img src="static/golf-course-96.png" width="20" height="20"></span> Adding a Course

You need at least one course before you can log a round.

1. Go to the **Courses** tab
2. Tap **+**
3. Fill in the course name, club/facility name, par for all 18 holes, and at least one tee box — color, slope rating, and course rating (all found on the physical scorecard). Yardages per tee are optional but enable club suggestions during Detailed entry.
4. Tap <span style="display:inline-flex;align-items:center;justify-content:center;background:#1B6B3A;border-radius:6px;padding:2px;line-height:0;vertical-align:middle"><img src="static/save-96.png" width="14" height="14"></span> **Save Course**

**Shortcut — Scan a Physical Scorecard:** Tap the <span style="display:inline-flex;align-items:center;justify-content:center;background:#1B6B3A;border-radius:6px;padding:2px;line-height:0;vertical-align:middle"><img src="static/camera-96.png" width="14" height="14"></span> **Scan Card** button at the top of the Add Course form to photograph a scorecard. Galf reads the pars, yardages, and tee ratings automatically, then shows a review screen where you can correct any misread fields before saving. Requires optional server dependencies — see below.

To edit a course later, tap its name then <span style="display:inline-flex;align-items:center;justify-content:center;background:#1B6B3A;border-radius:6px;padding:2px;line-height:0;vertical-align:middle"><img src="static/pencil-96.png" width="14" height="14"></span> **Edit Course**.
To delete it, tap the <span style="display:inline-flex;align-items:center;justify-content:center;background:#FF3B30;border-radius:6px;padding:2px;line-height:0;vertical-align:middle"><img src="static/trash-96.png" width="14" height="14"></span> button.

---

### <span style="display:inline-flex;align-items:center;justify-content:center;background:#1B6B3A;border-radius:8px;padding:3px;line-height:0;vertical-align:middle"><img src="static/golf-clubs-96.png" width="20" height="20"></span> Setting Up Your Bag

Your bag lives in **Stats → Clubs**. The <span style="display:inline-flex;align-items:center;justify-content:center;background:#1B6B3A;border-radius:6px;padding:2px;line-height:0;vertical-align:middle"><img src="static/golf-clubs-96.png" width="14" height="14"></span> clubs icon appears as a placeholder when the bag is empty — once you add clubs they show as a list sorted by distance (or by usage frequency once you have Detailed rounds).

1. Open the **Home** tab and tap any stat to reach the Stats screen
2. Tap the **Clubs** sub-tab
3. Tap **Add Club**, pick the club name, enter your carry distance in yards
4. Tap <span style="display:inline-flex;align-items:center;justify-content:center;background:#1B6B3A;border-radius:6px;padding:2px;line-height:0;vertical-align:middle"><img src="static/save-96.png" width="14" height="14"></span> **Add to Bag**
5. Repeat for each club you carry

To update a distance, tap <span style="display:inline-flex;align-items:center;justify-content:center;background:#1B6B3A;border-radius:6px;padding:2px;line-height:0;vertical-align:middle"><img src="static/pencil-96.png" width="14" height="14"></span> next to any club, change the value, tap <span style="display:inline-flex;align-items:center;justify-content:center;background:#1B6B3A;border-radius:6px;padding:2px;line-height:0;vertical-align:middle"><img src="static/save-96.png" width="14" height="14"></span> **Save**.

For wedge clubs (PW, GW, SW, LW, AW), the edit panel also shows **¾ swing**, **½ swing**, and **¼ swing** distance fields. Filling these in powers the partial-swing fallback in Detailed mode club suggestions — when no full club fits the remaining distance, Galf suggests the closest partial swing instead.

---

### <span style="display:inline-flex;align-items:center;justify-content:center;background:#1B6B3A;border-radius:8px;padding:3px;line-height:0;vertical-align:middle"><img src="static/Favicon-96.png" width="20" height="20"></span> Reading Your Stats

Tap any stat cell on the **Home** screen to open the Stats screen. It has four sub-tabs:

| Sub-tab | What it shows |
|---|---|
| **Overview** | Handicap Index, round count, top 8 score differentials, progress toward 54-hole threshold |
| **Performance** | GIR %, putts per round, scrambling rate, average strokes to green — requires Detailed rounds |
| **Clubs** | Your bag sorted by carry distance (or usage frequency once Detailed rounds exist) |
| **Analysis** | Stroke leaks — where you're losing shots vs. par — requires Detailed rounds |

> Performance and Analysis only populate if you use **Detailed** entry mode. Quick mode captures scores only.

---

### <span style="display:inline-flex;align-items:center;justify-content:center;background:#1B6B3A;border-radius:8px;padding:3px;line-height:0;vertical-align:middle"><img src="static/golf-cart-96.png" width="20" height="20"></span> Viewing a Past Round

1. Tap the **Rounds** tab
2. Tap any round to open its scorecard
3. To delete it, tap <span style="display:inline-flex;align-items:center;justify-content:center;background:#FF3B30;border-radius:6px;padding:2px;line-height:0;vertical-align:middle"><img src="static/trash-96.png" width="14" height="14"></span> **Delete** at the bottom of the scorecard

---

## Setup for Complete Beginners

### What you need

- A Mac, Windows PC, or Linux machine to act as the server
- Python 3.10 or newer — [download here](https://www.python.org/downloads/)
- Your iPhone on the same Wi-Fi as that computer

---

### Step 1 — Get the code

```bash
git clone https://github.com/Reddsoul/galf-webapp.git
cd galf-webapp/
```

No git? Download the ZIP from GitHub, unzip it, then open a terminal inside the `webapp` folder.

---

### Step 2 — Install the one dependency

```bash
pip3 install flask
```

> **Windows:** use `pip` if `pip3` isn't found.
> **"pip not found":** re-run the Python installer and tick **Add Python to PATH**.

---

### Step 3 — Start the server

```bash
python3 app.py
```

You'll see:

```
==================================================
  Galf is running!
  Local:   http://127.0.0.1:5003
  Network: http://192.168.1.42:5003
==================================================
```

Open the **Network** address (`192.168.x.x`) in Safari on your iPhone. Both devices must be on the same Wi-Fi.

> **Windows:** use `python` instead of `python3`.

---

### Step 4 — Add to iPhone home screen

1. Open the Network URL in **Safari**
2. Tap the **Share** button (square with an arrow pointing up)
3. Tap **Add to Home Screen** → **Add**

It will launch full-screen like a native app, complete with the <span style="display:inline-flex;align-items:center;justify-content:center;background:#1B6B3A;border-radius:5px;padding:2px;line-height:0;vertical-align:middle"><img src="static/Favicon-96.png" width="14" height="14"></span> icon.

---

## Keeping it running

**Easiest:** leave the terminal open.

**Background (Mac/Linux):**
```bash
nohup python3 app.py &
```
Stop it later: `kill $(lsof -ti:5003)`

**Always-on (Docker):**

Create a `docker-compose.yml` next to the `webapp/` folder:

```yaml
version: "3"
services:
  galf:
    image: python:3.12-slim
    working_dir: /app
    volumes:
      - ./webapp:/app
    command: sh -c "pip install flask -q && python app.py"
    ports:
      - "5003:5003"
    restart: unless-stopped
```

```bash
docker-compose up -d       # start
docker-compose restart     # restart after code changes
```

---

## Accessing from Anywhere with Tailscale

By default Galf is only reachable on your home Wi-Fi. [Tailscale](https://tailscale.com) is a free VPN that securely connects your devices over the internet — so you can open Galf on your iPhone from anywhere in the world as long as the server machine is on and running.

### How it works

Tailscale creates a private network between only your own devices. Nobody else can see or reach your server. No port forwarding, no router config, no public IP needed.

### Step 1 — Create a free Tailscale account

Go to [tailscale.com](https://tailscale.com) and sign up. The personal plan is free and supports up to 3 users and 100 devices — more than enough.

### Step 2 — Install Tailscale on the server machine

| OS | Instructions |
|---|---|
| **Mac** | Download from [tailscale.com/download](https://tailscale.com/download), open the `.pkg`, sign in |
| **Windows** | Download the installer from the same page, run it, sign in |
| **Linux** | Run `curl -fsSL https://tailscale.com/install.sh \| sh` then `sudo tailscale up` |

After signing in, your machine gets a private Tailscale IP in the `100.x.x.x` range. You can see it in the Tailscale menu bar icon or by running:

```bash
tailscale ip
```

### Step 3 — Install Tailscale on your iPhone

1. Download **Tailscale** from the App Store (it's free)
2. Open it and sign in with the same account you used in Step 2
3. Tap the toggle to connect

### Step 4 — Access Galf from anywhere

Make sure Galf is running on your server machine (`python3 app.py`), then open Safari on your iPhone and go to:

```
http://<tailscale-ip>:5003
```

Replace `<tailscale-ip>` with the `100.x.x.x` address from Step 2. You can bookmark this URL or update the home screen shortcut to use it.

> **Tip:** Tailscale device names also work. If your machine is named `macmini` in Tailscale, you can use `http://macmini:5003` instead of the IP.

---

## Optional: Scorecard OCR

The **Scan Card** feature lets you photograph a physical scorecard to auto-populate a course. It requires two extra dependencies that are not installed by default:

1. **Tesseract OCR** — install via your OS package manager:
   - Mac: `brew install tesseract`
   - Ubuntu/Debian: `sudo apt install tesseract-ocr`
   - Windows: download the installer from [github.com/UB-Mannheim/tesseract](https://github.com/UB-Mannheim/tesseract/wiki)

2. **Python packages:**
   ```bash
   pip3 install opencv-python-headless pytesseract pillow
   ```

If these are not installed, the app still runs normally — the scan endpoint returns a 503 if called but the rest of the app is unaffected.

---

## Environment Variables

| Variable | Default | Effect |
|---|---|---|
| `GALF_PORT` | `5003` | Port the server listens on |

Example:
```bash
GALF_PORT=8080 python3 app.py
```

---

## File layout

```
webapp/
├── app.py              Flask routes (thin layer only — no business logic)
├── Backend.py          All business logic: handicap, stats, scoring, data I/O
├── scorecard_ocr.py    Optional OCR module for scanning physical scorecards
├── templates/
│   └── index.html      Entire frontend — HTML + CSS + JS, one file
├── static/             Icons used throughout the UI
└── data/               Auto-created on first run; holds all your golf data
    ├── courses.json     Course definitions (pars, tee boxes, yardages)
    ├── rounds.json      Every logged round — your golf history
    ├── clubs.json       Club bag with carry distances; wedges also store partial swing distances
    ├── user_prefs.json  Entry mode preference
    └── stats_cache.json Cached stats, auto-invalidated on new rounds
```

---

## Backing up your data

Copy the `data/` folder somewhere safe. `data/rounds.json` is your complete golf history.

---

## Troubleshooting

**"python3: command not found"** — install Python from python.org, tick "Add to PATH" during install.

**"No module named flask"** — run `pip3 install flask` and try again.

**Can't reach the app from iPhone** — both devices must be on the same Wi-Fi. Use the `192.168.x.x` address, not `127.0.0.1`. Check your firewall isn't blocking port 5003.

**Data doesn't save** — the app creates the `data/` folder automatically. If it still fails, check that the process has write permission to the `webapp/` directory.
