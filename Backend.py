import math
import os
import shutil
import sys
from collections import defaultdict
from statistics import mean
from datetime import datetime

from sqlalchemy.orm import selectinload

from models import db, Course, TeeBox, Round, Club, UserPrefs, StatsCache, TrainingSession

# Club categories for analytics (category is the only field used)
CLUB_CATEGORIES = {
    "Driver": "driver",
    "3 Wood": "wood",   "5 Wood": "wood",   "7 Wood": "wood",
    "Hybrid": "hybrid", "2 Hybrid": "hybrid", "3 Hybrid": "hybrid",
    "4 Hybrid": "hybrid", "5 Hybrid": "hybrid",
    "2 Iron": "iron",   "3 Iron": "iron",   "4 Iron": "iron",
    "5 Iron": "iron",   "6 Iron": "iron",   "7 Iron": "iron",
    "8 Iron": "iron",   "9 Iron": "iron",
    "PW": "wedge",      "GW": "wedge",      "SW": "wedge",      "LW": "wedge",
    "Putter": "putter",
}

_STATS_CACHE_VERSION = 4


def _round_to_dict(r):
    return {
        "id": r.id,
        "course_name": r.course_name,
        "tee_color": r.tee_color,
        "date": r.date,
        "total_score": r.total_score,
        "par": r.par,
        "tee_rating": r.tee_rating,
        "tee_slope": r.tee_slope,
        "target_score": r.target_score,
        "holes_played": r.holes_played,
        "holes_choice": r.holes_choice,
        "round_type": r.round_type,
        "is_serious": r.is_serious,
        "is_sim": r.is_sim,
        "notes": r.notes,
        "scores": r.scores or [],
        "detailed_stats": r.detailed_stats or [],
        "pars": r.pars,
        "hole_hcp": r.hole_hcp,
        "course_handicap": r.course_handicap,
    }


def normalize_tee_color(color):
    """Title-case a tee color name: "red" -> "Red", "dark blue" -> "Dark Blue"."""
    return " ".join(w.capitalize() for w in str(color).strip().split())


# Defaults for the settings bag; unknown keys sent by the client are ignored.
DEFAULT_SETTINGS = {
    "theme": "green",           # "green" | "burgundy"
    "ocr_enabled": True,        # show Scan Card + allow /api/courses/scan
    "sim_in_handicap": False,   # opt in: serious sim rounds feed the handicap index
    # Scan LLM — no defaults. Written only by /api/ocr/test after a
    # successful connection test (see app.py); not settable via PUT /api/prefs.
    "ocr_llm_url": "",
    "ocr_llm_model": "",
    "ocr_llm_api_key": "",      # never sent to the client
    "ocr_llm_verified": False,
    "show_hole_hcp": True,      # HCP (stroke index) row on scorecards
    "home_club": "",            # club string shared by the user's home courses
}
SETTINGS_KEYS = tuple(DEFAULT_SETTINGS)


def normalize_existing_tee_colors():
    """One-time cleanup: canonicalize tee colors already stored in lowercase.
    Raw SQL so it runs before later migrations add ORM-mapped columns."""
    changed = 0
    for table, col in (("tee_boxes", "color"), ("rounds", "tee_color")):
        rows = db.session.execute(db.text(f"SELECT id, {col} FROM {table}")).all()
        for row_id, color in rows:
            if not color:
                continue
            fixed = normalize_tee_color(color)
            if fixed != color:
                db.session.execute(db.text(f"UPDATE {table} SET {col} = :c WHERE id = :i"),
                                   {"c": fixed, "i": row_id})
                changed += 1
    if changed:
        db.session.commit()
    return changed


def _columns(table):
    return {row[1] for row in db.session.execute(db.text(f"PRAGMA table_info({table})"))}


def _add_column(table, column, decl):
    if column not in _columns(table):
        db.session.execute(db.text(f"ALTER TABLE {table} ADD COLUMN {column} {decl}"))


def _migrate_v1():
    """Columns added before versioning existed, plus the one-time tee color
    cleanup that used to run on every boot."""
    _add_column("clubs", "in_bag", "INTEGER DEFAULT 1")
    _add_column("user_prefs", "settings", "JSON")
    db.session.commit()
    normalize_existing_tee_colors()


def _migrate_v2():
    """Per-hole handicap on courses, course snapshot on rounds, and one row
    per (user, course name)."""
    _add_column("courses", "hole_hcp", "JSON")
    _add_column("rounds", "pars", "JSON")
    _add_column("rounds", "hole_hcp", "JSON")
    _add_column("rounds", "course_handicap", "INTEGER")
    db.session.commit()

    # Dedupe courses by (user_id, name): keep the lowest id, move tee boxes
    # it lacks over from the duplicates, then drop the duplicates.
    dupes = db.session.execute(db.text(
        "SELECT user_id, name FROM courses GROUP BY user_id, name HAVING COUNT(*) > 1"
    )).all()
    for user_id, name in dupes:
        rows = (Course.query.filter_by(user_id=user_id, name=name)
                .order_by(Course.id).all())
        keep, extra = rows[0], rows[1:]
        have = {tb.color for tb in keep.tee_boxes}
        for c in extra:
            for tb in list(c.tee_boxes):
                if tb.color not in have:
                    tb.course_id = keep.id
                    have.add(tb.color)
            db.session.flush()
            db.session.expire(c)
            db.session.delete(c)
        db.session.commit()
    db.session.execute(db.text(
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_courses_user_name ON courses (user_id, name)"
    ))
    db.session.commit()


# Ordered ladder: index i migrates user_version i -> i+1. Steps must be
# idempotent so a crash mid-step is safe to re-run.
_MIGRATIONS = [_migrate_v1, _migrate_v2]
SCHEMA_VERSION = len(_MIGRATIONS)


def run_migrations(db_path=None):
    """Bring the SQLite file up to SCHEMA_VERSION (create_all won't alter
    existing tables). Copies the DB to galf.db.bak-v{N} before migrating."""
    current = db.session.execute(db.text("PRAGMA user_version")).scalar() or 0
    if current >= SCHEMA_VERSION:
        return current
    has_data = db.session.execute(db.text("SELECT 1 FROM rounds LIMIT 1")).first()
    if db_path and os.path.exists(db_path) and has_data:
        shutil.copy2(db_path, f"{db_path}.bak-v{current}")
    for version in range(current, SCHEMA_VERSION):
        _MIGRATIONS[version]()
        db.session.execute(db.text(f"PRAGMA user_version = {version + 1}"))
        db.session.commit()
        print(f"[galf] migrated schema to v{version + 1}", file=sys.stderr)
    return SCHEMA_VERSION


def _course_to_dict(c):
    tee_boxes = []
    yardages = {}
    for tb in c.tee_boxes:
        tee_boxes.append({"color": tb.color, "rating": tb.rating, "slope": tb.slope, "handicap": tb.handicap})
        yardages[tb.color] = tb.yardages or []
    return {
        "name": c.name,
        "club": c.club or "",
        "pars": c.pars or [],
        "hole_hcp": c.hole_hcp,
        "tee_boxes": tee_boxes,
        "yardages": yardages,
    }


def _club_to_dict(c):
    d = {"name": c.name, "distance": c.distance, "notes": c.notes or "", "in_bag": c.in_bag if c.in_bag is not None else True}
    if c.partials:
        d["partials"] = c.partials
    return d


# ---- WHS helpers ----

def course_handicap(index, slope, rating, par, nine=False, full_par=None):
    """WHS course handicap: index x slope/113 + (rating - par), rounded.

    9-hole rounds: a rating under 50 is a 9-hole rating and pairs with the
    9-hole par and half the index; an 18-hole rating gives the 18-hole course
    handicap halved (same <50 rule as _pair_nine_holes)."""
    if index is None or not slope or rating is None:
        return None
    if nine:
        if rating < 50:
            return round(index / 2 * slope / 113 + (rating - par))
        return round((index * slope / 113 + (rating - (full_par or par * 2))) / 2)
    return round(index * slope / 113 + (rating - par))


def strokes_per_hole(ch, hcps):
    """Handicap strokes received on each hole (WHS stroke allocation).

    hcps: stroke index of each played hole, in play order. Holes are ranked
    hardest (lowest index) first; every hole gets ch // n strokes and the
    ch % n hardest get one more. A plus handicap (ch < 0) gives strokes back
    on the easiest holes instead."""
    n = len(hcps)
    if not n or ch is None:
        return [0] * n
    order = sorted(range(n), key=lambda i: hcps[i])
    out = [0] * n
    if ch >= 0:
        base, extra = divmod(ch, n)
        for rank, i in enumerate(order):
            out[i] = base + (1 if rank < extra else 0)
    else:
        base, extra = divmod(-ch, n)
        for rank, i in enumerate(reversed(order)):
            out[i] = -(base + (1 if rank < extra else 0))
    return out


def _is_nine(r):
    return r.get("holes_choice") in ("front_9", "back_9") or r.get("holes_played") == 9


def round_hole_layout(r, course):
    """(played hole indexes, pars, hole_hcp) for a round. Prefers the round's
    own snapshot; falls back to the course row for rounds saved before it.
    hole_hcp is None when unknown or misaligned with pars."""
    pars = r.get("pars") or (course or {}).get("pars") or []
    hcp = r.get("hole_hcp") or (course or {}).get("hole_hcp")
    if hcp and len(hcp) != len(pars):
        hcp = None
    scores = r.get("scores") or []
    holes = [i for i, v in enumerate(scores)
             if isinstance(v, (int, float)) and not isinstance(v, bool) and i < len(pars)]
    return holes, pars, hcp


def adjusted_gross(r, index, course):
    """WHS adjusted gross score: each hole capped at net double bogey
    (par + 2 + strokes received), or par + 5 before an index exists.
    Rounds without per-hole scores keep their total. Without a hole HCP row,
    strokes are spread evenly (ceil(ch / n) per hole) — lenient, never harsher
    than the true cap."""
    total = r.get("total_score")
    holes, pars, hcp = round_hole_layout(r, course)
    if not holes or total is None:
        return total
    scores = r["scores"]
    if index is None:
        caps = [pars[i] + 5 for i in holes]
    else:
        par = sum(pars[i] for i in holes)
        ch = course_handicap(index, r.get("tee_slope"), r.get("tee_rating"), par,
                             nine=_is_nine(r), full_par=sum(pars))
        if ch is None:
            caps = [pars[i] + 5 for i in holes]
        elif hcp:
            given = strokes_per_hole(ch, [hcp[i] for i in holes])
            caps = [pars[i] + 2 + g for i, g in zip(holes, given)]
        else:
            even = math.ceil(ch / len(holes)) if ch > 0 else 0
            caps = [pars[i] + 2 + even for i in holes]
    excess = sum(max(0, scores[i] - cap) for i, cap in zip(holes, caps))
    return total - excess


def _differential(score, rating, slope):
    try:
        return round((113 * (score - rating)) / slope, 1)
    except (ZeroDivisionError, TypeError):
        return None


class GolfBackend:
    def __init__(self, user_id=1):
        self.user_id = user_id
        self._user_prefs_cache = None

    @property
    def user_prefs(self):
        if self._user_prefs_cache is None:
            self._user_prefs_cache = self._load_user_prefs()
        return self._user_prefs_cache

    # --- user prefs ---

    def _load_user_prefs(self):
        row = db.session.get(UserPrefs, self.user_id)
        d = dict(DEFAULT_SETTINGS)
        d["entry_mode"] = "quick"
        if row:
            d["entry_mode"] = row.entry_mode or "quick"
            if row.preferred_tee:
                d["preferred_tee"] = row.preferred_tee
            for k, v in (row.settings or {}).items():
                if k in DEFAULT_SETTINGS:
                    d[k] = v
        return d

    def save_user_prefs(self):
        settings = {k: self.user_prefs.get(k, DEFAULT_SETTINGS[k]) for k in SETTINGS_KEYS}
        row = db.session.get(UserPrefs, self.user_id)
        if row:
            row.entry_mode = self.user_prefs.get("entry_mode", "quick")
            row.preferred_tee = self.user_prefs.get("preferred_tee")
            row.settings = settings
        else:
            row = UserPrefs(
                user_id=self.user_id,
                entry_mode=self.user_prefs.get("entry_mode", "quick"),
                preferred_tee=self.user_prefs.get("preferred_tee"),
                settings=settings,
            )
            db.session.add(row)
        db.session.commit()

    # --- stats cache ---

    def invalidate_stats_cache(self):
        row = db.session.get(StatsCache, self.user_id)
        if row:
            row.valid = False
        else:
            row = StatsCache(user_id=self.user_id, valid=False, version=0, data=None)
            db.session.add(row)
        db.session.commit()

    # --- courses ---

    def get_courses(self):
        played = {
            name: (last, n)
            for name, last, n in db.session.query(
                Round.course_name, db.func.max(Round.date), db.func.count(Round.id)
            ).filter(Round.user_id == self.user_id).group_by(Round.course_name)
        }
        out = []
        for c in (Course.query.options(selectinload(Course.tee_boxes))
                  .filter_by(user_id=self.user_id).all()):
            d = _course_to_dict(c)
            last, n = played.get(c.name, (None, 0))
            d["last_played"] = last
            d["rounds_count"] = n
            out.append(d)
        return out

    def get_course_by_name(self, name):
        c = (Course.query.options(selectinload(Course.tee_boxes))
             .filter_by(user_id=self.user_id, name=name).first())
        return _course_to_dict(c) if c else None

    @staticmethod
    def _clean_hole_hcp(raw, n_holes):
        """Validate a per-hole handicap row. Blank -> None. Otherwise one
        distinct int 1-18 per hole (9-hole cards often print odds or evens)."""
        if not raw or all(v in (None, "", 0) for v in raw):
            return None
        if not isinstance(raw, list) or len(raw) != n_holes:
            raise ValueError(f"Hole handicaps must list all {n_holes} holes")
        vals = []
        for i, v in enumerate(raw):
            if isinstance(v, bool) or not isinstance(v, (int, float, str)):
                raise ValueError(f"Hole {i + 1}: handicap missing")
            try:
                iv = int(v)
            except (TypeError, ValueError):
                raise ValueError(f"Hole {i + 1}: handicap missing")
            if not 1 <= iv <= 18:
                raise ValueError(f"Hole {i + 1}: handicap must be 1-18")
            vals.append(iv)
        if len(set(vals)) != len(vals):
            raise ValueError("Hole handicaps must not repeat")
        return vals

    def _prepare_course_data(self, course_data):
        name = str(course_data.get("name") or "").strip()
        if not name:
            raise ValueError("Course name is required")
        course_data["name"] = name
        course_data["club"] = str(course_data.get("club") or "").strip()
        pars = course_data.get("pars")
        if (not isinstance(pars, list) or len(pars) < 9
                or not all(isinstance(p, int) and not isinstance(p, bool) and 3 <= p <= 6 for p in pars)):
            raise ValueError("Course pars are required (9+ holes, 3-6 each)")
        course_data["hole_hcp"] = self._clean_hole_hcp(course_data.get("hole_hcp"), len(pars))
        par_total = sum(pars)
        yardages = course_data.get("yardages") or {}
        if not isinstance(course_data.get("tee_boxes"), list):
            raise ValueError("Tee boxes are required")
        for box in course_data["tee_boxes"]:
            # Canonical tee color ("red" -> "Red") so color lookups and round
            # matching are case-stable everywhere.
            raw = box.get("color") or ""
            box["color"] = normalize_tee_color(raw)
            if raw in yardages and raw != box["color"]:
                yardages[box["color"]] = yardages.pop(raw)
            rating = box.get("rating")
            box["handicap"] = round(rating - par_total, 1) if rating is not None else None
        course_data["yardages"] = yardages

    def _add_tee_boxes(self, course, course_data):
        yardages_map = course_data.get("yardages", {})
        for tb in course_data.get("tee_boxes", []):
            db.session.add(TeeBox(
                course_id=course.id,
                color=tb["color"],
                rating=tb.get("rating"),
                slope=tb.get("slope"),
                handicap=tb.get("handicap"),
                yardages=yardages_map.get(tb["color"], []),
            ))

    def add_course(self, course_data):
        self._prepare_course_data(course_data)
        # Course name is the identifier used by rounds, PUT and DELETE, so a
        # second row with the same name (double-tap on Save) must be rejected.
        if Course.query.filter_by(user_id=self.user_id, name=course_data["name"]).first():
            raise ValueError(f"Course already exists: {course_data['name']}")
        course = Course(
            user_id=self.user_id,
            club=course_data["club"],
            name=course_data["name"],
            pars=course_data["pars"],
            hole_hcp=course_data["hole_hcp"],
        )
        db.session.add(course)
        db.session.flush()
        self._add_tee_boxes(course, course_data)
        db.session.commit()
        self.invalidate_stats_cache()

    def update_course(self, original_name, course_data):
        self._prepare_course_data(course_data)
        c = Course.query.filter_by(user_id=self.user_id, name=original_name).first()
        if not c:
            raise ValueError(f"Course not found: {original_name}")
        new_name = course_data["name"]
        if new_name != original_name:
            if Course.query.filter_by(user_id=self.user_id, name=new_name).first():
                raise ValueError(f"Course already exists: {new_name}")
            # Rounds reference courses by name string — cascade the rename
            Round.query.filter_by(
                user_id=self.user_id, course_name=original_name
            ).update({"course_name": new_name})
        old_club = c.club or ""
        c.club = course_data["club"]
        c.name = new_name
        c.pars = course_data["pars"]
        c.hole_hcp = course_data["hole_hcp"]

        # Replace tee boxes
        for tb in list(c.tee_boxes):
            db.session.delete(tb)
        db.session.flush()
        self._add_tee_boxes(c, course_data)
        db.session.commit()

        # Home club follows a rename once no course is left under the old name
        home = self.user_prefs.get("home_club") or ""
        if home and old_club == home and c.club and c.club != home:
            if not Course.query.filter_by(user_id=self.user_id, club=home).first():
                self.user_prefs["home_club"] = c.club
                self.save_user_prefs()
        self.invalidate_stats_cache()

    def delete_course(self, name):
        # Delete every row with this name so legacy duplicates go together
        # and the DB matches what the client removes from its list.
        rows = Course.query.filter_by(user_id=self.user_id, name=name).all()
        for c in rows:
            db.session.delete(c)
        if rows:
            db.session.commit()
        self.invalidate_stats_cache()

    # --- rounds ---

    def get_rounds(self):
        return [
            _round_to_dict(r)
            for r in Round.query.filter_by(user_id=self.user_id).order_by(Round.id).all()
        ]

    def add_round(self, round_data):
        course = self.get_course_by_name(round_data.get("course_name"))
        if not course:
            raise ValueError(f"Course not found: {round_data.get('course_name')}")
        tee_color = normalize_tee_color(round_data.get("tee_color") or "")
        box = next((b for b in course["tee_boxes"] if b["color"] == tee_color), None)
        if not box:
            raise ValueError(f"Tee box not found: {round_data.get('tee_color')}")
        # A NULL rating/slope or non-int score saves fine but 500s every
        # handicap/stats read afterwards, so reject it here.
        if box["rating"] is None or not box["slope"]:
            raise ValueError(f"Tee box {tee_color} needs a rating and slope")
        total = round_data.get("total_score")
        if isinstance(total, bool) or not isinstance(total, int) or not 9 <= total <= 400:
            raise ValueError("Invalid total_score")
        holes_choice = round_data.get("holes_choice", "full_18")
        if holes_choice not in ("full_18", "front_9", "back_9"):
            raise ValueError(f"Invalid holes_choice: {holes_choice}")
        holes_played = round_data.get("holes_played", 18)
        if isinstance(holes_played, bool) or not isinstance(holes_played, int) or not 1 <= holes_played <= 18:
            raise ValueError("Invalid holes_played")
        scores = round_data.get("scores") or []
        if not isinstance(scores, list):
            raise ValueError("scores must be a list")
        pars = course["pars"]
        if holes_choice == "front_9":
            par = sum(pars[:9])
        elif holes_choice == "back_9":
            par = sum(pars[9:])
        else:
            par = sum(pars)
        if not isinstance(round_data.get("date"), str) or not round_data["date"].strip():
            round_data["date"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        # Course handicap (rating - 18-hole par) is an 18-hole quantity;
        # halve it for 9-hole targets
        hcp = box["handicap"] or 0
        if holes_choice in ("front_9", "back_9"):
            hcp = hcp / 2
        # Course handicap from the index as it stands before this round; drives
        # stroke dots / net score on the scorecard. None until established.
        index = self.calculate_handicap_index()
        ch = None
        if index is not None:
            ch = course_handicap(index, box["slope"], box["rating"], par,
                                 nine=holes_choice in ("front_9", "back_9"),
                                 full_par=sum(pars))
        row = Round(
            user_id=self.user_id,
            course_name=course["name"],
            tee_color=tee_color,
            date=round_data["date"],
            total_score=total,
            par=par,
            tee_rating=box["rating"],
            tee_slope=box["slope"],
            target_score=par + round(hcp),
            holes_played=holes_played,
            holes_choice=holes_choice,
            round_type=round_data.get("round_type", "solo"),
            is_serious=bool(round_data.get("is_serious", False)),
            is_sim=bool(round_data.get("is_sim", False)),
            notes=round_data.get("notes", "") or "",
            scores=scores,
            detailed_stats=round_data.get("detailed_stats", []),
            pars=list(pars),
            hole_hcp=course.get("hole_hcp"),
            course_handicap=ch,
        )
        db.session.add(row)
        db.session.commit()
        self.invalidate_stats_cache()

    def delete_round(self, round_id):
        row = Round.query.filter_by(user_id=self.user_id, id=round_id).first()
        if row:
            db.session.delete(row)
            db.session.commit()
            self.invalidate_stats_cache()

    def get_filtered_rounds(self, round_type="all", _rounds=None):
        rounds = list(_rounds) if _rounds is not None else self.get_rounds()

        if round_type == "solo":
            rounds = [r for r in rounds
                      if r.get("round_type", "solo") == "solo" and not r.get("is_sim")]
        elif round_type == "scramble":
            rounds = [r for r in rounds if r.get("round_type") == "scramble"]
        elif round_type == "sim":
            rounds = [r for r in rounds if r.get("is_sim")]

        rounds.sort(key=lambda r: r.get("date") or "", reverse=True)
        return rounds

    # --- handicap ---

    def calculate_score_differential(self, round_data):
        """Differential from the raw total (no adjustment)."""
        return _differential(round_data.get("total_score"),
                             round_data.get("tee_rating"), round_data.get("tee_slope"))

    def _counts_toward_handicap(self, r):
        return (r.get("round_type", "solo") == "solo"
                and r.get("is_serious")
                and (self.user_prefs.get("sim_in_handicap", False) or not r.get("is_sim")))

    def _pair_nine_holes(self, rounds_9):
        """Pair front_9 + back_9 from same course+tee into virtual 18-hole dicts."""
        buckets = defaultdict(lambda: {"front": [], "back": []})
        for r in rounds_9:
            choice = r.get("holes_choice", "")
            if choice == "front_9":
                buckets[(r.get("course_name"), r.get("tee_color"))]["front"].append(r)
            elif choice == "back_9":
                buckets[(r.get("course_name"), r.get("tee_color"))]["back"].append(r)

        paired = []
        for (course, tee), halves in buckets.items():
            fronts = sorted(halves["front"], key=lambda r: r.get("date") or "")
            backs  = sorted(halves["back"],  key=lambda r: r.get("date") or "")
            for front, back in zip(fronts, backs):
                # If individual rating < 50 it's already a 9-hole rating (sum both halves).
                # If >= 50 it's the full 18-hole rating stored per half (use one copy).
                r = front["tee_rating"]
                combined_rating = (r + back["tee_rating"]) if r < 50 else r
                paired.append({
                    "course_name": course,
                    "tee_color": tee,
                    "total_score": front["total_score"] + back["total_score"],
                    "tee_rating": combined_rating,
                    "tee_slope": front["tee_slope"],
                    "holes_played": 18,
                    "date": max(front.get("date") or "", back.get("date") or ""),
                    "_paired": True,
                    "_front": front,
                    "_back": back,
                })
        return paired

    def _eligible_rounds(self, all_rounds):
        """Solo, serious rounds with a usable rating/slope (sim only if opted in)."""
        return [
            r for r in all_rounds
            if self._counts_toward_handicap(r)
            and r.get("holes_played", 18) in (9, 18)
            and r.get("tee_rating") is not None and r.get("tee_slope")
            and isinstance(r.get("total_score"), int)
        ]

    def _handicap_eligible_18s(self, all_rounds):
        """Eligible rounds as 18-hole entries, oldest first.
        9-hole halves are paired into virtual 18s BEFORE any windowing so a
        front-9 never loses its back-9 partner to the 20-round cut."""
        eligible = self._eligible_rounds(all_rounds)
        rounds_18 = [r for r in eligible if r.get("holes_played", 18) == 18]
        rounds_9  = [r for r in eligible if r.get("holes_played", 18) == 9]
        all_18 = rounds_18 + self._pair_nine_holes(rounds_9)
        all_18.sort(key=lambda r: r.get("date") or "")
        return all_18

    def _course_map(self):
        return {c["name"]: c for c in self.get_courses()}

    def _differential_series(self, all_rounds):
        """Walk eligible 18s oldest first. Each round's adjusted gross score
        uses the index as it stood before that round (par + 5 cap until one
        exists). Returns [{entry, ags, diff}] in date order."""
        courses = self._course_map()
        series, diffs = [], []
        for r in self._handicap_eligible_18s(all_rounds):
            recent = diffs[-20:]
            index = self._apply_handicap_table(sorted(recent)) if len(recent) >= 3 else None
            if r.get("_paired"):
                ags = sum(adjusted_gross(h, index, courses.get(h.get("course_name")))
                          for h in (r["_front"], r["_back"]))
            else:
                ags = adjusted_gross(r, index, courses.get(r.get("course_name")))
            diff = _differential(ags, r["tee_rating"], r["tee_slope"])
            if diff is None:
                continue
            diffs.append(diff)
            series.append({"entry": r, "ags": ags, "diff": diff})
        return series

    def calculate_handicap_index(self, _rounds=None):
        all_rounds = _rounds if _rounds is not None else self.get_rounds()
        # WHS: last 20 differentials (a paired 9+9 counts as one)
        diffs = [x["diff"] for x in self._differential_series(all_rounds)[-20:]]
        if len(diffs) < 3:
            return None
        return self._apply_handicap_table(sorted(diffs))

    def handicap_progress(self, _rounds=None):
        """What's missing before an index exists, for the home/stats hero."""
        all_rounds = _rounds if _rounds is not None else self.get_rounds()
        series = self._differential_series(all_rounds)
        n = len(series)
        nines = [r for r in self._eligible_rounds(all_rounds) if r.get("holes_played") == 9]
        paired = sum(1 for x in series if x["entry"].get("_paired"))
        sims_excluded = (not self.user_prefs.get("sim_in_handicap", False)
                         and any(r.get("is_sim") and r.get("is_serious")
                                 and r.get("round_type", "solo") == "solo" for r in all_rounds))
        provisional = None
        if 1 <= n <= 2:
            provisional = round(min(x["diff"] for x in series) - 2.0, 1)
        return {
            "eligible": n,
            "needed": max(0, 3 - n),
            "unpaired_9": len(nines) - 2 * paired,
            "provisional": provisional,
            "sims_excluded": sims_excluded,
        }

    def _apply_handicap_table(self, sorted_diffs):
        n = len(sorted_diffs)
        if n == 3:
            idx = sorted_diffs[0] - 2.0
        elif n == 4:
            idx = sorted_diffs[0] - 1.0
        elif n == 5:
            idx = sorted_diffs[0]
        elif n == 6:
            idx = mean(sorted_diffs[:2]) - 1.0
        elif n <= 8:
            idx = mean(sorted_diffs[:2])
        elif n <= 11:
            idx = mean(sorted_diffs[:3])
        elif n <= 14:
            idx = mean(sorted_diffs[:4])
        elif n <= 16:
            idx = mean(sorted_diffs[:5])
        elif n <= 18:
            idx = mean(sorted_diffs[:6])
        elif n == 19:
            idx = mean(sorted_diffs[:7])
        else:
            idx = mean(sorted_diffs[:8])
        # WHS (2020+): no 0.96 "bonus for excellence" multiplier
        return round(idx, 1)

    # --- aggregates ---

    def _round_summary_counts(self, _rounds=None):
        counts = {
            "total": 0, "serious": 0, "solo": 0, "scramble": 0, "sim": 0,
            "holes_18": 0, "holes_9": 0, "all_holes": 0,
            "hc_18": 0, "hc_9": 0, "hc_holes": 0,
        }
        for r in (_rounds if _rounds is not None else self.get_rounds()):
            counts["total"] += 1
            holes = r.get("holes_played", 18)
            counts["all_holes"] += holes
            is_solo = r.get("round_type", "solo") == "solo"
            is_serious = r.get("is_serious", False)
            is_scramble = r.get("round_type") == "scramble"
            if r.get("is_sim"):
                counts["sim"] += 1
            if is_serious:
                counts["serious"] += 1
            if is_solo:
                counts["solo"] += 1
            if is_scramble:
                counts["scramble"] += 1
            if holes == 18:
                counts["holes_18"] += 1
            elif holes == 9:
                counts["holes_9"] += 1
            if self._counts_toward_handicap(r):
                counts["hc_holes"] += holes
                if holes == 18:
                    counts["hc_18"] += 1
                elif holes == 9:
                    counts["hc_9"] += 1
        return counts

    def get_best_round(self, is_sim=False, _rounds=None):
        all_rounds = _rounds if _rounds is not None else self.get_rounds()
        if is_sim:
            candidates = [r for r in all_rounds if r.get("is_sim")]
        else:
            candidates = [r for r in all_rounds
                          if r.get("is_serious")
                          and r.get("round_type", "solo") == "solo"
                          and not r.get("is_sim")]
        if not candidates:
            return None

        # A full 18 always outranks a 9-hole round; 9-hole rounds are only
        # considered when no 18-hole round qualifies.
        full = [r for r in candidates if r.get("holes_played", 18) == 18]
        if full:
            candidates = full

        def score_vs_par(r):
            return r["total_score"] - r.get("par", 36 if r.get("holes_played") == 9 else 72)

        return min(candidates, key=score_vs_par)

    def get_score_differentials(self, _rounds=None):
        diffs = []
        for x in self._differential_series(
                _rounds if _rounds is not None else self.get_rounds()):
            r = x["entry"]
            if r.get("_paired"):
                f, b = r["_front"], r["_back"]
                label = f"{r['course_name']} (F9 {f['total_score']} + B9 {b['total_score']})"
            else:
                label = r["course_name"]
            diffs.append({
                "diff": x["diff"],
                "course": label,
                "score": r["total_score"],
                "ags": x["ags"],
                "holes": 18,
                "date": r.get("date") or "N/A",
            })
        return sorted(diffs, key=lambda x: x["diff"])

    # --- clubs ---

    def add_club(self, club_data):
        existing = Club.query.filter(
            Club.user_id == self.user_id,
            db.func.lower(Club.name) == club_data["name"].lower()
        ).first()
        if existing:
            return False
        club = Club(
            user_id=self.user_id,
            name=club_data["name"],
            distance=club_data.get("distance"),
            notes=club_data.get("notes", ""),
            partials=club_data.get("partials"),
        )
        db.session.add(club)
        db.session.commit()
        return True

    def update_club(self, original_name, club_data):
        club = Club.query.filter_by(user_id=self.user_id, name=original_name).first()
        if not club:
            return False
        club.name = club_data["name"]
        club.distance = club_data.get("distance")
        club.notes = club_data.get("notes", "")
        club.partials = club_data.get("partials")
        if "in_bag" in club_data:
            club.in_bag = bool(club_data["in_bag"])
        db.session.commit()
        return True

    def update_club_partial(self, name, swing, new_dist):
        club = Club.query.filter_by(user_id=self.user_id, name=name).first()
        if not club:
            return False
        partials = dict(club.partials or {})
        partials[swing] = new_dist
        club.partials = partials
        db.session.commit()
        return True

    def delete_club(self, name):
        club = Club.query.filter_by(user_id=self.user_id, name=name).first()
        if club:
            db.session.delete(club)
            db.session.commit()

    def get_clubs_sorted_by_distance(self):
        clubs = Club.query.filter_by(user_id=self.user_id).all()
        return sorted([_club_to_dict(c) for c in clubs], key=lambda c: c.get("distance") or 0, reverse=True)

    # --- statistics ---

    def get_statistics(self, _rounds=None):
        rounds = _rounds if _rounds is not None else self.get_rounds()
        c = self._round_summary_counts(_rounds=rounds)
        # Avg scores: include sim rounds, derive 9h datapoints from 18h rounds
        all_18_scores, all_9_scores = [], []
        for r in rounds:
            is_solo = r.get("round_type", "solo") == "solo"
            is_serious = r.get("is_serious", False)
            is_sim = r.get("is_sim", False)
            score = r.get("total_score")
            if score is None or not is_solo:
                continue
            if is_serious or is_sim:
                holes = r.get("holes_played", 18)
                if holes == 18:
                    all_18_scores.append(score)
                    all_9_scores.append(score / 2)
                elif holes == 9:
                    all_9_scores.append(score)
        return {
            "total_rounds": c["total"],
            "total_irl": c["total"] - c["sim"],
            "total_sim": c["sim"],
            "serious_rounds": c["serious"],
            "solo_rounds": c["solo"],
            "scramble_rounds": c["scramble"],
            "rounds_18": c["holes_18"],
            "rounds_9": c["holes_9"],
            "avg_score_18": round(mean(all_18_scores), 1) if all_18_scores else None,
            "avg_score_9": round(mean(all_9_scores), 1) if all_9_scores else None,
            "handicap_eligible_18": c["hc_18"],
            "handicap_eligible_9": c["hc_9"],
            "total_holes_played": c["hc_holes"],
            "all_holes_played": c["all_holes"],
        }

    def get_advanced_statistics(self):
        cache_row = db.session.get(StatsCache, self.user_id)
        if (cache_row
                and cache_row.valid
                and cache_row.version == _STATS_CACHE_VERSION
                and cache_row.data):
            return cache_row.data

        stats = {
            "gir": {"par3": [], "par4": [], "par5": [], "overall": []},
            "putts": {"par3": [], "par4": [], "par5": [], "overall": []},
            "strokes_to_green": {"par3": [], "par4": [], "par5": []},
            "three_putt_count": 0,
            "two_putt_count": 0,
            "one_putt_count": 0,
            "total_holes_with_putts": 0,
            "holes_with_stg": 0,
            "club_usage": {},
            "scramble_opportunities": 0,
            "scramble_successes": 0,
            "penalties": {"water": 0, "ob": 0, "unplayable": 0, "total": 0},
            "detailed_rounds": 0,
        }

        course_by_name = {c["name"]: c for c in self.get_courses()}

        for rd in self.get_rounds():
            if not rd.get("detailed_stats"):
                continue
            course = course_by_name.get(rd["course_name"])
            if not course:
                continue
            is_sim = rd.get("is_sim", False)
            pars = course["pars"]
            detailed = rd["detailed_stats"]
            stats["detailed_rounds"] += 1

            for hole_idx, hole_data in enumerate(detailed):
                if hole_idx >= len(pars):
                    continue
                par = pars[hole_idx]
                par_key = f"par{par}" if par in {3, 4, 5} else None
                strokes_to_green = hole_data.get("strokes_to_green")
                putts = hole_data.get("putts")
                clubs_used = hole_data.get("clubs_used", [])
                score = hole_data.get("score")

                if strokes_to_green is not None:
                    # GIR / strokes-to-green include sim rounds: the approach
                    # shots are real player input (only putts are auto-rolled).
                    stats["holes_with_stg"] += 1
                    gir_target = par - 2
                    is_gir = strokes_to_green <= gir_target
                    stats["gir"]["overall"].append(1 if is_gir else 0)
                    if par_key:
                        stats["gir"][par_key].append(1 if is_gir else 0)
                        stats["strokes_to_green"][par_key].append(strokes_to_green)
                    # Scramble depends on the total score (putts included), so sim
                    # rounds would taint it with random auto-putts — exclude them.
                    if not is_gir and score is not None and not is_sim:
                        stats["scramble_opportunities"] += 1
                        if score <= par:
                            stats["scramble_successes"] += 1

                if putts is not None and not is_sim:
                    stats["putts"]["overall"].append(putts)
                    stats["total_holes_with_putts"] += 1
                    if par_key:
                        stats["putts"][par_key].append(putts)
                    if putts >= 3:
                        stats["three_putt_count"] += 1
                    elif putts == 2:
                        stats["two_putt_count"] += 1
                    elif putts == 1:
                        stats["one_putt_count"] += 1


                for club in clubs_used:
                    if club != "X":
                        stats["club_usage"][club] = stats["club_usage"].get(club, 0) + 1

                pen = hole_data.get("penalties")
                if pen:
                    stats["penalties"]["water"] += pen.get("water", 0)
                    stats["penalties"]["ob"] += pen.get("ob", 0)
                    stats["penalties"]["unplayable"] += pen.get("unplayable", 0)
                    stats["penalties"]["total"] += pen.get("total", 0)

        thp = stats["total_holes_with_putts"]
        sco = stats["scramble_opportunities"]
        dr = stats["detailed_rounds"]
        hws = stats["holes_with_stg"]
        result = {
            "gir_overall": self._calc_percentage(stats["gir"]["overall"]),
            "gir_par3": self._calc_percentage(stats["gir"]["par3"]),
            "gir_par4": self._calc_percentage(stats["gir"]["par4"]),
            "gir_par5": self._calc_percentage(stats["gir"]["par5"]),
            "avg_putts_overall": self._calc_average(stats["putts"]["overall"]),
            "avg_putts_par3": self._calc_average(stats["putts"]["par3"]),
            "avg_putts_par4": self._calc_average(stats["putts"]["par4"]),
            "avg_putts_par5": self._calc_average(stats["putts"]["par5"]),
            "avg_strokes_to_green_par3": self._calc_average(stats["strokes_to_green"]["par3"]),
            "avg_strokes_to_green_par4": self._calc_average(stats["strokes_to_green"]["par4"]),
            "avg_strokes_to_green_par5": self._calc_average(stats["strokes_to_green"]["par5"]),
            "three_putt_rate": round(stats["three_putt_count"] / thp * 100, 1) if thp > 0 else None,
            "two_putt_rate": round(stats["two_putt_count"] / thp * 100, 1) if thp > 0 else None,
            "one_putt_rate": round(stats["one_putt_count"] / thp * 100, 1) if thp > 0 else None,

            "scramble_rate": round(stats["scramble_successes"] / sco * 100, 1) if sco > 0 else None,
            "club_usage": stats["club_usage"],
            # "tracked" = any hole with detailed approach data (GIR/STG), incl sim.
            # Putting-rate denominators still use total_holes_with_putts (real only).
            "total_holes_tracked": hws,
            "total_holes_with_putts": thp,
            "scramble_opportunities": sco,
            "scramble_successes": stats["scramble_successes"],
            "penalties_total": stats["penalties"]["total"],
            "penalties_water": stats["penalties"]["water"],
            "penalties_ob": stats["penalties"]["ob"],
            "penalties_unplayable": stats["penalties"]["unplayable"],
            "penalties_per_round": round(stats["penalties"]["total"] / dr, 2) if dr > 0 else None,
        }

        if not cache_row:
            cache_row = StatsCache(user_id=self.user_id)
            db.session.add(cache_row)
        cache_row.valid = True
        cache_row.version = _STATS_CACHE_VERSION
        cache_row.data = result
        db.session.commit()

        return result

    def _calc_percentage(self, values):
        if not values:
            return None
        return round(sum(values) / len(values) * 100, 1)

    def _calc_average(self, values):
        if not values:
            return None
        return round(mean(values), 2)

    def get_club_analytics(self):
        adv_stats = self.get_advanced_statistics()
        club_usage = adv_stats.get("club_usage", {})
        if not club_usage:
            return {
                "ranked_clubs": [],
                "rarely_used": [],
                "never_used": [],
                "category_breakdown": {},
                "total_shots": 0,
            }
        total_shots = sum(club_usage.values())
        ranked = sorted(club_usage.items(), key=lambda x: x[1], reverse=True)
        ranked_clubs = [
            {"name": name, "count": count, "percentage": round(count / total_shots * 100, 1)}
            for name, count in ranked
        ]
        rarely_used = [c for c in ranked_clubs if c["percentage"] < 3]
        bag_clubs = [c["name"] for c in self.get_clubs_sorted_by_distance()]
        used_clubs = set(club_usage.keys())
        never_used = [c for c in bag_clubs if c not in used_clubs]
        category_breakdown = {}
        for club_name, count in club_usage.items():
            cat = CLUB_CATEGORIES.get(club_name, "other")
            category_breakdown[cat] = category_breakdown.get(cat, 0) + count
        return {
            "ranked_clubs": ranked_clubs,
            "rarely_used": rarely_used,
            "never_used": never_used,
            "category_breakdown": category_breakdown,
            "total_shots": total_shots,
        }

    def get_stroke_leak_analysis(self):
        adv_stats = self.get_advanced_statistics()
        insights = []
        avg_stg_par4 = adv_stats.get("avg_strokes_to_green_par4")
        if avg_stg_par4 is not None:
            excess = avg_stg_par4 - 2
            if excess > 1:
                insights.append({
                    "area": "approach",
                    "severity": "high" if excess > 2 else "medium",
                    "message": f"On Par 4s, you're averaging {avg_stg_par4:.1f} strokes to reach the green (target: 2)",
                    "stat": avg_stg_par4,
                })
        avg_stg_par3 = adv_stats.get("avg_strokes_to_green_par3")
        if avg_stg_par3 is not None:
            excess = avg_stg_par3 - 1
            if excess > 0.5:
                insights.append({
                    "area": "tee_shots_par3",
                    "severity": "high" if excess > 1 else "medium",
                    "message": f"On Par 3s, you're averaging {avg_stg_par3:.1f} strokes to reach the green (target: 1)",
                    "stat": avg_stg_par3,
                })
        three_putt_rate = adv_stats.get("three_putt_rate")
        if three_putt_rate is not None and three_putt_rate > 10:
            insights.append({
                "area": "putting",
                "severity": "high" if three_putt_rate > 20 else "medium",
                "message": f"3-putt rate is {three_putt_rate:.1f}% ({adv_stats.get('total_holes_with_putts', 0)} holes tracked)",
                "stat": three_putt_rate,
            })
        avg_putts = adv_stats.get("avg_putts_overall")
        if avg_putts is not None and avg_putts > 2.1:
            insights.append({
                "area": "putting_avg",
                "severity": "medium",
                "message": f"Averaging {avg_putts:.2f} putts per hole (tour avg: ~1.8)",
                "stat": avg_putts,
            })
        gir_overall = adv_stats.get("gir_overall")
        if gir_overall is not None and gir_overall < 30:
            insights.append({
                "area": "gir",
                "severity": "high" if gir_overall < 20 else "medium",
                "message": f"GIR is {gir_overall:.1f}% (amateur target: 30-40%)",
                "stat": gir_overall,
            })
        severity_order = {"high": 0, "medium": 1, "low": 2}
        insights.sort(key=lambda x: severity_order.get(x["severity"], 2))
        return insights

    # --- aggregate bundles (one request per screen, rounds loaded once) ---

    def get_home_bundle(self):
        rounds = self.get_rounds()
        best = self.get_best_round(is_sim=False, _rounds=rounds)
        best_sim = self.get_best_round(is_sim=True, _rounds=rounds)
        return {
            "stats": self.get_statistics(_rounds=rounds),
            "handicap_index": self.calculate_handicap_index(_rounds=rounds),
            "handicap_progress": self.handicap_progress(_rounds=rounds),
            "best": best if best else {},
            "best_sim": best_sim if best_sim else {},
            "best_scorecard": generate_scorecard_data(self, best) if best else None,
            "best_sim_scorecard": generate_scorecard_data(self, best_sim) if best_sim else None,
            "advanced": self.get_advanced_statistics(),
            "rounds": self.get_filtered_rounds("all", _rounds=rounds),
            "training": self.get_training_sessions(),
            "leaks": self.get_stroke_leak_analysis(),
        }

    def get_stats_bundle(self):
        rounds = self.get_rounds()
        best = self.get_best_round(is_sim=False, _rounds=rounds)
        return {
            "stats": self.get_statistics(_rounds=rounds),
            "handicap_index": self.calculate_handicap_index(_rounds=rounds),
            "handicap_progress": self.handicap_progress(_rounds=rounds),
            "advanced": self.get_advanced_statistics(),
            "leaks": self.get_stroke_leak_analysis(),
            "differentials": self.get_score_differentials(_rounds=rounds),
            "best": best if best else {},
            "club_analytics": self.get_club_analytics(),
        }

    # --- training sessions ---

    # Iron names in descending order used for adaptive drill ordering
    _IRON_ORDER = ["9 Iron", "8 Iron", "7 Iron", "6 Iron", "5 Iron", "4 Iron", "3 Iron", "2 Iron"]
    _HYBRID_ORDER = ["5 Hybrid", "4 Hybrid", "3 Hybrid", "2 Hybrid"]

    def get_adaptive_drill_template(self):
        clubs = Club.query.filter_by(user_id=self.user_id).all()
        club_names = {c.name for c in clubs}
        club_lower = {c.name.lower() for c in clubs}

        def has(name):
            return name.lower() in club_lower

        categories = []

        # RANGE WARM-UP — always first
        categories.append({"category": "RANGE WARM-UP", "clubs": [], "instructions": (
            "One-Handed Swing Drill — Use a PW or 9-iron. Take your normal address. "
            "For the left-arm drill, remove your right hand and make full-speed swings, feeling the left arm guide the club through impact and naturally release. "
            "For the right-arm drill, remove your left hand and feel the right hand supply power and control the wrist hinge through the hitting zone. "
            "The single-arm constraint eliminates compensations and grooves a natural swing path. "
            "Combine both feelings in the two-handed swings. "
            "Recommended by Harvey Penick and widely used in modern practice curricula."
        ), "drills": [
            {"name": "10 swings — left arm only", "resultType": "check",
             "desc": "Full-speed swings with left arm only. Feel the swing path and natural release through the ball."},
            {"name": "10 swings — right arm only", "resultType": "check",
             "desc": "Full-speed swings with right arm only. Feel the power source and wrist hinge."},
            {"name": "10 swings — both arms", "resultType": "check",
             "desc": "Full swings combining the feelings from each arm. Build rhythm before hitting your first shot."},
        ]})

        # PUTTING — always included
        categories.append({"category": "PUTTING", "clubs": [], "drills": [
            {"name": "20 in a row from 3'", "resultType": "streak", "resultLabel": "Best streak",
             "desc": "Set up 3 feet from the hole. Make 20 consecutive putts — keep going past 20. Start over on any miss."},
            {"name": "8/10 from 6'", "resultType": "count", "target": 10, "resultLabel": "Made",
             "desc": "Place 10 balls around the hole at 6 feet. Make at least 8 to pass."},
            {"name": "10 in a row from 20 ft", "resultType": "streak", "resultLabel": "Best streak",
             "desc": "From 20 feet, make 10 consecutive putts within a 3-foot circle. Start over on any miss."},
            {"name": "10 in a row from 30 ft", "resultType": "streak", "resultLabel": "Best streak",
             "desc": "From 30 feet, make 10 consecutive putts within a 3-foot circle. Lag putting focus. Start over on any miss."},
            {"name": "8/10 from 50 ft", "resultType": "count", "target": 10, "resultLabel": "Made",
             "desc": "From 50 feet, get 8 of 10 putts to stop within a 3-foot circle of the hole."},
            {"name": "3 Strikes and You're Out", "resultType": "count", "resultLabel": "Total makes",
             "desc": "Putt from different spots around the hole. Three misses ends the game. Track total makes before striking out."},
            {"name": "20 Tee Game", "resultType": "count", "target": 20, "resultLabel": "Made",
             "desc": "Place 20 tees at various distances and positions around the hole. Make as many as possible."},
        ]})

        # CHIPPING — only if user has GW or LW
        chipping_clubs = [c for c in ["GW", "SW", "LW"] if has(c)]
        if chipping_clubs:
            categories.append({"category": "CHIPPING", "clubs": chipping_clubs, "instructions": (
                "Chip to a target circle around the hole. Each drill is 10 balls — "
                "count how many land the 1st bounce inside the circle. "
                "Use your standard chip setup: ball back, weight forward, quiet hands."
            ), "drills": [
                {"name": "10 yd — 1st bounce in circle", "resultType": "count", "target": 10, "resultLabel": "Made"},
                {"name": "15 yd — 1st bounce in circle", "resultType": "count", "target": 10, "resultLabel": "Made"},
                {"name": "25 yd — 1st bounce in circle", "resultType": "count", "target": 10, "resultLabel": "Made"},
            ]})

        # WEDGE MATRIX — calibrate partial distances for all wedges
        wedge_clubs = [c for c in clubs if c.name in {"LW", "SW", "GW", "PW"} or "wedge" in c.name.lower()]
        if wedge_clubs:
            wedge_club_dicts = [{"name": c.name, "partials": c.partials or {}, "full": c.distance} for c in wedge_clubs]
            categories.append({
                "category": "WEDGE MATRIX",
                "clubs": [c.name for c in wedge_clubs],
                "wedge_clubs": wedge_club_dicts,
                "drills": [],
                "resultType": "wedge_matrix",
                "instructions": (
                    "Hit 10 balls per swing length per club. Count how many carry within ±5 yards "
                    "of your stored distance for that swing (shown below each button). "
                    "If you consistently score higher than stored, save the new distance — it becomes your updated baseline."
                ),
            })

        # IRONS + HYBRIDS — 9i first (short to long), distance-control benchmark
        club_dist_map = {c.name: c.distance for c in clubs}
        iron_drills = []
        for iron in self._IRON_ORDER:
            if iron in club_names:
                iron_drills.append({
                    "name": iron,
                    "clubName": iron,
                    "distance": club_dist_map.get(iron),
                    "resultType": "count",
                    "target": 10,
                    "resultLabel": "In range",
                })
        for hybrid in self._HYBRID_ORDER:
            if hybrid in club_names:
                iron_drills.append({
                    "name": hybrid,
                    "clubName": hybrid,
                    "distance": club_dist_map.get(hybrid),
                    "resultType": "count",
                    "target": 10,
                    "resultLabel": "In range",
                })
        if iron_drills:
            categories.append({
                "category": "IRONS",
                "clubs": [d["name"] for d in iron_drills],
                "drills": iron_drills,
                "instructions": (
                    "Iron Distance Control — For each iron, hit 10 balls at your stored carry distance. "
                    "Count how many land within 10 yards of target (±10 yd circle, ~6% of a 150 yd shot — "
                    "the PGA Tour average dispersion benchmark for mid-irons). "
                    "This tests repeatability, not peak distance. "
                    "If you're consistently outside 10 yards, your stored distance may need updating."
                ),
            })

        # WOODS — Driver + fairway woods, one drill each
        _WOOD_ORDER = ["7 Wood", "5 Wood", "3 Wood", "Driver"]
        wood_drills = []
        for wood in _WOOD_ORDER:
            if wood in club_names:
                wood_drills.append({
                    "name": wood,
                    "clubName": wood,
                    "distance": club_dist_map.get(wood),
                    "resultType": "count",
                    "target": 25,
                    "resultLabel": "Fairways",
                })
        if wood_drills:
            categories.append({
                "category": "WOODS",
                "clubs": [d["clubName"] for d in wood_drills],
                "drills": wood_drills,
                "instructions": (
                    "Fairway Finder — Hit 25 balls per club. Count how many land in your target corridor (fairway or equivalent). "
                    "Focus on a consistent pre-shot routine: same alignment, same trigger, same tempo. "
                    "Do not chase distance — repeatable contact and direction is the goal."
                ),
            })

        return categories

    def get_training_sessions(self):
        q = TrainingSession.query.filter_by(user_id=self.user_id).order_by(TrainingSession.id.desc())
        return [_training_to_dict(s) for s in q.all()]

    def add_training_session(self, data):
        session = TrainingSession(
            user_id=self.user_id,
            date=data.get("date", datetime.now().strftime("%Y-%m-%d")),
            drills=data.get("drills", []),
            notes=data.get("notes", ""),
            duration_minutes=data.get("duration_minutes"),
        )
        db.session.add(session)
        for drill in data.get("drills", []):
            if drill.get("resultType") == "wedge_matrix":
                for upd in drill.get("pendingPartialUpdates", []):
                    self.update_club_partial(upd["club"], upd["swing"], upd["dist"])
        db.session.commit()
        return {"ok": True, "session": _training_to_dict(session)}

    def delete_training_session(self, session_id):
        session = TrainingSession.query.filter_by(id=session_id, user_id=self.user_id).first()
        if session:
            db.session.delete(session)
            db.session.commit()
            return True
        return False


def _training_to_dict(s):
    return {
        "id": s.id,
        "date": s.date,
        "drills": s.drills or [],
        "notes": s.notes or "",
        "duration_minutes": s.duration_minutes,
    }


# ---- Scorecard Export ----
def generate_scorecard_data(backend, round_data):
    course = backend.get_course_by_name(round_data["course_name"])
    pars = (round_data.get("pars") or (course["pars"] if course else None)
            or [4] * len(round_data.get("scores", [])))
    # Stroke index + strokes received, aligned with pars (None = unknown/unplayed)
    holes, _, hole_hcp = round_hole_layout(round_data, course)
    ch = round_data.get("course_handicap")
    strokes = [None] * len(pars)
    net_total = None
    if hole_hcp and ch is not None and holes:
        for i, g in zip(holes, strokes_per_hole(ch, [hole_hcp[i] for i in holes])):
            strokes[i] = g
    if ch is not None and round_data.get("total_score") is not None:
        net_total = round_data["total_score"] - ch
    yardages = []
    if course:
        tee_color = round_data.get("tee_color", "")
        yardages = course.get("yardages", {}).get(tee_color, [])
    scores = round_data.get("scores", [])
    # Per-hole putts from detailed_stats (sim rounds auto-roll these). Kept
    # aligned with `scores`; None where the hole has no putt data.
    detailed = round_data.get("detailed_stats") or []
    putts = [(detailed[i] or {}).get("putts") if i < len(detailed) else None
             for i in range(len(scores))]
    diff = round_data.get("total_score", 0) - round_data.get("par", 72)
    diff_str = f"+{diff}" if diff > 0 else ("E" if diff == 0 else str(diff))
    front_9_scores = [s for s in scores[:9] if s is not None]
    back_9_scores = [s for s in scores[9:18] if s is not None] if len(scores) > 9 else []
    # Filter putts with the same mask as scores so indices line up in the UI.
    front_9_putts = [p for s, p in zip(scores[:9], putts[:9]) if s is not None]
    back_9_putts = [p for s, p in zip(scores[9:18], putts[9:18]) if s is not None] if len(scores) > 9 else []
    front_9_pars = pars[:9]
    back_9_pars = pars[9:18] if len(pars) > 9 else []
    front_9_yards = yardages[:9] if len(yardages) >= 9 else yardages
    back_9_yards = yardages[9:18] if len(yardages) >= 18 else []
    return {
        "course_name": round_data.get("course_name", "Unknown Course"),
        "club_name": course.get("club", "") if course else "",
        "date": round_data.get("date", "N/A"),
        "tee_color": round_data.get("tee_color", "N/A"),
        "holes_played": round_data.get("holes_played", 18),
        "holes_choice": round_data.get("holes_choice", "full_18"),
        "total_score": round_data.get("total_score", 0),
        "par": round_data.get("par", 72),
        "diff_str": diff_str,
        "target_score": round_data.get("target_score", "N/A"),
        "round_type": round_data.get("round_type", "solo"),
        "is_serious": round_data.get("is_serious", False),
        "is_sim": round_data.get("is_sim", False),
        "notes": round_data.get("notes", ""),
        "pars": pars,
        "hole_hcp": hole_hcp,
        "strokes": strokes,
        "course_handicap": ch,
        "net_total": net_total,
        "scores": scores,
        "putts": putts,
        "yardages": yardages,
        "front_9": {
            "pars": front_9_pars,
            "hole_hcp": hole_hcp[:9] if hole_hcp else [],
            "strokes": strokes[:9],
            "scores": front_9_scores,
            "putts": front_9_putts,
            "yardages": front_9_yards,
            "par_total": sum(front_9_pars),
            "score_total": sum(front_9_scores) if front_9_scores else 0,
            "yards_total": sum(front_9_yards) if front_9_yards else 0,
        },
        "back_9": {
            "pars": back_9_pars,
            "hole_hcp": hole_hcp[9:18] if hole_hcp else [],
            "strokes": strokes[9:18],
            "scores": back_9_scores,
            "putts": back_9_putts,
            "yardages": back_9_yards,
            "par_total": sum(back_9_pars) if back_9_pars else 0,
            "score_total": sum(back_9_scores) if back_9_scores else 0,
            "yards_total": sum(back_9_yards) if back_9_yards else 0,
        },
    }
