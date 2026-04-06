import json
import os
from statistics import mean
from datetime import datetime

# --- Data files ---
COURSES_FILE = 'Data/courses.json'
ROUNDS_FILE = 'Data/rounds.json'
CLUBS_FILE = 'Data/clubs.json'
STATS_CACHE_FILE = 'Data/stats_cache.json'
USER_PREFS_FILE = 'Data/user_prefs.json'  # User preferences (entry mode, etc.)


# Club categories for analytics
CLUB_CATEGORIES = {
    "Driver": {"category": "driver", "loft": 10.5, "order": 1},
    "3 Wood": {"category": "wood", "loft": 15, "order": 2},
    "5 Wood": {"category": "wood", "loft": 18, "order": 3},
    "7 Wood": {"category": "wood", "loft": 21, "order": 4},
    "Hybrid": {"category": "hybrid", "loft": 22, "order": 5},
    "2 Hybrid": {"category": "hybrid", "loft": 18, "order": 5},
    "3 Hybrid": {"category": "hybrid", "loft": 20, "order": 6},
    "4 Hybrid": {"category": "hybrid", "loft": 23, "order": 7},
    "5 Hybrid": {"category": "hybrid", "loft": 26, "order": 8},
    "2 Iron": {"category": "iron", "loft": 18, "order": 9},
    "3 Iron": {"category": "iron", "loft": 21, "order": 10},
    "4 Iron": {"category": "iron", "loft": 24, "order": 11},
    "5 Iron": {"category": "iron", "loft": 27, "order": 12},
    "6 Iron": {"category": "iron", "loft": 30, "order": 13},
    "7 Iron": {"category": "iron", "loft": 34, "order": 14},
    "8 Iron": {"category": "iron", "loft": 38, "order": 15},
    "9 Iron": {"category": "iron", "loft": 42, "order": 16},
    "PW": {"category": "wedge", "loft": 46, "order": 17},
    "GW": {"category": "wedge", "loft": 50, "order": 18},
    "SW": {"category": "wedge", "loft": 54, "order": 19},
    "LW": {"category": "wedge", "loft": 58, "order": 20},
    "Putter": {"category": "putter", "loft": 3, "order": 21},
}


def load_json(filename):
    if not os.path.exists(filename):
        return []
    with open(filename, 'r') as f:
        return json.load(f)


def save_json(filename, data):
    with open(filename, 'w') as f:
        json.dump(data, f, indent=2)


class GolfBackend:
    def __init__(self):
        os.makedirs('data', exist_ok=True)
        self.courses = load_json(COURSES_FILE)
        self.rounds = load_json(ROUNDS_FILE)
        self.clubs = load_json(CLUBS_FILE)
        self.user_prefs = self._load_user_prefs()
        self.stats_cache = self._load_stats_cache()
    
    def _load_user_prefs(self):
        """Load user preferences from file."""
        defaults = {"entry_mode": "quick"}
        if os.path.exists(USER_PREFS_FILE):
            try:
                data = load_json(USER_PREFS_FILE)
                if isinstance(data, dict):
                    # Merge with defaults, preserving existing + unknown keys
                    for key, value in defaults.items():
                        if key not in data:
                            data[key] = value
                    return data
            except:
                pass
        return defaults.copy()
    
    def save_user_prefs(self):
        """Save user preferences to file."""
        save_json(USER_PREFS_FILE, self.user_prefs)
    
    def _load_stats_cache(self):
        """Load computed stats cache from file."""
        if os.path.exists(STATS_CACHE_FILE):
            try:
                return load_json(STATS_CACHE_FILE)
            except:
                return {}
        return {}
    
    def save_stats_cache(self):
        """Save stats cache to file."""
        save_json(STATS_CACHE_FILE, self.stats_cache)
    
    def invalidate_stats_cache(self):
        """Mark stats cache as invalid (needs recomputation)."""
        self.stats_cache["valid"] = False
        self.save_stats_cache()
    
    # ---- Courses ----
    def get_courses(self):
        return self.courses

    def get_course_by_name(self, name):
        return next((c for c in self.courses if c["name"] == name), None)

    def add_course(self, course_data):
        par_total = sum(course_data["pars"])
        for box in course_data["tee_boxes"]:
            hc = (box["slope"] / 113) * (box["rating"] - par_total)
            box["handicap"] = round(hc, 1)
        # Ensure yardages field exists (backward compatibility)
        if "yardages" not in course_data:
            course_data["yardages"] = {}
        self.courses.append(course_data)
        save_json(COURSES_FILE, self.courses)

    def update_course(self, original_name, course_data):
        par_total = sum(course_data["pars"])
        for box in course_data["tee_boxes"]:
            hc = (box["slope"] / 113) * (box["rating"] - par_total)
            box["handicap"] = round(hc, 1)
        # Ensure yardages field exists (backward compatibility)
        if "yardages" not in course_data:
            course_data["yardages"] = {}
        for i, c in enumerate(self.courses):
            if c["name"] == original_name:
                self.courses[i] = course_data
                break
        save_json(COURSES_FILE, self.courses)

    def delete_course(self, name):
        """Remove a course by name."""
        self.courses = [c for c in self.courses if c["name"] != name]
        save_json(COURSES_FILE, self.courses)

    # ---- Rounds ----
    def get_rounds(self):
        return self.rounds

    def add_round(self, round_data):
        course = self.get_course_by_name(round_data["course_name"])
        if not course:
            return
        box = next(b for b in course["tee_boxes"] if b["color"] == round_data["tee_color"])
        par = sum(course["pars"])
        round_data["target_score"] = par + round(box["handicap"])
        round_data["tee_rating"] = box["rating"]
        round_data["tee_slope"] = box["slope"]
        round_data["par"] = par
        # Add timestamp if not present
        if "date" not in round_data:
            round_data["date"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        self.rounds.append(round_data)
        save_json(ROUNDS_FILE, self.rounds)
        self.invalidate_stats_cache()  # Stats need recomputation

    def delete_round(self, index):
        """Delete a round by its index."""
        if 0 <= index < len(self.rounds):
            del self.rounds[index]
            save_json(ROUNDS_FILE, self.rounds)
            self.invalidate_stats_cache()

    def get_filtered_rounds(self, round_type="all", sort_by="recent"):
        """
        Filter and sort rounds.
        round_type: 'all', 'solo', 'scramble'
        sort_by: 'recent', 'best', 'worst'
        
        For best/worst sorting, uses score relative to par to properly compare
        9-hole and 18-hole rounds (e.g., 80 on par 72 = +8, 54 on par 35 = +19)
        """
        rounds_with_idx = [(i, r) for i, r in enumerate(self.rounds)]

        # Filter by type
        if round_type == "solo":
            rounds_with_idx = [(i, r) for i, r in rounds_with_idx
                              if r.get("round_type", "solo") == "solo"]
        elif round_type == "scramble":
            rounds_with_idx = [(i, r) for i, r in rounds_with_idx
                              if r.get("round_type") == "scramble"]

        # Sort
        if sort_by == "recent":
            rounds_with_idx.sort(key=lambda x: x[1].get("date", ""), reverse=True)
        elif sort_by == "best":
            # Sort by score relative to par (lower is better)
            rounds_with_idx.sort(key=lambda x: self._get_score_relative_to_par(x[1]))
        elif sort_by == "worst":
            # Sort by score relative to par (higher is worse)
            rounds_with_idx.sort(key=lambda x: self._get_score_relative_to_par(x[1]), reverse=True)

        return rounds_with_idx
    
    def _get_score_relative_to_par(self, round_data: dict) -> int:
        """
        Calculate score relative to par for proper comparison of 9 vs 18 hole rounds.
        Returns total_score - total_par (e.g., 80 on par 72 = +8)
        """
        total_score = round_data.get("total_score", 999)
        total_par = round_data.get("total_par", 0)
        
        if total_par == 0:
            # Fallback: estimate par based on holes played
            holes_played = round_data.get("holes_played", 18)
            total_par = holes_played * 4  # Assume par 4 average
        
        return total_score - total_par

    # ---- Aggregates ----
    def calculate_9hole_expected_differential(self, handicap_index):
        """
        Calculate expected 9-hole differential based on current handicap index.
        Formula from 2024 WHS rules: Expected Score = (0.52 × Handicap_Index) + 1.2
        """
        if handicap_index is None:
            return None
        return (0.52 * handicap_index) + 1.2

    def calculate_score_differential(self, round_data, current_handicap=None):
        """
        Calculate score differential for a round.
        For 9-hole rounds, uses the 2024 WHS method with expected score.
        """
        try:
            holes_played = round_data.get("holes_played", 18)
            total_score = round_data["total_score"]
            tee_rating = round_data["tee_rating"]
            tee_slope = round_data["tee_slope"]

            if holes_played == 18:
                # Standard 18-hole calculation
                diff = (113 * (total_score - tee_rating)) / tee_slope
            else:
                # 9-hole calculation (2024 WHS rules)
                # First calculate 9-hole differential
                nine_hole_diff = (113 * (total_score - tee_rating)) / tee_slope

                # Add expected differential for the unplayed 9
                if current_handicap is not None:
                    expected_diff = self.calculate_9hole_expected_differential(current_handicap)
                    diff = nine_hole_diff + expected_diff
                else:
                    # If no handicap established, double the 9-hole diff as approximation
                    diff = nine_hole_diff * 2

            return round(diff, 1)
        except (ZeroDivisionError, KeyError):
            return None

    def calculate_handicap_index(self):
        """
        Calculate handicap index using serious, solo rounds (both 9 and 18 hole).
        Uses the official USGA/WHS formula with the handicap table adjustments.
        9-hole rounds are converted to 18-hole equivalents using expected score.
        
        When no 18-hole rounds exist, 9-hole rounds are combined in pairs or
        doubled (as approximation) to establish an initial handicap.
        """
        # Collect all eligible rounds separated by hole count
        rounds_18 = []
        rounds_9 = []
        
        for r in self.rounds:
            is_solo = r.get("round_type", "solo") == "solo"
            is_serious = r.get("is_serious", False)
            
            if is_solo and is_serious:
                holes = r.get("holes_played", 18)
                if holes == 18:
                    rounds_18.append(r)
                elif holes == 9:
                    rounds_9.append(r)
        
        # First pass: calculate differentials for 18-hole rounds to establish base handicap
        diffs_18 = []
        for r in rounds_18:
            diff = self.calculate_score_differential(r)
            if diff is not None:
                diffs_18.append(diff)
        
        # Calculate preliminary handicap from 18-hole rounds if we have enough
        preliminary_handicap = None
        if len(diffs_18) >= 3:
            sorted_diffs = sorted(diffs_18)
            preliminary_handicap = self._apply_handicap_table(sorted_diffs)
        
        # If no preliminary handicap from 18-hole rounds, try to establish one from 9-hole rounds
        # by using the doubling approximation method
        if preliminary_handicap is None and len(rounds_9) >= 3:
            # Calculate approximate differentials by doubling 9-hole diffs
            approx_diffs = []
            for r in rounds_9:
                diff = self.calculate_score_differential(r, current_handicap=None)
                if diff is not None:
                    approx_diffs.append(diff)
            
            if len(approx_diffs) >= 3:
                sorted_approx = sorted(approx_diffs)
                preliminary_handicap = self._apply_handicap_table(sorted_approx)
        
        # Second pass: include all rounds using the preliminary handicap (if available)
        all_diffs = []
        for r in rounds_18:
            diff = self.calculate_score_differential(r)
            if diff is not None:
                all_diffs.append(diff)
        
        for r in rounds_9:
            # Use preliminary handicap if available, otherwise use doubling approximation
            diff = self.calculate_score_differential(r, preliminary_handicap)
            if diff is not None:
                all_diffs.append(diff)
        
        if len(all_diffs) < 3:
            return None
        
        all_diffs.sort()
        return self._apply_handicap_table(all_diffs)

    def _apply_handicap_table(self, sorted_diffs):
        """Apply the USGA handicap table to sorted differentials."""
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

        # Apply 0.96 multiplier (bonus for improvement)
        return round(idx * 0.96, 1)

    def get_handicap_rounds_count(self):
        """Return count of rounds eligible for handicap calculation."""
        count_18 = 0
        count_9 = 0
        for r in self.rounds:
            is_solo = r.get("round_type", "solo") == "solo"
            is_serious = r.get("is_serious", False)
            if is_solo and is_serious:
                if r.get("holes_played") == 18:
                    count_18 += 1
                elif r.get("holes_played") == 9:
                    count_9 += 1
        return {"18_hole": count_18, "9_hole": count_9, "total": count_18 + count_9}

    def get_total_holes_played(self):
        """Return total holes played for handicap-eligible rounds."""
        total = 0
        for r in self.rounds:
            is_solo = r.get("round_type", "solo") == "solo"
            is_serious = r.get("is_serious", False)
            if is_solo and is_serious:
                total += r.get("holes_played", 0)
        return total

    def get_best_round(self, holes_filter=None):
        """
        Get best serious solo round.
        holes_filter: None for any, 18 for 18-hole only, 9 for 9-hole only
        """
        serious_rounds = [r for r in self.rounds
                          if r.get("is_serious")
                          and r.get("round_type", "solo") == "solo"]

        if holes_filter:
            serious_rounds = [r for r in serious_rounds if r.get("holes_played") == holes_filter]

        if not serious_rounds:
            return None

        # For comparison, normalize to score vs par
        def score_vs_par(r):
            return r["total_score"] - r.get("par", 36 if r.get("holes_played") == 9 else 72)

        return min(serious_rounds, key=score_vs_par)

    def get_score_differentials(self):
        """Return list of all score differentials for serious solo rounds."""
        # Get current handicap for 9-hole calculations
        current_handicap = self.calculate_handicap_index()

        diffs = []
        for r in self.rounds:
            is_solo = r.get("round_type", "solo") == "solo"
            is_serious = r.get("is_serious", False)

            if is_solo and is_serious:
                holes = r.get("holes_played", 18)
                if holes == 18:
                    diff = self.calculate_score_differential(r)
                elif holes == 9 and current_handicap is not None:
                    diff = self.calculate_score_differential(r, current_handicap)
                else:
                    continue

                if diff is not None:
                    diffs.append({
                        "diff": diff,
                        "course": r["course_name"],
                        "score": r["total_score"],
                        "holes": holes,
                        "date": r.get("date", "N/A")
                    })

        return sorted(diffs, key=lambda x: x["diff"])

    # ---- Club Distances ----
    def add_club(self, club_data):
        """
        Add a new club.
        club_data: {"name": "7 Iron", "distance": 150, "notes": ""}
        """
        # Check for duplicate
        existing = next((c for c in self.clubs if c["name"].lower() == club_data["name"].lower()), None)
        if existing:
            return False
        self.clubs.append(club_data)
        save_json(CLUBS_FILE, self.clubs)
        return True

    def update_club(self, original_name, club_data):
        """Update an existing club."""
        for i, c in enumerate(self.clubs):
            if c["name"] == original_name:
                self.clubs[i] = club_data
                save_json(CLUBS_FILE, self.clubs)
                return True
        return False

    def delete_club(self, name):
        """Delete a club by name."""
        self.clubs = [c for c in self.clubs if c["name"] != name]
        save_json(CLUBS_FILE, self.clubs)

    def get_clubs_sorted_by_distance(self):
        """Return clubs sorted by distance (longest first)."""
        return sorted(self.clubs, key=lambda c: c.get("distance", 0), reverse=True)

    # ---- Statistics ----
    def get_statistics(self):
        """Return various statistics about the player's rounds."""
        total_rounds = len(self.rounds)
        serious_rounds = len([r for r in self.rounds if r.get("is_serious")])
        solo_rounds = len([r for r in self.rounds if r.get("round_type", "solo") == "solo"])
        scramble_rounds = len([r for r in self.rounds if r.get("round_type") == "scramble"])

        # Count by holes
        rounds_18 = len([r for r in self.rounds if r.get("holes_played") == 18])
        rounds_9 = len([r for r in self.rounds if r.get("holes_played") == 9])

        # Average score for serious 18-hole rounds
        serious_18 = [r for r in self.rounds
                      if r.get("is_serious") and r.get("holes_played") == 18]
        avg_score_18 = None
        if serious_18:
            avg_score_18 = round(mean(r["total_score"] for r in serious_18), 1)

        # Average score for serious 9-hole rounds
        serious_9 = [r for r in self.rounds
                     if r.get("is_serious") and r.get("holes_played") == 9]
        avg_score_9 = None
        if serious_9:
            avg_score_9 = round(mean(r["total_score"] for r in serious_9), 1)

        handicap_counts = self.get_handicap_rounds_count()
        total_holes = self.get_total_holes_played()

        return {
            "total_rounds": total_rounds,
            "serious_rounds": serious_rounds,
            "solo_rounds": solo_rounds,
            "scramble_rounds": scramble_rounds,
            "rounds_18": rounds_18,
            "rounds_9": rounds_9,
            "avg_score_18": avg_score_18,
            "avg_score_9": avg_score_9,
            "handicap_eligible_18": handicap_counts["18_hole"],
            "handicap_eligible_9": handicap_counts["9_hole"],
            "total_holes_played": total_holes
        }

    def get_advanced_statistics(self):
        """
        Calculate advanced statistics from detailed round data.
        Returns GIR, putting stats, strokes-to-green by par type, club usage, etc.
        """
        # Check cache first
        if self.stats_cache.get("valid") and self.stats_cache.get("advanced_stats"):
            return self.stats_cache["advanced_stats"]
        
        stats = {
            "gir": {"par3": [], "par4": [], "par5": [], "overall": []},
            "putts": {"par3": [], "par4": [], "par5": [], "overall": []},
            "strokes_to_green": {"par3": [], "par4": [], "par5": []},
            "three_putt_count": 0,
            "two_putt_count": 0,
            "one_putt_count": 0,
            "total_holes_with_putts": 0,
            "club_usage": {},
            "scramble_opportunities": 0,
            "scramble_successes": 0,
            "fir_attempts": 0,
            "fir_hits": 0,
        }
        
        for rd in self.rounds:
            if not rd.get("detailed_stats"):
                continue
            
            course = self.get_course_by_name(rd["course_name"])
            if not course:
                continue
            
            pars = course["pars"]
            detailed = rd["detailed_stats"]
            
            for hole_idx, hole_data in enumerate(detailed):
                if hole_idx >= len(pars):
                    continue
                    
                par = pars[hole_idx]
                par_key = f"par{par}" if par in [3, 4, 5] else None
                
                strokes_to_green = hole_data.get("strokes_to_green")
                putts = hole_data.get("putts")
                clubs_used = hole_data.get("clubs_used", [])
                score = hole_data.get("score")
                
                # GIR calculation
                if strokes_to_green is not None:
                    gir_target = par - 2  # Par 3: 1 stroke, Par 4: 2 strokes, Par 5: 3 strokes
                    is_gir = strokes_to_green <= gir_target
                    stats["gir"]["overall"].append(1 if is_gir else 0)
                    if par_key:
                        stats["gir"][par_key].append(1 if is_gir else 0)
                        stats["strokes_to_green"][par_key].append(strokes_to_green)
                    
                    # Scramble tracking (missed GIR but made bogey or better)
                    if not is_gir and score is not None:
                        stats["scramble_opportunities"] += 1
                        if score <= par + 1:  # Bogey or better
                            stats["scramble_successes"] += 1
                
                # Putting stats
                if putts is not None:
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
                
                # FIR tracking (fairway in regulation for par 4/5)
                fir = hole_data.get("fir")
                if fir is not None and par in [4, 5]:
                    stats["fir_attempts"] += 1
                    if fir:
                        stats["fir_hits"] += 1
                
                # Club usage tracking
                for club in clubs_used:
                    stats["club_usage"][club] = stats["club_usage"].get(club, 0) + 1
        
        # Calculate averages and percentages
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
            "three_putt_rate": round(stats["three_putt_count"] / stats["total_holes_with_putts"] * 100, 1) if stats["total_holes_with_putts"] > 0 else None,
            "two_putt_rate": round(stats["two_putt_count"] / stats["total_holes_with_putts"] * 100, 1) if stats["total_holes_with_putts"] > 0 else None,
            "one_putt_rate": round(stats["one_putt_count"] / stats["total_holes_with_putts"] * 100, 1) if stats["total_holes_with_putts"] > 0 else None,
            "fir_overall": round(stats["fir_hits"] / stats["fir_attempts"] * 100, 1) if stats["fir_attempts"] > 0 else None,
            "scramble_rate": round(stats["scramble_successes"] / stats["scramble_opportunities"] * 100, 1) if stats["scramble_opportunities"] > 0 else None,
            "club_usage": stats["club_usage"],
            "total_holes_tracked": stats["total_holes_with_putts"],
            "scramble_opportunities": stats["scramble_opportunities"],
            "scramble_successes": stats["scramble_successes"],
        }
        
        # Cache the result
        self.stats_cache["advanced_stats"] = result
        self.stats_cache["valid"] = True
        self.save_stats_cache()
        
        return result
    
    def _calc_percentage(self, values):
        """Calculate percentage from a list of 0s and 1s."""
        if not values:
            return None
        return round(sum(values) / len(values) * 100, 1)
    
    def _calc_average(self, values):
        """Calculate average from a list of numbers."""
        if not values:
            return None
        return round(mean(values), 2)
    
    def get_club_analytics(self):
        """
        Analyze club usage patterns.
        Returns clubs ranked by usage, rarely used clubs, and category breakdown.
        """
        adv_stats = self.get_advanced_statistics()
        club_usage = adv_stats.get("club_usage", {})
        
        if not club_usage:
            return {
                "ranked_clubs": [],
                "rarely_used": [],
                "never_used": [],
                "category_breakdown": {},
                "total_shots": 0
            }
        
        total_shots = sum(club_usage.values())
        
        # Rank clubs by usage (most to least)
        ranked = sorted(club_usage.items(), key=lambda x: x[1], reverse=True)
        ranked_clubs = [
            {"name": name, "count": count, "percentage": round(count / total_shots * 100, 1)}
            for name, count in ranked
        ]
        
        # Find rarely used clubs (< 3% of shots)
        rarely_used = [c for c in ranked_clubs if c["percentage"] < 3]
        
        # Find clubs in bag that were never used
        bag_clubs = [c["name"] for c in self.clubs]
        used_clubs = set(club_usage.keys())
        never_used = [c for c in bag_clubs if c not in used_clubs]
        
        # Category breakdown
        category_breakdown = {}
        for club_name, count in club_usage.items():
            cat_info = CLUB_CATEGORIES.get(club_name, {"category": "other"})
            cat = cat_info["category"]
            category_breakdown[cat] = category_breakdown.get(cat, 0) + count
        
        return {
            "ranked_clubs": ranked_clubs,
            "rarely_used": rarely_used,
            "never_used": never_used,
            "category_breakdown": category_breakdown,
            "total_shots": total_shots
        }
    
    def get_stroke_leak_analysis(self):
        """
        Analyze where the player is losing the most strokes.
        Returns insights about tee-to-green vs putting performance.
        """
        adv_stats = self.get_advanced_statistics()
        
        insights = []
        
        # Check strokes to green vs par expectations
        avg_stg_par4 = adv_stats.get("avg_strokes_to_green_par4")
        if avg_stg_par4 is not None:
            excess = avg_stg_par4 - 2  # Expectation is 2 for par 4
            if excess > 1:
                insights.append({
                    "area": "approach",
                    "severity": "high" if excess > 2 else "medium",
                    "message": f"On Par 4s, you're averaging {avg_stg_par4:.1f} strokes to reach the green (target: 2)",
                    "stat": avg_stg_par4
                })
        
        avg_stg_par3 = adv_stats.get("avg_strokes_to_green_par3")
        if avg_stg_par3 is not None:
            excess = avg_stg_par3 - 1
            if excess > 0.5:
                insights.append({
                    "area": "tee_shots_par3",
                    "severity": "high" if excess > 1 else "medium",
                    "message": f"On Par 3s, you're averaging {avg_stg_par3:.1f} strokes to reach the green (target: 1)",
                    "stat": avg_stg_par3
                })
        
        # Check putting
        three_putt_rate = adv_stats.get("three_putt_rate")
        if three_putt_rate is not None and three_putt_rate > 10:
            insights.append({
                "area": "putting",
                "severity": "high" if three_putt_rate > 20 else "medium",
                "message": f"3-putt rate is {three_putt_rate:.1f}% ({adv_stats.get('total_holes_tracked', 0)} holes tracked)",
                "stat": three_putt_rate
            })
        
        avg_putts = adv_stats.get("avg_putts_overall")
        if avg_putts is not None and avg_putts > 2.1:
            insights.append({
                "area": "putting_avg",
                "severity": "medium",
                "message": f"Averaging {avg_putts:.2f} putts per hole (tour avg: ~1.8)",
                "stat": avg_putts
            })
        
        # GIR insights
        gir_overall = adv_stats.get("gir_overall")
        if gir_overall is not None and gir_overall < 30:
            insights.append({
                "area": "gir",
                "severity": "high" if gir_overall < 20 else "medium",
                "message": f"GIR is {gir_overall:.1f}% (amateur target: 30-40%)",
                "stat": gir_overall
            })
        
        # Sort by severity
        severity_order = {"high": 0, "medium": 1, "low": 2}
        insights.sort(key=lambda x: severity_order.get(x["severity"], 2))
        
        return insights


# ---- Scorecard Export Helper Functions ----
def generate_scorecard_data(backend, round_data):
    """
    Generate formatted scorecard data for export.
    Returns a dictionary with all data needed for PDF/image export.
    """
    course = backend.get_course_by_name(round_data["course_name"])
    pars = course["pars"] if course else [4] * len(round_data.get("scores", []))
    
    # Get yardages if available
    yardages = []
    if course:
        tee_color = round_data.get("tee_color", "")
        yardages = course.get("yardages", {}).get(tee_color, [])
    
    scores = round_data.get("scores", [])
    diff = round_data.get("total_score", 0) - round_data.get("par", 72)
    diff_str = f"+{diff}" if diff > 0 else str(diff)
    
    # Calculate front/back 9 totals
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
            "yards_total": sum(front_9_yards) if front_9_yards else 0
        },
        "back_9": {
            "pars": back_9_pars,
            "scores": back_9_scores,
            "yardages": back_9_yards,
            "par_total": sum(back_9_pars) if back_9_pars else 0,
            "score_total": sum(back_9_scores) if back_9_scores else 0,
            "yards_total": sum(back_9_yards) if back_9_yards else 0
        }
    }