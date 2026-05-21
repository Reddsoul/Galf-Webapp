## 1. Home Screen

The Home screen is your dashboard. It's the **center tab** in the tab bar.

### Handicap Index

The large number at the top is your **WHS Handicap Index**, calculated from your serious solo rounds following USGA rules.

- Shows `--` until you have logged **54 holes** of serious play
- Beneath the dashes it tells you how many more holes you need: _"Play 38 more holes to establish"_
- Once established, the number updates automatically every time you save a new round
- Shown to one decimal place (e.g. `12.3`)

### Best Round Card

Below the handicap, Galf shows a single card for your best round. If you have both IRL and simulator rounds, **IRL** and **Sim** toggle buttons appear on the card so you can switch between the two bests.

Each card shows:

- Course name and date
- Tee color stripe on the left edge
- Total score and score vs. par (e.g. `+8` in red, `-1` in green, `E` in black)
- A mini scorecard with every hole's score, color-coded (see [Score Color Coding](#7-score-color-coding))

Tap the card to open the full scorecard.

### Stat Row

Two elements sit below the best-round card:

| Element | What it shows |
|---|---|
| **Logged** | Total number of rounds ever logged |
| **GIR card** | Overall Greens in Regulation percentage plus bar charts for par 3, par 4, and par 5 (Detailed rounds only — shows `—` until you have at least one Detailed round) |

If stroke leaks are detected in your game, a **Priority Practice** card appears below the stat row. It shows the highest-priority drill category with suggested drills and a link to the full Analysis screen.

### Activity Heatmap

An 18-week calendar grid above the best-round card shows every day you played a round, completed a practice session, or both. Each cell is one day, aligned Monday–Sunday. Colors:

| Color | Meaning |
|---|---|
| **Light green** | Round played or practice session on that day |
| **Dark green** | Round and practice session both logged on the same day |
| **Empty** | No activity |

A legend below the grid labels the two filled states.

### New Session Button

The **New Session** button floats just above the tab bar. Tap it to choose:

| Option | What it starts |
|---|---|
| **Log a Round** | The round setup flow |
| **Practice Session** | An adaptive drill session based on your bag |

---

## 2. Logging a Round

Logging a round is a three-step flow: **Setup ▶ Entry ▶ Review & Save**.

---

### 2.1 Round Setup

The setup screen collects everything Galf needs before you start entering scores.

#### Club / Facility

A dropdown of all the clubs (golf facilities) you have added courses for. Select the facility you played at. The Course list below updates automatically.

#### Course

A list of courses at the selected facility. Tap a course name to select it — a green checkmark appears. If there is only one course at the facility it is pre-selected.

#### Tee Box

Colored pill buttons appear once a course is selected, one per tee box. Each pill shows the **color name** and the **Course Rating / Slope** (e.g. `72.1 / 128`). Tap the tee color you played from.

#### Holes

Choose how many holes you played:

| Option | When to use |
|---|---|
| **18 Holes** | Full round, holes 1–18 |
| **Front 9** | Only played holes 1–9 |
| **Back 9** | Only played holes 10–18 |

#### Date

Defaults to today. Tap to change. Useful when logging a round you played yesterday.

#### Round Type

| Option | Effect |
|---|---|
| **Solo** | Your own ball, normal stroke play |
| **Scramble** | Team format — automatically marks the round as Casual and excludes it from handicap |

#### Serious Round checkbox

When checked, the round counts toward your Handicap Index. Unchecked rounds are logged and visible in history but excluded from handicap calculation.

- Scramble rounds disable this checkbox automatically — scrambles never count
- Use **Casual** for practice rounds or rounds you don't want affecting your index

#### Simulator Round checkbox

Marks the round as a simulator round. Simulator rounds are tracked separately — they show a "Sim" pill on the scorecard and feed the **Best Sim** card on the Home screen. They do not affect the handicap of real rounds.

#### Entry Mode

| Mode | What you enter per hole |
|---|---|
| **Quick** | Score only — just a number |
| **Detailed** | Clubs used + putts — score is calculated automatically from the clubs you tap |

Detailed mode is required to unlock the Performance and Analysis stats screens. Quick mode is faster and good for casual rounds.

> Your last-used mode is remembered and pre-selected next time.

#### Start Entering Scores

Tap **▶ Start Entering Scores** when everything is set. You will be taken to the entry screen.

---

### 2.2 Quick Entry Mode

The Quick entry screen shows one hole at a time.

#### Top Bar

Shows the current **Hole number**, **Course name**, **Par**, **Yardage** (if entered for this course and tee), and **Tee color**.

#### Score Display

The large number in the center is your running score for the current hole. It shows `–` until you enter something. Beside or below it you will see your score vs. par (`E`, `+1`, `–2`, etc.).

#### Navigation

- **◀** — go back to the previous hole to correct a score. On hole 1, tapping ◀ exits the round without saving and returns to the Home screen.
- **▶** — jump forward (only works on holes already scored)

#### Numpad

Buttons 1–9 are individual digit taps. For scores of 10 or above, tap two digits in a row (e.g. tap `1` then `0` to enter 10). If the running total exceeds 20, the score resets to that last digit.

| Button | What it does |
|---|---|
| **1–9** | Sets / appends a digit to the current hole score |
| **0** | Appends a zero (e.g. `1` then `0` = score of 10) |
| **Forfeit** | Marks the hole with a score of par+2 (double bogey max). Used when you pick up or don't finish a hole. A confirmation prompt appears. |
| **Next ▶** | Moves to the next hole |
| **✓ Done** | Appears on the last hole — finishes entry and goes to the Review screen |

If you tap **Done** and any hole is missing a score, the app shows which hole numbers are incomplete and does not proceed.

---

### 2.3 Detailed Entry Mode

Detailed mode works differently — **your score is the number of clubs you tap**, including putts. You do not enter a number.

#### Top Bar

Same as Quick mode: hole number, course, par, yardage, tee.

#### Score Display

Shows the clubs tapped so far in sequence (e.g. `D ▶ 7i ▶ P`). A club currently being cycled through multi-tap appears in brackets (e.g. `D ▶ 7i ▶ [9i]`) until committed. The count of all clubs — including any pending — is your running score. Score vs. par updates in real time.

#### Club Suggestion

If yardages are entered for this course and tee, and you have clubs in your bag, Galf shows a **Suggested** club sequence for the hole yardage using a greedy algorithm:

> _Suggested: D ▶ 9i ▶ P_

It picks the longest club in your bag that fits the remaining distance, subtracts it, and repeats until the hole is covered. The putter can only appear once. If two clubs have the same distance, the one you use more often is preferred.

If no full club fits the remaining distance (e.g. 30 yards left after the last approach), Galf falls back to the nearest partial wedge swing — for example `SW ¾` or `PW ½`. Partial swings only appear in suggestions if you have entered partial distances for that wedge in the Clubs tab.

This is a starting point — not a prescription. You still tap whatever you actually hit.

#### Simulator Auto-Putts

If you checked **Simulator Round** in setup, Galf rolls a random putt count for each hole when you first arrive at it:

- 1 putt — 2.2% of holes
- 2 putts — 57.8% of holes
- 3 putts — 40% of holes

The rolled count appears as _"Sim putts: 2"_ on screen. If you tap the Putter button yourself, your taps override the auto-roll entirely (it will show _"(overridden)"_). If you tap no putts, the auto-rolled count is used when saving.

#### Club Keypad

Clubs are arranged in a **fixed 3×4 grid** — 9 club cells across the top three rows, and a fixed action row at the bottom. The layout never changes regardless of which clubs are in your bag.

```
Driver      │ Woods      │ Hybrids
Long (2i–4i)│ Mid (5i–7i)│ Short (8i–9i)
Wedges (hi) │ Wedges (lo)│ Putter
────────────┼────────────┼────────────
Forfeit     │ ◀ Undo     │ Next ▶
```

**Layout rules:**
- If you carry no hybrids, your woods are split evenly across the two top-row cells.
- All wedges (PW, GW, SW, LW) are pooled together, sorted longest carry first, and split evenly across the two wedge cells.
- The 5-iron sits in the Mid cell (5i–7i), not Long.

Cells that group more than one club (e.g. **3w · 5w**) use **Nokia-style multi-tap**: tap the cell once to select the first club, tap again before the timer fires to cycle to the next, and so on. After ~0.9 seconds of no input the selection is committed automatically. **Cells with only one club commit immediately** — no wait needed.

While a cell is cycling, the active club is displayed larger and the others are dimmed — you can always see all options in the cell at once.

The **Putter** cell is always in the bottom-right of the club area (above Next ▶) and is tinted green so it stands out.

Tap clubs in the order you hit them on the hole. The sequence appears in the score display as `D ▶ 7i ▶ [9i]` — brackets indicate a multi-tap selection that hasn't committed yet.

#### Action Row (always at the bottom)

| Button | What it does |
|---|---|
| **Forfeit** | Marks hole with par+2 (double bogey max). Confirmation required. |
| **◀ Undo** | If a multi-tap is in progress, cancels it. Otherwise removes the last committed club. |
| **Next ▶** / **✓ Done** | Commits any pending multi-tap, then advances to the next hole or finishes entry. |

---

### 2.4 Review & Save

After the last hole, you land on the **Review & Save** screen.

- A full scorecard is shown with your scores, pars, and totals — same layout as the Scorecard Viewer
- The tee-colored header shows the course name, date, total score, and score vs. par
- Pills show: hole selection (18 Holes / Front 9 / Back 9), round type, Casual (if not serious), Sim (if simulator), and tee color

#### Notes

An optional text field at the bottom. Use it to jot down anything about the round — conditions, what clicked, what didn't. Notes appear on the saved scorecard.

#### Save Round

Tap **Save Round** to write the round to your history. Your Handicap Index updates immediately. You are taken to the Rounds screen.

> The Review & Save screen has no back button. If you need to fix a score, use **◀** on the entry screen to step back through holes before tapping **✓ Done**.

---

## 3. Logbook

**Tab bar position:** left tab (logbook icon).

The Logbook is a date-sorted table of every round and practice session you have logged.

### Columns (rounds)

| Column | What it shows |
|---|---|
| **Date** | Date played (YYYY-MM-DD) |
| **Course** | Course name (truncated at 18 characters) |
| **Score** | Total strokes |
| **+/−** | Score vs. par — red for over, green for under, black for even |
| **Holes** | `18`, `F9` (Front 9), or `B9` (Back 9) |

Practice session rows show the session date, "Practice", and a completion percentage (drills completed out of total).

### Filter

Five buttons at the top filter the list:

| Filter | Shows |
|---|---|
| **All** | Rounds and practice sessions interleaved, most recent first |
| **Solo** | Only rounds logged as Solo |
| **Scramble** | Only rounds logged as Scramble |
| **Sim** | Only simulator rounds |
| **Practice** | Only practice sessions |

Rows are sorted **most recent first** in all views.

### Viewing a Round

Tap a round row to open that round's [Scorecard Viewer](#4-scorecard-viewer).

### Viewing a Practice Session

Tap a practice session row to expand it inline and see the drill results. Tap again to collapse.

---

## 4. Scorecard Viewer

The Scorecard Viewer shows a full breakdown of a saved round.

### Header Card

The header is tinted in the tee box color you played from:

- **Course name** and club/facility
- **Date** played and total yardage (if available)
- **Total score** and score vs. par in large type
- **Target score** — your par-plus-handicap target, and how you performed against it (e.g. `Target 80 (+3)`)

#### Pills

Small tags below the header show round metadata:

| Pill | Meaning |
|---|---|
| `18 Holes` / `Front 9` / `Back 9` | Which holes were played |
| `Solo` / `Scramble` | Round type |
| `Casual` | Round was not marked serious — not in handicap |
| `Sim` | Simulator round |
| colored dot + color name | Tee box played |

### Scorecard Grid

The traditional hole-by-hole grid appears for the front 9 and back 9 separately. Each grid shows:

- **Hole numbers** across the top
- **Yardage** row (if entered for this course and tee)
- **Par** row — par 3s in green, par 5s in the app's accent color, par 4s in the default
- **Score** row — each score is color-coded (see [Score Color Coding](#7-score-color-coding))

For 18-hole rounds, a **Totals row** appears between the two grids showing OUT (front 9), IN (back 9), TOTAL, PAR, and +/−.

### Notes

If you wrote notes when saving the round, they appear below the scorecard.

### Delete

Tap **Delete** at the bottom to permanently remove the round. A confirmation prompt appears. **This cannot be undone.** Your handicap recalculates automatically after deletion.

---

## 5. Courses

**Tab bar position:** right tab (golf course icon).

---

### 5.1 Course List

Courses are grouped by **Club / Facility** name, sorted alphabetically. Each course row shows:

- Course name
- Number of holes and total par
- Small colored dots for each tee box

Tap a course to open its [Course Detail](#52-course-detail) screen.

Tap **+ Add New Course** in the top-right to add a new one.

---

### 5.2 Course Detail

A read-only view of a course with everything Galf knows about it.

#### Header

Shows course name, facility name, and three stats: Holes, Par, and total Yards (for the currently selected tee).

#### Tee Pills

Tap a tee color to switch the yardage display. The selected tee's detail card shows:

| Field | What it is |
|---|---|
| **Rating** | Course Rating for this tee (e.g. `72.1`) |
| **Slope** | Slope Rating (e.g. `128`) |
| **Yards** | Total yardage for all holes combined |
| **HCP** | Calculated handicap differential for this tee — used internally for handicap math |

#### Hole Grid

A table with one row per hole showing hole number, par, and yardage. Par 3s are green, par 5s are the accent color. Front 9 subtotal (OUT), back 9 subtotal (IN), and a grand total (TOT) appear at the bottom.

#### Edit and Delete

- Tap **Edit Course** to open the editor
- Tap **Delete** to permanently remove the course. **Cannot be undone.**

---

### 5.3 Adding or Editing a Course

The Course Editor is used for both adding and editing. All fields work the same either way.

#### Course Information

| Field | What to enter |
|---|---|
| **Course Name** | The name of the specific course (e.g. `North Course`) |
| **Club / Facility** | The name of the golf club or facility (e.g. `Torrey Pines`). Courses are grouped by this in the list and the Log Round setup. |

#### Tee Boxes

Each tee box has three fields:

| Field | Where to find it |
|---|---|
| **Color** | The tee color name (e.g. `White`, `Blue`, `Red`). Any color name works — the app renders it visually. |
| **Rating** | Course Rating for this tee (on the scorecard, e.g. `72.1`) |
| **Slope** | Slope Rating (on the scorecard, e.g. `128`) |

Tap **+ Add Tee** to add another tee box. Tap the **✕** button on a tee card to remove it. You need at least one tee box to save.

#### Hole Pars & Yardages

A hole-by-hole grid with two columns per hole: **Par** and **Yardage**.

- Tap a tee color pill at the top to edit yardages for that specific tee — each tee has its own distances
- Par values are shared across all tees
- Yardages are optional — the app works without them, but they power the club suggestions during Detailed entry

Default par is 4 for all holes. Change any hole's par using the number input.

#### Save and Cancel

Tap **Save Course** to write changes. Tap **Cancel** to discard and go back.

---

### 5.4 Scanning a Physical Scorecard

Instead of entering course data by hand, you can photograph a real scorecard and let Galf read the pars, yardages, and tee ratings automatically.

#### Starting a Scan

Tap **+ Add New Course**, then tap the **Scan Card** button that appears at the top of the Add Course form. The Scan Scorecard screen opens.

#### Upload Step

Two buttons let you supply the image:

| Button | What it does |
|---|---|
| **Take Photo** | Opens the camera directly — point at the scorecard |
| **Choose File** | Opens the photo library or file browser |

A preview of the selected image appears. Tap **Scan This Card** to send it to the server. Processing takes 5–15 seconds.

> **Best results:** lay the card flat on a dark surface, use good lighting, and avoid glare. Shoot straight down — not at an angle.

#### 9-Hole Card Detected

If the scan finds only 9 holes of par values, Galf asks which 9 holes the card covers:

| Choice | Effect |
|---|---|
| **Front 9 — Holes 1–9** | Assigns extracted data to holes 1–9 |
| **Back 9 — Holes 10–18** | Assigns extracted data to holes 10–18 |
| **It's actually a full 18-hole card** | Treats all values as 18 holes (use this if the card fits on one page) |

#### Two Layouts Found

If the scan detects two separate 9-hole sections (common on cards that print both nines side by side), Galf asks how to save them:

| Choice | Effect |
|---|---|
| **One 18-hole course** | Combines both layouts into a single front+back course |
| **Save first layout only** | Saves holes from the first column of the card |
| **Save second layout only** | Saves holes from the second column of the card |

#### Review Screen

The extracted data is shown in an editable form before saving. A **confidence badge** indicates how much of the card was read cleanly:

- **Green (70%+)** — most fields were read correctly; spot-check
- **Orange (40–69%)** — review carefully; several fields may need correction
- **Red (below 40%)** — many fields need manual entry; the scan is a rough starting point

Fields highlighted in orange were not read and need to be filled in.

**What you can review and correct:**

- **Course Name** and **Club / Facility** — extracted from text at the top of the card
- **Tee Boxes** — each detected tee shows color (dropdown), label, rating, and slope
- **Hole Data table** — rows for Par, Handicap (HCP), and yardages per tee; scroll right to see all holes

Any warnings (unread holes, missing ratings, etc.) appear in an orange banner above the form.

#### Scanning a Second Photo

If the back of the card contains the second 9 holes, tap **Scan another photo (back of card / second 9)** at the bottom of the review screen to upload a second image without losing what was already extracted.

#### Saving

Tap **Save Course** when the data looks correct. The course is added to your library just as if you had entered it by hand.

> Scan Card requires optional server-side dependencies (Tesseract + OpenCV). If these are not installed, the feature is unavailable on that server.

---

## 6. Statistics

The Statistics screen is reached by tapping the **Stats** cell on the Home screen. It has four sub-tabs.

---

### 6.1 Overview

A summary of your overall game.

**Handicap Index** — shown large at the top, to one decimal place (e.g. `12.3`). Color: green under 15, accent 15–25, orange 25+.

Below the handicap, four quick-stat cells:

| Cell | What it means |
|---|---|
| **Total Rounds** | Every round ever logged (all types) |
| **Best Round** | Your lowest score vs. par — shown as the total score with the diff (e.g. `82 (+10)`) |
| **Avg Score (9h)** | Average total score across serious 9-hole rounds only |
| **Holes Played** | Total holes logged in serious solo rounds — tracks progress toward the 54-hole handicap threshold |

Below the quick numbers, a list of your **top 8 score differentials** sorted best to worst. Each row shows the course, date, hole count, raw score, and the computed differential. The top 3 are highlighted green — these are the rounds carrying the most weight in your handicap.

---

### 6.2 Performance

**Requires Detailed entry mode.** Shows nothing until you have at least one Detailed round.

#### Greens in Regulation (GIR)

A circular ring chart showing what percentage of holes you reached the green in regulation. Ring color:

- Green — 30% or above (amateur target)
- Orange — 20–29%
- Red — below 20%

Below the ring, GIR is broken down by par 3, par 4, and par 5.

#### Putting

Average putts per hole. Color:

- Green — 2.0 or below
- Accent — 2.0–2.5
- Red — above 2.5

Also shows 1-putt, 2-putt, and 3-putt rates. Tour average is ~1.8. A high 3-putt rate (above 25%) is highlighted red.

#### Scramble Rate

Percentage of holes where you missed the green in regulation but still made bogey or better. Shown as a smaller ring.

- Green — 30% or above
- Orange — 15–29%
- Red — below 15%

#### Avg Strokes to Green (Par 4)

How many strokes on average it takes you to reach the green on par 4 holes. Target is 2.0 (meaning you hit the green in regulation). Higher numbers indicate approach shot struggles.

---

### 6.3 Clubs

Your bag with distance and usage data.

#### My Bag List

Each club appears as a row with:

- **Club name**
- **Bar** — horizontal bar showing relative carry distance (or usage frequency if you have detailed rounds)
- **Carry distance** in yards
- **Usage %** — what percentage of all logged shots were with this club (only shown once you have detailed rounds)

The bag sorts by **usage frequency** once you have detailed rounds, so your most-used clubs rise to the top. Before any detailed rounds it sorts by distance, longest to shortest. The putter is always last.

#### Editing a Club

Tap any club row to expand it. You can:

- Change the **carry distance** (labeled **Full**) and tap **Save**
- For wedge clubs (PW, GW, SW, LW), set optional partial swing distances — **¾ swing**, **½ swing**, and **¼ swing** — in yards. Leave any blank if you don't use that partial. These values feed the partial-swing fallback in Detailed mode club suggestions.
- Tap **Remove** to delete the club from your bag (confirmation required)
- Tap **Cancel** to collapse without changes

#### Adding a Club

Tap **+ Add Club** at the bottom of the list. A new panel appears:

1. Select the club name from the dropdown (only clubs not already in your bag appear)
2. Enter the carry distance in yards
3. Tap **Add to Bag**

Once all standard clubs are added, the **+ Add Club** button disappears.

---

### 6.4 Analysis

**Requires Detailed entry mode.** Shows areas where you are losing the most strokes.

Galf calculates **stroke leaks** — parts of your game that are costing you more shots than average. Each leak appears as a card with:

- **Priority badge** — 🔴 High Priority or 🟡 Medium Priority
- **Description** of the issue (e.g. _"Your 3-putt rate is 42% — significantly above average"_)
- **Tip** — a specific practice suggestion for that area

#### Leak areas Galf tracks

| Area | What triggers it |
|---|---|
| Putting / 3-putts | High 3-putt rate or high avg putts |
| Tee shots on par 3 | Frequently missing the green from the tee on par 3s |
| Approach shots | Consistently too many strokes to reach the green on par 4s |
| GIR | Low green-in-regulation percentage overall |

If no significant leaks are found, the screen shows a celebration message instead.

> Focus on one area at a time. Track progress over multiple rounds — single-round improvements are noise, trends over 5–10 rounds are signal.

---

## 7. Practice Sessions

Start a practice session from the **New Session** button on the Home screen → **Practice Session**.

Galf builds a drill template automatically from the clubs in your bag. No bag configured = only the always-included categories appear.

---

### 7.1 Drill Categories

| Category | Always shown? | Condition |
|---|---|---|
| **Range Warm-Up** | Yes | — |
| **Putting** | Yes | — |
| **Chipping** | No | You have GW, SW, or LW in your bag |
| **Wedge Matrix** | No | You have any wedge (PW, GW, SW, or LW) in your bag |
| **Irons** | No | You have any iron or hybrid |
| **Woods** | No | You have Driver or any fairway wood |

Irons are listed short-to-long (9i first). Woods are listed short-to-long (7w first, Driver last).

---

### 7.2 Drill Types

| Type | How you record it |
|---|---|
| **Check** | Tap the circle to mark done |
| **Streak** | Enter your best consecutive streak with the number field |
| **Count** | Tap **+** / **−** to count makes or reps; auto-marks done when target is reached |
| **Wedge Matrix** | Tap each swing-length button (Full / ¾ / ½ / ¼) per wedge; enter how many of 10 balls carried within ±5 yards of your stored distance. See [7.3 Wedge Matrix](#73-wedge-matrix) |

Tap the circle on any drill to toggle it done/not-done regardless of type.

---

### 7.3 Wedge Matrix

The Wedge Matrix is a dedicated calibration drill for all your wedges. It appears once per session and covers every wedge in your bag (PW, GW, SW, LW) across four swing lengths: **Full**, **¾**, **½**, and **¼**.

**How it works:**

1. Tap a swing-length button for a wedge (e.g. **¾ SW**). The button shows your stored carry distance for that swing.
2. Hit 10 balls trying to match that distance.
3. Enter how many carried within ±5 yards of the target.
4. Repeat for each swing length and club.

If you consistently hit more balls in range than your stored distance reflects, tap **Update** next to the result — this queues a distance update. When you tap **Save Session**, all queued updates are written back to your club bag automatically. Your partial distances are now current without ever opening the Clubs tab.

> Buttons with no stored distance are dimmed. To activate them, go to the Clubs tab, tap a wedge, and enter distances for the partial swings you want to track.

---

### 7.4 Saving a Session

Tap **Save Session** at the bottom of the drill list. The session is stored with its date, drill results, and any notes you add at the top.

If the session included a Wedge Matrix drill, any distance updates you queued are saved to your club bag at the same time.

Completed sessions appear in the [Logbook](#3-logbook) under the **Practice** filter and in the **All** view.

---

## 8. Score Color Coding

Every score in the app — on scorecards, the home best-round card, and the log entry screen — uses the same color system:

| Visual style | Color | Name | Score vs. Par |
|---|---|---|---|
| Score in a **double circle** | Yellow | Eagle or better | −2 or better |
| Score in a **circle** | Green | Birdie | −1 |
| Plain score | Default text | Par | Even |
| Score in a **square** | Red | Bogey | +1 |
| Score in a **double square** | Red | Double bogey or worse | +2 or worse |

---

*That covers every screen and every option in Galf. If something behaves unexpectedly, check that you have at least one course added and that Detailed entry mode was used for the rounds you want performance stats from.*
