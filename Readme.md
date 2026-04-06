# Galf

A personal golf companion web app designed to run on a Mac and be accessed from an iPhone over the local network. Built with Flask and a vanilla JS single-page frontend following Apple Human Interface Guidelines.

---

## Features

### Home
- Handicap Index displayed prominently (calculated using the official WHS/USGA formula)
- One-tap access to log a new round
- Personal best scorecard with color-coded hole scores (eagle/birdie/par/bogey/double+)
- Quick stats: rounds played, average score, link to full statistics

### Log Round
- Select club/facility, course, tee box, date, hole selection (18, Front 9, Back 9)
- **Quick mode** — numeric keypad entry, one score per hole
- **Detailed mode** — club-by-club entry per hole; tracks strokes, putts, clubs used
- Live running total and score-vs-par during entry
- Review scorecard before saving

### Rounds
- Full history of all rounds, filterable by type (Solo / Scramble)
- Tap any round to view its full scorecard
- Tee-color-themed scorecard header with score, +/−, and round metadata
- Front 9 / Back 9 / combined totals

### Statistics
Four tabs:

| Tab | Contents |
|---|---|
| Overview | Handicap index, differentials chart, best round, average scores |
| Performance | GIR, putting averages, 3-putt rate, fairways in regulation, scrambling |
| Clubs | Full bag sorted by usage frequency (or distance). Tap any club to edit distance inline. |
| Analysis | Stroke leak detection with prioritized improvement areas |

### Courses
- Add and manage golf courses with full tee box configuration (rating, slope, yardages per hole)
- Supports multiple tee boxes per course (Black, Blue, White, Yellow, Red, Gold, etc.)
- Courses grouped by club/facility

### Rulebook
- Browse the 2023 Rules of Golf PDF page by page
- Full-text search with snippet previews

---

## Setup

### Requirements

- Python 3.10+
- Flask
- PyMuPDF (`fitz`) — optional, required for the Rulebook feature

```bash
pip install flask pymupdf
```

### Running

```bash
cd webapp
python app.py
```

The app prints its local network address on startup:

```
==================================================
  Galf is running!
  Local:   http://127.0.0.1:5001
  Network: http://192.168.x.x:5001
  Password: galf
==================================================
```

Open the Network URL on your iPhone. The default password is `galf` — change `APP_PASSWORD` in `app.py` to something else.

The port defaults to `5001`. Override with:

```bash
GALF_PORT=8080 python app.py
```

---

## Data

All data is stored as JSON files in `data/`:

| File | Contents |
|---|---|
| `courses.json` | Course definitions (pars, tee boxes, yardages) |
| `rounds.json` | All logged rounds including detailed hole-by-hole stats |
| `clubs.json` | Your bag (club names and carry distances) |
| `user_prefs.json` | Entry mode preference and preferred tee color |
| `stats_cache.json` | Cached advanced statistics (auto-invalidated on new rounds) |
| `2023_Rules_of_Golf.pdf` | Rulebook PDF (optional) |

No database required. Back up the `data/` folder to preserve your history.

---

## Handicap Calculation

Uses the official **World Handicap System (WHS)** formula:

- Score differential = `113 × (Score − Course Rating) / Slope`
- 9-hole rounds are combined using the WHS expected score method
- The handicap table (3–20 differentials) applies the appropriate number of best differentials with a 0.96 multiplier

A minimum of **3 handicap-eligible rounds** (serious, solo) is required to establish an index. Progress toward that is shown on the home screen.

---

## Entry Modes

| Mode | How it works |
|---|---|
| **Quick** | Enter total score per hole via number pad |
| **Detailed** | Tap clubs in order of use per hole; putts, GIR, and strokes-to-green are derived automatically |

Detailed mode is required for the Performance and Analysis stats tabs to populate.

The preferred entry mode is saved automatically between sessions.

---

## Project Structure

```
webapp/
├── app.py              # Flask routes and API
├── Backend.py          # All business logic (handicap, stats, scoring)
├── templates/
│   ├── index.html      # Single-page app (HTML + CSS + JS, ~2200 lines)
│   └── login.html      # Password gate
└── data/               # JSON data files + rulebook PDF
```
