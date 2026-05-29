from statistics import mean
from datetime import datetime

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
    }


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
        "tee_boxes": tee_boxes,
        "yardages": yardages,
    }


def _club_to_dict(c):
    d = {"name": c.name, "distance": c.distance, "notes": c.notes or ""}
    if c.partials:
        d["partials"] = c.partials
    return d


class GolfBackend:
    def __init__(self, user_id=1):
        self.user_id = user_id
        self._user_prefs_cache = None

    @property
    def user_prefs(self):
        if self._user_prefs_cache is None:
            self._user_prefs_cache = self._load_user_prefs()
        return self._user_prefs_cache

    @user_prefs.setter
    def user_prefs(self, value):
        self._user_prefs_cache = value

    # --- user prefs ---

    def _load_user_prefs(self):
        row = db.session.get(UserPrefs, self.user_id)
        if row:
            d = {"entry_mode": row.entry_mode or "quick"}
            if row.preferred_tee:
                d["preferred_tee"] = row.preferred_tee
            return d
        return {"entry_mode": "quick"}

    def save_user_prefs(self):
        row = db.session.get(UserPrefs, self.user_id)
        if row:
            row.entry_mode = self.user_prefs.get("entry_mode", "quick")
            row.preferred_tee = self.user_prefs.get("preferred_tee")
        else:
            row = UserPrefs(
                user_id=self.user_id,
                entry_mode=self.user_prefs.get("entry_mode", "quick"),
                preferred_tee=self.user_prefs.get("preferred_tee"),
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
        return [
            _course_to_dict(c)
            for c in Course.query.filter_by(user_id=self.user_id).all()
        ]

    def get_course_by_name(self, name):
        c = Course.query.filter_by(user_id=self.user_id, name=name).first()
        return _course_to_dict(c) if c else None

    def _prepare_course_data(self, course_data):
        par_total = sum(course_data["pars"])
        for box in course_data["tee_boxes"]:
            rating = box.get("rating")
            box["handicap"] = round(rating - par_total, 1) if rating is not None else None
        if "yardages" not in course_data:
            course_data["yardages"] = {}

    def add_course(self, course_data):
        self._prepare_course_data(course_data)
        course = Course(
            user_id=self.user_id,
            club=course_data.get("club", ""),
            name=course_data["name"],
            pars=course_data["pars"],
        )
        db.session.add(course)
        db.session.flush()
        yardages_map = course_data.get("yardages", {})
        for tb in course_data.get("tee_boxes", []):
            tee_box = TeeBox(
                course_id=course.id,
                color=tb["color"],
                rating=tb.get("rating"),
                slope=tb.get("slope"),
                handicap=tb.get("handicap"),
                yardages=yardages_map.get(tb["color"], []),
            )
            db.session.add(tee_box)
        db.session.commit()

    def update_course(self, original_name, course_data):
        self._prepare_course_data(course_data)
        c = Course.query.filter_by(user_id=self.user_id, name=original_name).first()
        if not c:
            return
        c.club = course_data.get("club", "")
        c.name = course_data["name"]
        c.pars = course_data["pars"]

        # Replace tee boxes
        for tb in list(c.tee_boxes):
            db.session.delete(tb)
        db.session.flush()

        yardages_map = course_data.get("yardages", {})
        for tb in course_data.get("tee_boxes", []):
            tee_box = TeeBox(
                course_id=c.id,
                color=tb["color"],
                rating=tb.get("rating"),
                slope=tb.get("slope"),
                handicap=tb.get("handicap"),
                yardages=yardages_map.get(tb["color"], []),
            )
            db.session.add(tee_box)
        db.session.commit()
        self.invalidate_stats_cache()

    def delete_course(self, name):
        c = Course.query.filter_by(user_id=self.user_id, name=name).first()
        if c:
            db.session.delete(c)
            db.session.commit()
        self.invalidate_stats_cache()

    # --- rounds ---

    def get_rounds(self):
        return [
            _round_to_dict(r)
            for r in Round.query.filter_by(user_id=self.user_id).order_by(Round.id).all()
        ]

    def add_round(self, round_data):
        course = self.get_course_by_name(round_data["course_name"])
        if not course:
            raise ValueError(f"Course not found: {round_data.get('course_name')}")
        box = next((b for b in course["tee_boxes"] if b["color"] == round_data["tee_color"]), None)
        if not box:
            raise ValueError(f"Tee box not found: {round_data.get('tee_color')}")
        holes_choice = round_data.get("holes_choice", "full_18")
        pars = course["pars"]
        if holes_choice == "front_9":
            par = sum(pars[:9])
        elif holes_choice == "back_9":
            par = sum(pars[9:])
        else:
            par = sum(pars)
        if "date" not in round_data:
            round_data["date"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        row = Round(
            user_id=self.user_id,
            course_name=round_data["course_name"],
            tee_color=round_data["tee_color"],
            date=round_data["date"],
            total_score=round_data["total_score"],
            par=par,
            tee_rating=box["rating"],
            tee_slope=box["slope"],
            target_score=par + round(box["handicap"] or 0),
            holes_played=round_data.get("holes_played", 18),
            holes_choice=holes_choice,
            round_type=round_data.get("round_type", "solo"),
            is_serious=round_data.get("is_serious", False),
            is_sim=round_data.get("is_sim", False),
            notes=round_data.get("notes", ""),
            scores=round_data.get("scores", []),
            detailed_stats=round_data.get("detailed_stats", []),
        )
        db.session.add(row)
        db.session.commit()
        self.invalidate_stats_cache()

    def delete_round(self, index):
        row = Round.query.filter_by(user_id=self.user_id).order_by(Round.id).offset(index).limit(1).first()
        if row:
            db.session.delete(row)
            db.session.commit()
            self.invalidate_stats_cache()

    def get_filtered_rounds(self, round_type="all", sort_by="recent"):
        rounds_with_idx = list(enumerate(self.get_rounds()))

        if round_type == "solo":
            rounds_with_idx = [(i, r) for i, r in rounds_with_idx
                               if r.get("round_type", "solo") == "solo" and not r.get("is_sim")]
        elif round_type == "scramble":
            rounds_with_idx = [(i, r) for i, r in rounds_with_idx
                               if r.get("round_type") == "scramble"]
        elif round_type == "sim":
            rounds_with_idx = [(i, r) for i, r in rounds_with_idx
                               if r.get("is_sim")]

        if sort_by == "recent":
            rounds_with_idx.sort(key=lambda x: x[1].get("date", ""), reverse=True)
        elif sort_by == "best":
            rounds_with_idx.sort(key=lambda x: self._get_score_relative_to_par(x[1]))
        elif sort_by == "worst":
            rounds_with_idx.sort(key=lambda x: self._get_score_relative_to_par(x[1]), reverse=True)

        return rounds_with_idx

    def _get_score_relative_to_par(self, round_data):
        total_score = round_data.get("total_score", 999)
        total_par = round_data.get("par", 0)
        if total_par == 0:
            holes_played = round_data.get("holes_played", 18)
            total_par = holes_played * 4
        return total_score - total_par

    # --- handicap ---

    def calculate_9hole_expected_differential(self, handicap_index):
        if handicap_index is None:
            return None
        return (0.52 * handicap_index) + 1.2

    def calculate_score_differential(self, round_data, current_handicap=None):
        try:
            holes_played = round_data.get("holes_played", 18)
            total_score = round_data["total_score"]
            tee_rating = round_data["tee_rating"]
            tee_slope = round_data["tee_slope"]

            if holes_played == 18:
                diff = (113 * (total_score - tee_rating)) / tee_slope
            else:
                nine_hole_diff = (113 * (total_score - tee_rating)) / tee_slope
                if current_handicap is not None:
                    expected_diff = self.calculate_9hole_expected_differential(current_handicap)
                    diff = nine_hole_diff + expected_diff
                else:
                    diff = nine_hole_diff * 2

            return round(diff, 1)
        except (ZeroDivisionError, KeyError):
            return None

    def calculate_handicap_index(self, _rounds=None):
        all_rounds = _rounds if _rounds is not None else self.get_rounds()
        rounds_18 = []
        rounds_9 = []
        for r in all_rounds:
            if r.get("round_type", "solo") == "solo" and r.get("is_serious") and not r.get("is_sim"):
                holes = r.get("holes_played", 18)
                if holes == 18:
                    rounds_18.append(r)
                elif holes == 9:
                    rounds_9.append(r)

        diffs_18 = [d for d in (self.calculate_score_differential(r) for r in rounds_18) if d is not None]

        preliminary_handicap = None
        if len(diffs_18) >= 3:
            preliminary_handicap = self._apply_handicap_table(sorted(diffs_18))

        if preliminary_handicap is None and len(rounds_9) >= 3:
            approx_diffs = [d for d in (self.calculate_score_differential(r) for r in rounds_9) if d is not None]
            if len(approx_diffs) >= 3:
                preliminary_handicap = self._apply_handicap_table(sorted(approx_diffs))

        all_diffs = list(diffs_18)
        for r in rounds_9:
            diff = self.calculate_score_differential(r, preliminary_handicap)
            if diff is not None:
                all_diffs.append(diff)

        if len(all_diffs) < 3:
            return None

        all_diffs.sort()
        return self._apply_handicap_table(all_diffs)

    def _apply_handicap_table(self, sorted_diffs):
        n = len(sorted_diffs)
        if n < 3:
            return None
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
        return round(idx * 0.96, 1)

    # --- aggregates ---

    def _round_summary_counts(self):
        counts = {
            "total": 0, "serious": 0, "solo": 0, "scramble": 0, "sim": 0,
            "holes_18": 0, "holes_9": 0, "all_holes": 0,
            "hc_18": 0, "hc_9": 0, "hc_holes": 0,
            "serious_18_scores": [], "serious_9_scores": [],
        }
        for r in self.get_rounds():
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
            if is_solo and is_serious and not r.get("is_sim"):
                counts["hc_holes"] += holes
                if holes == 18:
                    counts["hc_18"] += 1
                    counts["serious_18_scores"].append(r["total_score"])
                elif holes == 9:
                    counts["hc_9"] += 1
                    counts["serious_9_scores"].append(r["total_score"])
        return counts

    def get_best_round(self, is_sim=False):
        all_rounds = list(enumerate(self.get_rounds()))
        if is_sim:
            candidates = [(i, r) for i, r in all_rounds if r.get("is_sim")]
        else:
            candidates = [(i, r) for i, r in all_rounds
                          if r.get("is_serious")
                          and r.get("round_type", "solo") == "solo"
                          and not r.get("is_sim")]
        if not candidates:
            return None, None

        def score_vs_par(ir):
            r = ir[1]
            return r["total_score"] - r.get("par", 36 if r.get("holes_played") == 9 else 72)

        idx, best = min(candidates, key=score_vs_par)
        return best, idx

    def get_score_differentials(self):
        all_rounds = self.get_rounds()
        eligible = [
            (r, r.get("holes_played", 18)) for r in all_rounds
            if r.get("round_type", "solo") == "solo" and r.get("is_serious")
        ]
        has_nine_hole = any(holes == 9 for _, holes in eligible)
        current_handicap = self.calculate_handicap_index(_rounds=all_rounds) if has_nine_hole else None
        diffs = []
        for r, holes in eligible:
            if holes == 18:
                diff = self.calculate_score_differential(r)
            elif holes == 9:
                diff = self.calculate_score_differential(r, current_handicap)
            else:
                continue
            if diff is not None:
                diffs.append({
                    "diff": diff,
                    "course": r["course_name"],
                    "score": r["total_score"],
                    "holes": holes,
                    "date": r.get("date", "N/A"),
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

    def get_statistics(self):
        c = self._round_summary_counts()
        s18 = c["serious_18_scores"]
        s9 = c["serious_9_scores"]
        return {
            "total_rounds": c["total"],
            "total_irl": c["total"] - c["sim"],
            "total_sim": c["sim"],
            "serious_rounds": c["serious"],
            "solo_rounds": c["solo"],
            "scramble_rounds": c["scramble"],
            "rounds_18": c["holes_18"],
            "rounds_9": c["holes_9"],
            "avg_score_18": round(mean(s18), 1) if s18 else None,
            "avg_score_9": round(mean(s9), 1) if s9 else None,
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
                        if score <= par + 1:
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

    def get_training_sessions(self, limit=None):
        q = TrainingSession.query.filter_by(user_id=self.user_id).order_by(TrainingSession.id.desc())
        if limit:
            q = q.limit(limit)
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
    pars = course["pars"] if course else [4] * len(round_data.get("scores", []))
    yardages = []
    if course:
        tee_color = round_data.get("tee_color", "")
        yardages = course.get("yardages", {}).get(tee_color, [])
    scores = round_data.get("scores", [])
    diff = round_data.get("total_score", 0) - round_data.get("par", 72)
    diff_str = f"+{diff}" if diff > 0 else ("E" if diff == 0 else str(diff))
    front_9_scores = [s for s in scores[:9] if s is not None]
    back_9_scores = [s for s in scores[9:18] if s is not None] if len(scores) > 9 else []
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
        "scores": scores,
        "yardages": yardages,
        "front_9": {
            "pars": front_9_pars,
            "scores": front_9_scores,
            "yardages": front_9_yards,
            "par_total": sum(front_9_pars),
            "score_total": sum(front_9_scores) if front_9_scores else 0,
            "yards_total": sum(front_9_yards) if front_9_yards else 0,
        },
        "back_9": {
            "pars": back_9_pars,
            "scores": back_9_scores,
            "yardages": back_9_yards,
            "par_total": sum(back_9_pars) if back_9_pars else 0,
            "score_total": sum(back_9_scores) if back_9_scores else 0,
            "yards_total": sum(back_9_yards) if back_9_yards else 0,
        },
    }
