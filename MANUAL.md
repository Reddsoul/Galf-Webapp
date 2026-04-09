<h1>
  <span style="display:inline-flex;align-items:center;justify-content:center;background:#1B6B3A;border-radius:12px;padding:6px;line-height:0;vertical-align:middle"><img src="static/Favicon-96.png" width="32" height="32"></span>
  Galf — User Manual
</h1>

Everything the app can do, screen by screen.

---

## Table of Contents

1. [Home Screen](#1-home-screen)
2. [Logging a Round](#2-logging-a-round)
   - [Round Setup](#21-round-setup)
   - [Quick Entry Mode](#22-quick-entry-mode)
   - [Detailed Entry Mode](#23-detailed-entry-mode)
   - [Review & Save](#24-review--save)
3. [Rounds History](#3-rounds-history)
4. [Scorecard Viewer](#4-scorecard-viewer)
5. [Courses](#5-courses)
   - [Course List](#51-course-list)
   - [Course Detail](#52-course-detail)
   - [Adding or Editing a Course](#53-adding-or-editing-a-course)
6. [Statistics](#6-statistics)
   - [Overview](#61-overview)
   - [Performance](#62-performance)
   - [Clubs](#63-clubs)
   - [Analysis](#64-analysis)
7. [Score Color Coding](#7-score-color-coding)

---

## 1. Home Screen

The Home screen is the first thing you see when you open Galf. It is your dashboard.

<img src="static/Favicon-96.png" width="16" style="vertical-align:middle"> **Tab bar position:** center tab.

### Handicap Index

The large number at the top is your **WHS Handicap Index**, calculated using your last 20 rounds following USGA rules.

- Shows `--` until you have logged **54 holes** of serious play
- Beneath the dashes it tells you how many more holes you need: _"Play 38 more holes to establish"_
- Once established, the number updates automatically every time you save a new round

### Best Round Cards

Below the handicap, Galf shows one card for your **Best IRL** round and one for your **Best Sim** round (if any simulator rounds exist). Each card shows:

- Course name and date
- Tee color stripe on the left edge
- Total score and score vs. par (e.g. `+8` in red, `-1` in green, `E` in black)
- A mini scorecard with every hole's score, color-coded (see [Score Color Coding](#7-score-color-coding))

Tap the card to open the full scorecard.

### Stat Row

Three cells sit below the best-round cards:

| Cell | What it shows |
|---|---|
| **Rounds** | Total number of rounds ever logged |
| **GIR** | Greens in Regulation percentage (from Detailed rounds only) |
| <span style="display:inline-flex;align-items:center;justify-content:center;background:#1B6B3A;border-radius:5px;padding:2px;line-height:0;vertical-align:middle"><img src="static/golf-clubs-96.png" width="14" height="14"></span> **Stats** | Tap this to open the full Statistics screen |

### Log New Round Button

The <span style="display:inline-flex;align-items:center;justify-content:center;background:#1B6B3A;border-radius:5px;padding:2px;line-height:0;vertical-align:middle"><img src="static/golf-ball-w-96.png" width="14" height="14"></span> **Log New Round** button floats just above the tab bar. Tap it from anywhere on the Home screen to start logging.

---

## 2. Logging a Round

Logging a round is a three-step flow: **Setup → Entry → Review & Save**.

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

- **◀** — go back to the previous hole to correct a score
- **▶** — jump forward (only works on holes already scored)

#### Numpad

Buttons 1–9 are individual digit taps. For scores of 10 or above, tap two digits in a row (e.g. tap `1` then `0` to enter 10). If you tap a third digit, the score resets to that single digit — so you can never accidentally enter a 3-digit score.

| Button | What it does |
|---|---|
| **1–9** | Sets / appends a digit to the current hole score |
| **0** | Appends a zero (e.g. `1` then `0` = score of 10) |
| **Forfeit** | Marks the hole with a score of 0. Used when you pick up or don't finish a hole. A confirmation prompt appears. |
| **Next →** | Moves to the next hole |
| **✓ Done** | Appears on the last hole — finishes entry and goes to the Review screen |

If you tap **Done** and any hole is missing a score, the app shows which hole numbers are incomplete and does not proceed.

---

### 2.3 Detailed Entry Mode

Detailed mode works differently — **your score is the number of clubs you tap**, including putts. You do not enter a number.

#### Top Bar

Same as Quick mode: hole number, course, par, yardage, tee.

#### Score Display

Shows the clubs you have tapped so far in sequence (e.g. `D → 7i → P`). The count of those clubs is your score. The score vs. par updates in real time.

#### Club Suggestion

If yardages are entered for this course and tee, and you have clubs in your bag, Galf shows a **Suggested** club sequence for the hole yardage using a greedy algorithm:

> _Suggested: D → 9i → P_

It picks the longest club in your bag that fits the remaining distance, subtracts it, and repeats until the hole is covered. The putter can only appear once. If two clubs have the same distance, the one you use more often is preferred.

This is a starting point — not a prescription. You still tap whatever you actually hit.

#### Simulator Auto-Putts

If you checked **Simulator Round** in setup, Galf rolls a random putt count for each hole when you first arrive at it:

- 1 putt — 2.2% of holes
- 2 putts — 57.8% of holes
- 3 putts — 40% of holes

The rolled count appears as _"Sim putts: 2"_ on screen. If you tap the Putter button yourself, your taps override the auto-roll entirely (it will show _"(overridden)"_). If you tap no putts, the auto-rolled count is used when saving.

#### Club Grid Buttons

Every club in your bag appears as an abbreviated button:

| Abbreviation | Club |
|---|---|
| D | Driver |
| 3W, 5W | 3 Wood, 5 Wood |
| H | Hybrid |
| 3i, 4i, 5i, 6i, 7i, 8i, 9i | Irons |
| PW, GW, SW, LW | Wedges |
| P | Putter |

Tap clubs in the order you hit them on the hole. The putter button is styled differently so it's easy to find at the bottom of the grid.

#### Action Row (bottom of club grid)

| Button | What it does |
|---|---|
| **Forfeit** | Marks hole with score 0 and clubs `[X]`. Confirmation required. |
| **↩ Undo** | Removes the last club tapped — useful if you tap the wrong one |
| **Next →** / **✓ Done** | Advances to next hole or finishes entry |

---

### 2.4 Review & Save

After the last hole, you land on the **Review & Save** screen.

- A full scorecard is shown with your scores, pars, and totals — same layout as the Scorecard Viewer
- The tee-colored header shows the course name, date, total score, and score vs. par
- Pills show: hole selection (18 Holes / Front 9 / Back 9), round type, Casual (if not serious), Sim (if simulator), and tee color

#### Notes

An optional text field at the bottom. Use it to jot down anything about the round — conditions, what clicked, what didn't. Notes appear on the saved scorecard.

#### Save Round

Tap <span style="display:inline-flex;align-items:center;justify-content:center;background:#1B6B3A;border-radius:5px;padding:2px;line-height:0;vertical-align:middle"><img src="static/save-96.png" width="14" height="14"></span> **Save Round** to write the round to your history. Your Handicap Index updates immediately. You are taken to the Rounds screen.

#### Back to Scoring

Tap **← Back to Scoring** at the top to return to the entry screen and make corrections before saving.

---

## 3. Rounds History

<img src="static/golf-cart-96.png" width="16" style="vertical-align:middle"> **Tab bar position:** left tab.

The Rounds screen is a table of every round you have logged.

### Columns

| Column | What it shows |
|---|---|
| **Date** | Date played (YYYY-MM-DD) |
| **Course** | Course name (truncated at 18 characters) |
| **Score** | Total strokes |
| **+/−** | Score vs. par — red for over, green for under, black for even |
| **Holes** | `18`, `F9` (Front 9), or `B9` (Back 9) |

### Filter

Three buttons at the top filter the list:

| Filter | Shows |
|---|---|
| **All** | Every round regardless of type |
| **Solo** | Only rounds logged as Solo |
| **Scramble** | Only rounds logged as Scramble |

Rounds are always sorted **most recent first**. There is no sort option on this screen.

### Viewing a Round

Tap any row to open that round's [Scorecard Viewer](#4-scorecard-viewer).

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

Tap <span style="display:inline-flex;align-items:center;justify-content:center;background:#FF3B30;border-radius:5px;padding:2px;line-height:0;vertical-align:middle"><img src="static/trash-96.png" width="14" height="14"></span> **Delete** at the bottom to permanently remove the round. A confirmation prompt appears. **This cannot be undone.** Your handicap recalculates automatically after deletion.

---

## 5. Courses

<img src="static/golf-course-96.png" width="16" style="vertical-align:middle"> **Tab bar position:** right tab.

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

A table with one row per hole showing hole number, par, and yardage. Par 3s are green, par 5s are the accent color. Front 9 and back 9 subtotals (OUT) and a grand total (TOT) appear at the bottom.

#### Edit and Delete

- Tap <span style="display:inline-flex;align-items:center;justify-content:center;background:#1B6B3A;border-radius:5px;padding:2px;line-height:0;vertical-align:middle"><img src="static/pencil-96.png" width="14" height="14"></span> **Edit Course** to open the editor
- Tap <span style="display:inline-flex;align-items:center;justify-content:center;background:#FF3B30;border-radius:5px;padding:2px;line-height:0;vertical-align:middle"><img src="static/trash-96.png" width="14" height="14"></span> to delete the course. **Cannot be undone.**

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

Tap <span style="display:inline-flex;align-items:center;justify-content:center;background:#1B6B3A;border-radius:5px;padding:2px;line-height:0;vertical-align:middle"><img src="static/save-96.png" width="14" height="14"></span> **Save Course** to write changes. Tap **Cancel** to discard and go back.

---

## 6. Statistics

The Statistics screen is reached by tapping any stat cell on the Home screen. It has four sub-tabs.

---

### 6.1 Overview

A summary of your overall game.

**Handicap Index** — shown large at the top, to one decimal place (e.g. `12.3`). Color: green under 15, accent 15–25, orange 25+. Note: the Home screen rounds this up to the nearest whole number — the full decimal is only shown here.

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

Percentage of holes where you missed the green in regulation but still made par or better. Shown as a smaller ring.

- Green — 30% or above
- Orange — 15–29%
- Red — below 15%

#### Avg Strokes to Green (Par 4)

How many strokes on average it takes you to reach the green on par 4 holes. Target is 2.0 (meaning you hit the green in regulation). Higher numbers indicate approach shot struggles.

#### Fairways in Regulation

Percentage of par 4 and par 5 holes where your tee shot landed in the fairway. Only appears if fairway data is available from your rounds.

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

- Change the **carry distance** and tap <span style="display:inline-flex;align-items:center;justify-content:center;background:#1B6B3A;border-radius:5px;padding:2px;line-height:0;vertical-align:middle"><img src="static/save-96.png" width="14" height="14"></span> **Save**
- Tap **Remove** to delete the club from your bag (confirmation required)
- Tap **Cancel** to collapse without changes

#### Adding a Club

Tap **+ Add Club** at the bottom of the list. A new panel appears:

1. Select the club name from the dropdown (only clubs not already in your bag appear)
2. Enter the carry distance in yards
3. Tap <span style="display:inline-flex;align-items:center;justify-content:center;background:#1B6B3A;border-radius:5px;padding:2px;line-height:0;vertical-align:middle"><img src="static/save-96.png" width="14" height="14"></span> **Add to Bag**

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
| Approach shots | Consistently too many strokes to reach the green |
| GIR | Low green-in-regulation percentage overall |
| Fairways | Low fairway hit rate |
| Scrambling | Low scramble rate when missing greens |

If no significant leaks are found, the screen shows a celebration message instead.

> Focus on one area at a time. Track progress over multiple rounds — single-round improvements are noise, trends over 5–10 rounds are signal.

---

## 7. Score Color Coding

Every score in the app — on scorecards, the home best-round card, and the log entry screen — uses the same color system:

| Visual style | Color | Name | Score vs. Par |
|---|---|---|---|
| Score in a **double circle** | Yellow | Eagle or better | −2 or better |
| Score in a **circle** | Green | Birdie | −1 |
| Plain score | Default text | Par | Even |
| Score in a **square** | Red | Bogey | +1 |
| Score in a **double square** | Red | Double bogey or worse | +2 or worse |

---

*That covers every screen and every option in Galf. If something behaves unexpectedly, check that you have at least one course added and that Detailed entry mode was used for the rounds you want stats from.*
