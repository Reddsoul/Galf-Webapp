"""
Scorecard OCR — classic cell-crop pipeline.

Pure OpenCV + Tesseract. No ML models, no external APIs.

Pipeline
--------
1. Preprocess: grayscale, resize long-side=2000, deskew, CLAHE, Otsu.
2. Find table: detect horizontal + vertical lines, get grid bbox.
3. Find rows from horizontal lines (cluster Y positions).
4. Find columns from vertical lines (cluster X positions).
5. Remove grid lines from binary -> clean text image.
6. OCR each cell with Tesseract (PSM 8 digits, PSM 7 labels).
7. Classify rows: HEADER / PAR / HCP / TEE / SKIP.
8. Sample background colour behind tee-row label cell.
9. Course/club name from top 15% via PSM 6.
10. Rating/slope regex over tee-row text.

Public interface
----------------
ScorecardOCR.process_image(image_bytes: bytes, debug: bool = False) -> dict
"""

import io
import json
import os
import re
import sys
import time

import cv2
import numpy as np
import pytesseract
from PIL import Image


# ── Colour normalisation ──────────────────────────────────────────────────────

_COLOR_ALIASES: dict[str, str] = {
    "black":          "Black",  "blk":      "Black",  "championship": "Black",
    "tips":           "Black",  "knight":   "Black",  "tournament":   "Black",
    "blue":           "Blue",   "blu":      "Blue",   "back":         "Blue",
    "white":          "White",  "wht":      "White",  "regular":      "White",
    "middle":         "White",
    "yellow":         "Yellow", "yel":      "Yellow", "senior":       "Yellow",
    "red":            "Red",    "ladies":   "Red",    "women":        "Red",
    "forward":        "Red",
    "gold":           "Gold",   "gld":      "Gold",   "super":        "Gold",
    "green":          "Green",  "grn":      "Green",
    "silver":         "Silver", "slv":      "Silver", "platinum":     "Silver",
}

_NUM_FIX = str.maketrans({
    'O': '0', 'o': '0',
    'l': '1', 'I': '1', '|': '1',
    'S': '5', 's': '5',
    'B': '8',
    'G': '6', 'g': '9',
    'q': '4',
    'D': '0',
    'Z': '2', 'z': '2',
    'T': '7',
})

# Known tee background colours (RGB) with tolerance.
_TEE_COLORS = [
    ("Black",   17,  17,  17, 45),
    ("Blue",    21,  95, 192, 60),
    ("Red",    198,  40,  40, 60),
    ("Gold",   200, 150,  12, 60),
    ("Green",   46, 125,  50, 60),
    ("Silver", 158, 158, 158, 45),
    ("White",  245, 245, 245, 20),
    ("Yellow", 240, 210,  40, 60),
]


def normalize_tee_color(label: str) -> str | None:
    if not label:
        return None
    low = label.lower().strip()
    if low in _COLOR_ALIASES:
        return _COLOR_ALIASES[low]
    parts = low.split()
    if parts and parts[0] in _COLOR_ALIASES:
        return _COLOR_ALIASES[parts[0]]
    for alias, color in _COLOR_ALIASES.items():
        if alias in low:
            return color
    # Fuzzy match against canonical colour names (handles OCR mangling
    # like "Blac" -> "Black", "Slive" -> "Silver", "Gok" -> "Gold")
    first = parts[0] if parts else ""
    if len(first) >= 3:
        canonical = ["black", "blue", "white", "red", "gold", "green",
                     "silver", "yellow"]
        best, best_score = None, 0.0
        for c in canonical:
            # Letter-set overlap on the first 4 chars
            a = set(first[:5])
            b = set(c[:5])
            if not a or not b:
                continue
            overlap = len(a & b) / len(a | b)
            # Bonus if same starting letter
            if first[0] == c[0]:
                overlap += 0.25
            if overlap > best_score:
                best_score = overlap
                best = c
        if best and best_score >= 0.55:
            return best.capitalize()
    return None


def _to_int(s) -> int | None:
    if s is None:
        return None
    cleaned = re.sub(r"[^0-9OolISsBbGgqDdZzT|]", "", str(s))
    if not cleaned:
        return None
    try:
        return int(cleaned.translate(_NUM_FIX))
    except (ValueError, TypeError):
        return None


# ── Main class ────────────────────────────────────────────────────────────────

class ScorecardOCR:

    LONG_SIDE   = 2000
    YARD_MIN    = 80
    YARD_MAX    = 650
    MIN_COLS    = 10
    MIN_ROW_PX  = 8

    _PAR_RE  = re.compile(r"\bpar\b", re.IGNORECASE)
    _HCP_RE  = re.compile(
        r"\b(hdcp|hcp|handicap|stroke|index|m\s*hcp|w\s*hcp)\b", re.IGNORECASE
    )
    _HOLE_RE = re.compile(r"\bhole\b", re.IGNORECASE)
    _SKIP_RE = re.compile(
        r"\b(scorer|attest|date|net|gross|signature|local|rules|"
        r"out|in|total|tot)\b",
        re.IGNORECASE,
    )
    _RATE_LINE_RE = re.compile(
        r"(6\d\.\d|7\d\.\d|8[0-2]\.\d)\s*[/\\\-]\s*(1[0-5]\d|[5-9]\d)"
    )

    # ── Public ────────────────────────────────────────────────────────────────

    def process_image(self, image_bytes: bytes, debug: bool = False) -> dict:
        result = self._empty()

        try:
            pil = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            color_orig = np.array(pil)  # RGB
        except Exception as e:
            raise ValueError(f"Could not decode image: {e}")

        color = self._resize_long_side(color_orig, self.LONG_SIDE)
        gray  = cv2.cvtColor(color, cv2.COLOR_RGB2GRAY)

        # Deskew
        angle = self._estimate_skew(gray)
        if abs(angle) > 0.3:
            color = self._rotate(color, angle)
            gray  = self._rotate(gray,  angle)

        # CLAHE
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        gray_eq = clahe.apply(gray)

        # Otsu binarise (text = white on black for morphology)
        _, binv = cv2.threshold(
            gray_eq, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
        )

        t0 = time.perf_counter()

        # Find grid
        h, w = binv.shape
        h_kern = cv2.getStructuringElement(cv2.MORPH_RECT, (max(10, w // 8), 1))
        v_kern = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(10, h // 15)))
        h_lines = cv2.morphologyEx(binv, cv2.MORPH_OPEN, h_kern)
        v_lines = cv2.morphologyEx(binv, cv2.MORPH_OPEN, v_kern)
        grid    = cv2.bitwise_or(h_lines, v_lines)

        # Find all sizeable grid contours (handles front/back split cards)
        contours, _ = cv2.findContours(
            grid, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        bboxes: list[tuple[int, int, int, int]] = []
        if contours:
            min_area = h * w * 0.008
            for c in contours:
                if cv2.contourArea(c) >= min_area:
                    x_, y_, w_, h_ = cv2.boundingRect(c)
                    if w_ < 80 or h_ < 20:
                        continue
                    bboxes.append((x_, y_, w_, h_))
        # Sort top-to-bottom, left-to-right
        bboxes.sort(key=lambda b: (b[1] // 50, b[0]))

        if not bboxes:
            print("[scorecard_ocr] No grid detected — using projection fallback",
                  file=sys.stderr)
            self._projection_fallback(gray_eq, binv, color, result)
            self._course_name(color_orig, result)
            self._validate(result)
            self._score_confidence(result)
            return result

        # Track per-tee accumulation across tables (front + back nine)
        per_tee_yards: dict[str, list[int]] = {}
        debug_payload = []
        table_min_y = min(b[1] for b in bboxes)
        # Per-table column intervals so the PAR/HDCP scan can reuse them
        # (local — the shared instance serves concurrent Flask requests)
        table_cols: list[tuple[tuple, list[tuple[int, int]]]] = []

        for tbl_idx, (x, y, ww, hh) in enumerate(bboxes):
            # Extend table downward by 60% to capture HDCP/PAR rows whose
            # separator lines are too light for contour detection
            ext_h = min(h - y, int(hh * 1.6))
            gray_t  = gray_eq[y:y + ext_h, x:x + ww]
            color_t = color[y:y + ext_h, x:x + ww]
            binv_t  = binv[y:y + ext_h, x:x + ww]

            hk_t = cv2.getStructuringElement(
                cv2.MORPH_RECT, (max(15, ww // 4), 1)
            )
            h_lines_t = cv2.morphologyEx(binv_t, cv2.MORPH_OPEN, hk_t)
            hh = ext_h

            rows_y = self._cluster_lines(h_lines_t, axis="h")
            if len(rows_y) < 3:
                continue
            rows_y = self._extend_rows_by_text(binv_t, rows_y)
            row_ints = [(rows_y[i], rows_y[i + 1])
                        for i in range(len(rows_y) - 1)
                        if rows_y[i + 1] - rows_y[i] >= self.MIN_ROW_PX]
            if not row_ints:
                continue

            # Derive columns from the HEADER row text positions
            col_ints = self._cols_from_header(gray_t, row_ints[0], ww)
            if len(col_ints) < 6:
                # Fallback: morphological vertical lines
                vk_t = cv2.getStructuringElement(
                    cv2.MORPH_RECT, (1, max(8, ext_h // 4))
                )
                v_lines_t = cv2.morphologyEx(binv_t, cv2.MORPH_OPEN, vk_t)
                cols_x = self._cluster_lines(v_lines_t, axis="v")
                min_col_w = max(self.MIN_ROW_PX, ww // 30)
                col_ints = [(cols_x[i], cols_x[i + 1])
                            for i in range(len(cols_x) - 1)
                            if cols_x[i + 1] - cols_x[i] >= min_col_w]
            if len(col_ints) < 4:
                continue
            table_cols.append(((x, y, ww, hh), col_ints))

            grid_text: list[list[str | None]] = []
            for (ry1, ry2) in row_ints:
                row_cells: list[str | None] = []
                for ci, (cx1, cx2) in enumerate(col_ints):
                    cell = gray_t[ry1:ry2, cx1:cx2]
                    txt = self._ocr_cell(cell, is_label=(ci == 0))
                    row_cells.append(txt)
                grid_text.append(row_cells)

            debug_labels: list[str] = []
            for ri, cells in enumerate(grid_text):
                kind = self._classify_row(cells)
                debug_labels.append(kind)
                if kind == "PAR":
                    self._merge_pars(cells, result)
                elif kind == "HCP":
                    self._merge_hcps(cells, result)
                elif kind == "TEE":
                    self._extract_tee(
                        cells, color_t, row_ints[ri], col_ints,
                        result, per_tee_yards,
                    )

            if debug:
                debug_payload.append(
                    (color_t.copy(), row_ints, col_ints, grid_text, debug_labels,
                     f"table{tbl_idx}")
                )

        # Sweep all tables for a rating/slope summary (e.g. right-side table
        # with "Black 77.2/124 6465 yds" per row).
        self._extract_ratings_summary(color, gray_eq, bboxes, result)

        # PAR / HDCP scan: PSM 6 over each main table region (extended) and
        # look for lines starting with "PAR" / "HDCP".
        self._extract_par_hcp_lines(gray_eq, bboxes, result)
        # Cell-by-cell PAR fallback when line OCR garbles the row
        if len(result["pars"]) < 18:
            self._extract_par_hcp_from_grid(gray_eq, bboxes, binv, result,
                                            table_cols)

        # Course/club from above the top-most table
        self._course_name(color, result, table_top=table_min_y)

        elapsed = time.perf_counter() - t0
        print(f"[scorecard_ocr] {len(bboxes)} tables OCR'd in {elapsed:.2f}s",
              file=sys.stderr)

        # 9 vs 18 hole: use the longest yardage list as ground truth
        max_yards = max(
            (len(t.get("yardages") or []) for t in result["tee_boxes"]),
            default=0,
        )
        if 0 < max_yards <= 10 and 0 < len(result["pars"]) <= 10:
            result["nine_hole_card"] = True

        if debug:
            for payload in debug_payload:
                self._save_debug_image(*payload[:5],
                                        path=f"/tmp/scorecard_debug_{payload[5]}.jpg")

        self._validate(result)
        self._score_confidence(result)
        return result

    # ── Preprocessing ─────────────────────────────────────────────────────────

    @staticmethod
    def _resize_long_side(img: np.ndarray, max_side: int) -> np.ndarray:
        h, w = img.shape[:2]
        long_side = max(h, w)
        if long_side == max_side:
            return img
        scale = max_side / long_side
        new_w = max(1, int(w * scale))
        new_h = max(1, int(h * scale))
        interp = cv2.INTER_AREA if scale < 1 else cv2.INTER_CUBIC
        return cv2.resize(img, (new_w, new_h), interpolation=interp)

    @staticmethod
    def _estimate_skew(gray: np.ndarray) -> float:
        edges = cv2.Canny(gray, 50, 150, apertureSize=3)
        lines = cv2.HoughLines(edges, 1, np.pi / 360, threshold=200)
        if lines is None:
            return 0.0
        angles: list[float] = []
        for rho_theta in lines[:200]:
            _, theta = rho_theta[0]
            deg = (theta * 180.0 / np.pi) - 90.0
            if -15 < deg < 15:
                angles.append(deg)
        if len(angles) < 5:
            return 0.0
        return float(np.median(angles))

    @staticmethod
    def _rotate(img: np.ndarray, angle: float) -> np.ndarray:
        h, w = img.shape[:2]
        M = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
        return cv2.warpAffine(
            img, M, (w, h),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_REPLICATE,
        )

    @staticmethod
    def _cluster_lines(mask: np.ndarray, axis: str, gap: int = 4) -> list[int]:
        """Return sorted line positions (Y for axis='h', X for axis='v')."""
        if axis == "h":
            proj = mask.sum(axis=1)
        else:
            proj = mask.sum(axis=0)
        if proj.max() == 0:
            return []
        thresh = proj.max() * 0.35
        hits = np.where(proj >= thresh)[0]
        if hits.size == 0:
            return []
        clusters: list[list[int]] = [[int(hits[0])]]
        for p in hits[1:]:
            if p - clusters[-1][-1] <= gap:
                clusters[-1].append(int(p))
            else:
                clusters.append([int(p)])
        return [int(np.mean(c)) for c in clusters]

    @staticmethod
    def _cols_from_header(gray_t: np.ndarray, header_row: tuple[int, int],
                           ww: int) -> list[tuple[int, int]]:
        """Use OCR word-box positions in the header row to define columns.
        Header shows '1 2 3 4 5 6 7 8 9 OUT' — each word's centre is a
        column anchor."""
        ry1, ry2 = header_row
        strip = gray_t[ry1:ry2, :]
        if strip.size == 0 or (ry2 - ry1) < 6:
            return []
        # Upscale for stable OCR
        h, w = strip.shape
        scale = 3
        big = cv2.resize(strip, (w * scale, h * scale),
                         interpolation=cv2.INTER_CUBIC)
        try:
            data = pytesseract.image_to_data(
                big, config="--psm 6 --oem 3",
                output_type=pytesseract.Output.DICT,
            )
        except Exception:
            return []
        centres: list[int] = []
        for i, txt in enumerate(data["text"]):
            t = (txt or "").strip()
            if not t:
                continue
            # Only accept hole-number / OUT / IN tokens
            if not (t.isdigit() or t.upper() in ("OUT", "IN", "TOT", "TOTAL")):
                continue
            cx = (data["left"][i] + data["width"][i] // 2) // scale
            centres.append(cx)
        centres = sorted(set(centres))
        if len(centres) < 6:
            return []
        # Build column intervals: midpoints between centres
        bounds: list[int] = [0]
        for i in range(len(centres) - 1):
            bounds.append((centres[i] + centres[i + 1]) // 2)
        bounds.append(ww)
        # Insert a leading "label" column before the first centre
        first_centre = centres[0]
        label_right = max(8, first_centre - (centres[1] - first_centre) // 2)
        # Bounds: [0, label_right, mid01, mid12, ..., ww]
        bounds = [0, label_right] + bounds[1:]
        ints = [(bounds[i], bounds[i + 1])
                 for i in range(len(bounds) - 1)
                 if bounds[i + 1] - bounds[i] >= 8]
        return ints

    @staticmethod
    def _extend_rows_by_text(binv_t: np.ndarray, rows_y: list[int]) -> list[int]:
        """Below last detected line, find text bands as additional row borders."""
        h, w = binv_t.shape
        if not rows_y:
            return rows_y
        bottom = rows_y[-1] + 2
        if bottom >= h - 10:
            return rows_y
        region = binv_t[bottom:]
        row_density = region.sum(axis=1).astype(np.float32)
        if row_density.max() == 0:
            return rows_y
        # Smooth
        k = np.ones(3, dtype=np.float32) / 3
        sm = np.convolve(row_density, k, mode="same")
        thresh = sm.max() * 0.2
        in_text = sm >= thresh
        extras: list[int] = []
        i = 0
        while i < len(in_text):
            if in_text[i]:
                start = i
                while i < len(in_text) and in_text[i]:
                    i += 1
                end = i
                if end - start >= 6:
                    extras.append(bottom + start - 2)
                    extras.append(bottom + end + 2)
            else:
                i += 1
        merged = list(rows_y)
        for e in extras:
            if 0 <= e < h and all(abs(e - r) > 4 for r in merged):
                merged.append(e)
        merged.sort()
        return merged

    # ── Tesseract ─────────────────────────────────────────────────────────────

    @staticmethod
    def _ocr_cell(cell: np.ndarray, is_label: bool) -> str | None:
        """OCR a single grayscale cell crop. Handles dark/light backgrounds."""
        if cell is None or cell.size == 0:
            return None
        h, w = cell.shape[:2]
        if h < 10 or w < 10:
            return None
        # Inset to drop grid lines (lighter on narrow cells)
        inset_y = max(1, h // 12)
        inset_x = 2 if w < 50 else max(2, w // 12)
        if h - 2 * inset_y < 6 or w - 2 * inset_x < 6:
            return None
        inner = cell[inset_y:h - inset_y, inset_x:w - inset_x]

        # Decide polarity from border pixels (sampled away from text centre)
        bord_pad = max(1, min(inner.shape) // 6)
        border_pixels = np.concatenate([
            inner[:bord_pad].ravel(),
            inner[-bord_pad:].ravel(),
            inner[:, :bord_pad].ravel(),
            inner[:, -bord_pad:].ravel(),
        ])
        bg_mean = float(np.median(border_pixels))
        if bg_mean < 130:
            inner = 255 - inner

        # Local contrast boost
        try:
            inner = cv2.normalize(inner, None, 0, 255, cv2.NORM_MINMAX)
        except cv2.error:
            return None

        # Pad with white
        padded = cv2.copyMakeBorder(
            inner, 8, 8, 8, 8, cv2.BORDER_CONSTANT, value=255
        )
        # Upscale to ~64px tall for Tesseract
        ph, pw = padded.shape[:2]
        scale = max(1.0, 64.0 / ph)
        resized = cv2.resize(
            padded, (max(16, int(pw * scale)), max(32, int(ph * scale))),
            interpolation=cv2.INTER_CUBIC,
        )
        # Otsu threshold to clean binary
        _, bw = cv2.threshold(
            resized, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
        )

        try:
            if is_label:
                # Multi-line label (e.g. "Black\n77.2/124") — PSM 6
                raw = pytesseract.image_to_string(bw, config="--psm 6 --oem 3")
                lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
                # Prefer first line containing alphas
                txt = next(
                    (ln for ln in lines if any(c.isalpha() for c in ln)),
                    raw,
                )
            else:
                # PSM 7 handles multi-digit numbers better than PSM 8 on small cells
                cfg = ("--psm 7 --oem 3 "
                       "-c tessedit_char_whitelist=0123456789")
                txt = pytesseract.image_to_string(bw, config=cfg).strip()
                if not txt:
                    cfg = ("--psm 8 --oem 3 "
                           "-c tessedit_char_whitelist=0123456789")
                    txt = pytesseract.image_to_string(bw, config=cfg)
        except Exception:
            return None
        txt = txt.strip()
        if not txt:
            return None
        if not is_label:
            txt = txt.translate(_NUM_FIX)
            txt = re.sub(r"[^0-9]", "", txt)
            return txt or None
        return txt

    @staticmethod
    def _split_merged_yards(s: str) -> list[int]:
        """OCR sometimes glues two adjacent yardage cells: '215365' -> [215, 365].
        Returns split values if they're plausible yardages, else single value."""
        if not s:
            return []
        digits = re.sub(r"[^0-9]", "", s)
        n = len(digits)
        if 5 <= n <= 7 and n % 2 == 0:
            half = n // 2
            a, b = int(digits[:half]), int(digits[half:])
            if 80 <= a <= 650 and 80 <= b <= 650:
                return [a, b]
        if n == 6:
            a, b = int(digits[:3]), int(digits[3:])
            if 80 <= a <= 650 and 80 <= b <= 650:
                return [a, b]
        try:
            return [int(digits)]
        except ValueError:
            return []

    # Backwards-compat merge helpers
    def _merge_pars(self, cells: list[str | None], result: dict):
        """Append pars from this row to existing pars (front+back nine)."""
        vals = []
        for c in cells[1:]:
            n = _to_int(c)
            if n in (3, 4, 5):
                vals.append(n)
        if not vals:
            return
        # Append (front-nine table first, back-nine second)
        existing = result["pars"]
        merged = existing + vals
        # Cap and prefer the longest unique stream
        if len(merged) <= 18 and len(merged) > len(existing):
            result["pars"] = merged[:18]
        elif len(vals) >= 9 and len(existing) == 0:
            result["pars"] = vals[:18]

    def _merge_hcps(self, cells: list[str | None], result: dict):
        vals = []
        for c in cells[1:]:
            n = _to_int(c)
            if n is not None and 1 <= n <= 18:
                vals.append(n)
        if not vals:
            return
        existing = result["handicaps"]
        merged = existing + vals
        if len(merged) <= 18 and len(merged) > len(existing):
            result["handicaps"] = merged[:18]
        elif len(vals) >= 9 and len(existing) == 0:
            result["handicaps"] = vals[:18]

    # ── Row classification ───────────────────────────────────────────────────

    def _classify_row(self, cells: list[str | None]) -> str:
        if not cells:
            return "SKIP"
        label = (cells[0] or "").strip()
        rest  = cells[1:]
        rest_nonempty = [c for c in rest if c]

        # Numeric values across the row; expand merged 2-cell hits
        nums: list[int] = []
        for c in rest_nonempty:
            for n in self._split_merged_yards(c):
                nums.append(n)

        low = label.lower()
        if self._SKIP_RE.search(low):
            return "SKIP"
        if self._HOLE_RE.search(low):
            return "HEADER"
        if self._HCP_RE.search(low):
            return "HCP"
        if self._PAR_RE.search(low):
            return "PAR"

        # Heuristic: header = monotonic 1..9 or 10..18 with OCR slack
        seq = [_to_int(c) for c in rest_nonempty]
        seq_clean = [n for n in seq if n is not None]
        if len(seq_clean) >= 7:
            mono = all(seq_clean[i] <= seq_clean[i + 1] + 1
                       for i in range(len(seq_clean) - 1))
            small_range = (min(seq_clean) >= 1 and max(seq_clean) <= 18
                            and (max(seq_clean) - min(seq_clean)) <= 9)
            if mono and small_range:
                return "HEADER"

        # Unlabelled par: most values in {3,4,5}
        if nums:
            par_like = sum(1 for n in nums if n in (3, 4, 5))
            if par_like >= 7 and par_like / max(1, len(nums)) >= 0.7:
                return "PAR"

        # HCP: most values 1..18, no value > 18
        if nums and len(nums) >= 7:
            hcp_like = sum(1 for n in nums if 1 <= n <= 18)
            if hcp_like / len(nums) >= 0.8 and max(nums) <= 18:
                return "HCP"

        # Tee: yardage range dominates the row
        yards = [n for n in nums if self.YARD_MIN <= n <= self.YARD_MAX]
        # Label may include rating/slope appended ("Black 77.2/124")
        has_alpha_label = bool(label) and any(c.isalpha() for c in label)
        if has_alpha_label and len(yards) >= 3:
            return "TEE"
        if len(yards) >= 5:
            return "TEE"

        return "SKIP"

    # ── Extractors ───────────────────────────────────────────────────────────

    def _extract_pars(self, cells: list[str | None], result: dict):
        vals = []
        for c in cells[1:]:
            n = _to_int(c)
            if n in (3, 4, 5):
                vals.append(n)
            if len(vals) >= 18:
                break
        if len(vals) >= 7 and len(vals) > sum(1 for p in result["pars"]
                                              if p in (3, 4, 5)):
            result["pars"] = vals[:18]

    def _extract_hcps(self, cells: list[str | None], result: dict):
        vals = []
        for c in cells[1:]:
            n = _to_int(c)
            if n is not None and 1 <= n <= 18:
                vals.append(n)
            if len(vals) >= 18:
                break
        if len(vals) >= 7 and len(vals) > len(result["handicaps"]):
            result["handicaps"] = vals[:18]

    def _extract_tee(self, cells: list[str | None], color_t: np.ndarray,
                     row_int: tuple[int, int], col_ints: list[tuple[int, int]],
                     result: dict,
                     per_tee_yards: dict | None = None):
        label = (cells[0] or "").strip()
        # Expand merged-cell numbers ("215365" -> 215, 365) before filtering
        yards: list[int] = []
        for c in cells[1:]:
            if not c:
                continue
            for n in self._split_merged_yards(c):
                if self.YARD_MIN <= n <= self.YARD_MAX:
                    yards.append(n)
        if len(yards) < 3:
            return

        # Colour: prefer label normalisation (more reliable than bg sample)
        label_color = normalize_tee_color(label)
        bg_color    = self._sample_bg_color(color_t, row_int, col_ints[0])
        color = label_color or bg_color
        if not label and bg_color:
            label = bg_color
        if not label:
            return

        # Rating/slope from row text
        rating, slope = None, None
        full_text = " ".join(c for c in cells if c)
        m = self._RATE_LINE_RE.search(full_text)
        if m:
            rating = float(m.group(1))
            slope  = int(m.group(2))

        # Identify tee by colour (preferred) or normalised label
        key = (color or normalize_tee_color(label) or label).lower()

        # Track per-tee yardage accumulation across tables
        if per_tee_yards is not None:
            per_tee_yards.setdefault(key, [])
            per_tee_yards[key].extend(yards[:9])

        existing = None
        for t in result["tee_boxes"]:
            tk = (t.get("color") or normalize_tee_color(t["label"])
                  or t["label"]).lower()
            if tk == key:
                existing = t
                break

        if existing:
            if per_tee_yards is not None:
                existing["yardages"] = per_tee_yards[key][:18]
            elif len(yards) > len(existing.get("yardages") or []):
                existing["yardages"] = yards[:18]
            if rating and not existing.get("rating"):
                existing["rating"] = rating
                existing["slope"]  = slope
            if color and not existing.get("color"):
                existing["color"] = color
        else:
            result["tee_boxes"].append({
                "label":    label or (color or "Unknown"),
                "color":    color,
                "rating":   rating,
                "slope":    slope,
                "yardages": (per_tee_yards[key][:18] if per_tee_yards is not None
                             else yards[:18]),
            })

    @staticmethod
    def _sample_bg_color(color_t: np.ndarray,
                          row_int: tuple[int, int],
                          col_int: tuple[int, int]) -> str | None:
        ry1, ry2 = row_int
        cx1, cx2 = col_int
        h, w = color_t.shape[:2]
        ry1 = max(0, ry1); ry2 = min(h, ry2)
        cx1 = max(0, cx1); cx2 = min(w, cx2)
        if ry2 <= ry1 or cx2 <= cx1:
            return None
        crop = color_t[ry1:ry2, cx1:cx2]
        if crop.size == 0:
            return None
        # Use border pixels — text occupies the centre
        border_pad = max(1, (ry2 - ry1) // 5)
        top    = crop[:border_pad].reshape(-1, 3)
        bottom = crop[-border_pad:].reshape(-1, 3)
        sample = np.concatenate([top, bottom], axis=0)
        med = np.median(sample, axis=0)
        r, g, b = int(med[0]), int(med[1]), int(med[2])
        best = None
        best_d = 1e9
        for name, rc, gc, bc, tol in _TEE_COLORS:
            d = abs(r - rc) + abs(g - gc) + abs(b - bc)
            if d < best_d and abs(r - rc) <= tol and abs(g - gc) <= tol and abs(b - bc) <= tol:
                best_d = d
                best = name
        return best

    # ── Ratings summary table (sidebar with "Black 77.2/124 6465 yds") ───────

    def _extract_ratings_summary(self, color: np.ndarray, gray_eq: np.ndarray,
                                  bboxes: list[tuple[int, int, int, int]],
                                  result: dict):
        """Scan every detected table region with PSM 6, regex out tee+rating."""
        for (x, y, ww, hh) in bboxes:
            region = gray_eq[y:y + hh, x:x + ww]
            try:
                text = pytesseract.image_to_string(region, config="--psm 6 --oem 3")
            except Exception:
                continue
            for line in text.splitlines():
                line = line.strip()
                if not line:
                    continue
                m = self._RATE_LINE_RE.search(line)
                if not m:
                    continue
                rating = float(m.group(1))
                slope  = int(m.group(2))
                # Find the tee label on this line
                low = line.lower()
                color_match = None
                for alias, name in _COLOR_ALIASES.items():
                    if re.search(rf"\b{alias}\b", low):
                        color_match = name
                        break
                if not color_match:
                    continue
                # Apply to matching tee_box (or create one)
                found = False
                for t in result["tee_boxes"]:
                    tk = (t.get("color") or normalize_tee_color(t["label"])
                          or t["label"]).lower()
                    if tk == color_match.lower():
                        if not t.get("rating"):
                            t["rating"] = rating
                            t["slope"]  = slope
                        if not t.get("color"):
                            t["color"] = color_match
                        found = True
                        break
                if not found:
                    result["tee_boxes"].append({
                        "label":    color_match,
                        "color":    color_match,
                        "rating":   rating,
                        "slope":    slope,
                        "yardages": [],
                    })

    def _extract_par_hcp_from_grid(self, gray_eq: np.ndarray,
                                     bboxes: list[tuple[int, int, int, int]],
                                     binv: np.ndarray, result: dict,
                                     saved_cols: list | None = None):
        """For each wide table, build column positions and OCR the strip
        below the grid cell-by-cell to recover PAR row."""
        h_img, w_img = gray_eq.shape
        wide = [b for b in bboxes if b[2] > w_img * 0.15]
        wide.sort(key=lambda b: b[0])
        front_pars: list[int] = []
        back_pars:  list[int] = []
        # Prefer header-derived cols that were captured during main pass
        saved_cols = saved_cols or []
        for idx, (x, y, ww, hh) in enumerate(wide[:2]):
            below_y = y + hh
            ext_bot = min(h_img, below_y + int(hh * 0.8))
            if ext_bot - below_y < 12:
                continue
            # Find matching saved col_ints
            col_ints = None
            for (bx, by, bw, bh), ints in saved_cols:
                if abs(bx - x) < 5 and abs(by - y) < 5:
                    col_ints = ints
                    break
            if not col_ints:
                binv_grid = binv[y:y + hh, x:x + ww]
                vk = cv2.getStructuringElement(
                    cv2.MORPH_RECT, (1, max(8, hh // 4))
                )
                v_lines = cv2.morphologyEx(binv_grid, cv2.MORPH_OPEN, vk)
                cols_x = self._cluster_lines(v_lines, axis="v")
                if len(cols_x) < 6:
                    continue
                min_col_w = max(self.MIN_ROW_PX, ww // 30)
                col_ints = [(cols_x[i], cols_x[i + 1])
                             for i in range(len(cols_x) - 1)
                             if cols_x[i + 1] - cols_x[i] >= min_col_w]
            if not col_ints:
                continue

            # Find text bands within the strip below the grid
            strip = gray_eq[below_y:ext_bot, x:x + ww]
            binv_strip = binv[below_y:ext_bot, x:x + ww]
            row_density = binv_strip.sum(axis=1).astype(np.float32)
            if row_density.max() == 0:
                continue
            sm = np.convolve(row_density,
                             np.ones(3, dtype=np.float32) / 3, mode="same")
            thresh = sm.max() * 0.12
            bands: list[tuple[int, int]] = []
            i = 0
            while i < len(sm):
                if sm[i] >= thresh:
                    start = i
                    while i < len(sm) and sm[i] >= thresh:
                        i += 1
                    if i - start >= 4:
                        bands.append((max(0, start - 1),
                                      min(len(sm), i + 1)))
                else:
                    i += 1
            if not bands:
                continue
            # For each band, OCR each cell using col_ints
            for ry1, ry2 in bands[:6]:
                cells: list[str | None] = []
                for cx1, cx2 in col_ints:
                    cell = strip[ry1:ry2, cx1:cx2]
                    txt = self._ocr_cell(cell, is_label=False)
                    cells.append(txt)
                label_cell = strip[ry1:ry2, col_ints[0][0]:col_ints[0][1]]
                lbl = self._ocr_cell(label_cell, is_label=True) or ""

                # Extract every individual digit in each cell; any 3/4/5
                # digit is a candidate par
                par_vals: list[int] = []
                for c in cells[1:]:
                    if not c:
                        continue
                    for d in c:
                        if d in "345":
                            par_vals.append(int(d))

                low = lbl.lower()
                par_label = bool(re.search(r"\bpar\b|^pa[a-z]?$|^p4r$", low))
                # Or: most digits in non-empty cells are 3/4/5
                all_digits = "".join(c for c in cells[1:] if c)
                par_like = (len(all_digits) >= 5
                            and sum(1 for d in all_digits if d in "345")
                                >= len(all_digits) * 0.6)
                if (par_label or par_like) and par_vals:
                    if idx == 0 and len(par_vals) > len(front_pars):
                        front_pars = par_vals[:9]
                    elif idx == 1 and len(par_vals) > len(back_pars):
                        back_pars = par_vals[:9]

        merged = front_pars + back_pars
        if merged and len(merged) > len(result["pars"]):
            result["pars"] = merged[:18]

    def _extract_par_hcp_lines(self, gray_eq: np.ndarray,
                                 bboxes: list[tuple[int, int, int, int]],
                                 result: dict):
        h_img, w_img = gray_eq.shape
        front_pars: list[int] = []
        back_pars:  list[int] = []
        front_hcps: list[int] = []
        back_hcps:  list[int] = []

        # Take the two largest "wide" tables (front + back nine main tables)
        wide = [b for b in bboxes if b[2] > w_img * 0.15]
        wide.sort(key=lambda b: b[0])  # left-to-right

        for idx, (x, y, ww, hh) in enumerate(wide[:2]):
            # Focus on the strip *below* the main grid where PAR/HDCP live
            below_y = y + hh
            ext_bottom = min(h_img, below_y + int(hh * 0.7))
            if ext_bottom - below_y < 10:
                continue
            strip = gray_eq[below_y:ext_bottom, x:x + ww]
            # Upscale strip 2x for tighter OCR on small print
            strip = cv2.resize(strip, (strip.shape[1] * 2, strip.shape[0] * 2),
                                interpolation=cv2.INTER_CUBIC)
            try:
                text = pytesseract.image_to_string(
                    strip, config="--psm 6 --oem 3"
                )
            except Exception:
                continue
            for line in text.splitlines():
                low = line.strip().lower()
                if not low:
                    continue
                nums = [int(n) for n in re.findall(r"\d+", line)]
                # PAR row: explicit label or row with mostly {3,4,5}
                par_label = bool(re.search(r"\bpar\b|^par\b|^pa[a-z]?\b", low))
                par_vals  = [n for n in nums if n in (3, 4, 5)]
                par_like  = (len(par_vals) >= 7
                              and len(par_vals) >= len(nums) - 2)
                if par_label or par_like:
                    vals = par_vals[:9]
                    if vals:
                        if idx == 0 and len(vals) > len(front_pars):
                            front_pars = vals
                        elif idx == 1 and len(vals) > len(back_pars):
                            back_pars = vals
                        continue

                hcp_label = bool(re.search(r"\b(hdcp|hcp|handicap|hoce|hoop)\b",
                                            low))
                if hcp_label:
                    vals = [n for n in nums if 1 <= n <= 18][:9]
                    if idx == 0:
                        front_hcps = vals
                    else:
                        back_hcps = vals

        pars = front_pars + back_pars
        if pars and len(pars) > len(result["pars"]):
            result["pars"] = pars[:18]
        hcps = front_hcps + back_hcps
        if hcps and len(hcps) > len(result["handicaps"]):
            result["handicaps"] = hcps[:18]

    # ── Course/club name from above-table band ───────────────────────────────

    def _course_name(self, color: np.ndarray, result: dict,
                      table_top: int | None = None):
        h, w = color.shape[:2]
        if table_top and table_top > 30:
            band = color[:table_top]
        else:
            band = color[: max(30, int(h * 0.15))]
        if band.size == 0:
            return
        gray = cv2.cvtColor(band, cv2.COLOR_RGB2GRAY)
        try:
            text = pytesseract.image_to_string(gray, config="--psm 6 --oem 3")
        except Exception:
            return
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        long_lines = [
            ln for ln in lines
            if sum(c.isalpha() for c in ln) >= 4
            and not self._SKIP_RE.search(ln.lower())
            and not self._PAR_RE.search(ln.lower())
        ]
        if long_lines and not result["course_name"]:
            result["course_name"] = long_lines[0]
        if len(long_lines) >= 2 and not result["club_name"]:
            result["club_name"] = long_lines[1]

    # ── Projection fallback (no grid lines detected) ─────────────────────────

    def _projection_fallback(self, gray_eq: np.ndarray, binv: np.ndarray,
                              color: np.ndarray, result: dict):
        # Row strips from horizontal projection
        proj = binv.sum(axis=1).astype(np.float32)
        if proj.max() == 0:
            return
        # Smooth
        kernel = np.ones(5, dtype=np.float32) / 5.0
        smooth = np.convolve(proj, kernel, mode="same")
        # Peaks: above 0.4 * max with min spacing
        thresh = smooth.max() * 0.3
        peaks: list[int] = []
        min_gap = max(8, gray_eq.shape[0] // 80)
        for i in range(1, len(smooth) - 1):
            if smooth[i] >= thresh and smooth[i] >= smooth[i - 1] and smooth[i] >= smooth[i + 1]:
                if not peaks or i - peaks[-1] >= min_gap:
                    peaks.append(i)
        if len(peaks) < 3:
            return
        half = min_gap
        white = cv2.bitwise_not(binv)
        for p in peaks:
            y1 = max(0, p - half); y2 = min(white.shape[0], p + half)
            strip = white[y1:y2]
            try:
                text = pytesseract.image_to_string(strip, config="--psm 11 --oem 3")
            except Exception:
                continue
            toks = re.findall(r"[A-Za-z][A-Za-z'/\-]+|\d+", text)
            if not toks:
                continue
            # Treat first alpha as label, parse rest
            cells = [toks[0]] + toks[1:]
            kind = self._classify_row(cells)
            if kind == "PAR":
                self._extract_pars(cells, result)
            elif kind == "HCP":
                self._extract_hcps(cells, result)
            elif kind == "TEE":
                # Approx row interval; first col = first 5% of width
                row_int = (y1, y2)
                col_ints = [(0, color.shape[1] // 12)]
                self._extract_tee(cells, color, row_int, col_ints, result)

    # ── Debug overlay ────────────────────────────────────────────────────────

    @staticmethod
    def _save_debug_image(color_t: np.ndarray,
                           row_ints: list[tuple[int, int]],
                           col_ints: list[tuple[int, int]],
                           grid_text: list[list[str | None]],
                           row_kinds: list[str],
                           path: str = "/tmp/scorecard_debug.jpg"):
        out = cv2.cvtColor(color_t, cv2.COLOR_RGB2BGR).copy()
        font  = cv2.FONT_HERSHEY_SIMPLEX
        scale = 0.4
        for ri, (ry1, ry2) in enumerate(row_ints):
            cv2.putText(out, row_kinds[ri], (2, ry1 + 14),
                        font, scale, (0, 0, 255), 1, cv2.LINE_AA)
            for ci, (cx1, cx2) in enumerate(col_ints):
                cv2.rectangle(out, (cx1, ry1), (cx2, ry2), (0, 200, 0), 1)
                txt = grid_text[ri][ci] if ri < len(grid_text) and ci < len(grid_text[ri]) else None
                if txt:
                    cv2.putText(out, str(txt)[:6], (cx1 + 2, ry1 + 14),
                                font, scale, (255, 0, 0), 1, cv2.LINE_AA)
        cv2.imwrite(path, out)
        print(f"[scorecard_ocr] Debug image: {path}", file=sys.stderr)

    # ── Output schema ────────────────────────────────────────────────────────

    @staticmethod
    def _empty() -> dict:
        return {
            "course_name":      None,
            "club_name":        None,
            "nine_hole_card":   False,
            "multiple_courses": None,
            "tee_boxes":        [],
            "pars":             [],
            "handicaps":        [],
            "warnings":         [],
            "confidence":       {"overall": 0.0, "pars": 0.0,
                                 "ratings": 0.0, "yardages": 0.0},
        }

    def _validate(self, result: dict):
        w    = result.setdefault("warnings", [])
        n    = 9 if result.get("nine_hole_card") else 18
        pars = result.get("pars", [])
        if not pars or all(v is None for v in pars):
            w.append("No par values extracted")
        else:
            bad = [i + 1 for i, p in enumerate(pars)
                   if p is not None and p not in (3, 4, 5)]
            if bad:
                w.append(f"Unexpected par values at holes: {bad}")
            missing = [i + 1 for i, p in enumerate(pars) if p is None]
            if missing:
                w.append(f"Could not read par for holes: {missing}")
        if result.get("nine_hole_card"):
            w.append("Card appears to be 9-hole only")
        for tee in result.get("tee_boxes", []):
            lbl     = tee.get("label", "?")
            n_yards = len(tee.get("yardages") or [])
            if tee.get("rating") is None:
                w.append(f"No rating/slope for tee: {lbl}")
            if n_yards < n:
                w.append(f"Only {n_yards}/{n} yardages for tee: {lbl}")

    def _score_confidence(self, result: dict):
        n    = 9 if result.get("nine_hole_card") else 18
        pars = result.get("pars", [])
        valid_pars = [v for v in pars if v is not None]
        pc   = min(1.0, len(valid_pars) / n) if pars else 0.0

        all_y = [y for t in result.get("tee_boxes", [])
                   for y in (t.get("yardages") or [])]
        yc = (sum(1 for y in all_y if y) / len(all_y)) if all_y else 0.0

        tees = result.get("tee_boxes", [])
        rc   = (sum(1 for t in tees if t.get("rating") and t.get("slope")) /
                len(tees)) if tees else 0.0

        result["confidence"] = {
            "overall":  round(0.40 * yc + 0.35 * pc + 0.25 * rc, 2),
            "pars":     round(pc, 2),
            "ratings":  round(rc, 2),
            "yardages": round(yc, 2),
        }


# ── CLI ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scorecard_ocr.py <image_path>", file=sys.stderr)
        sys.exit(1)
    path = sys.argv[1]
    if not os.path.exists(path):
        print(f"Not found: {path}", file=sys.stderr)
        sys.exit(1)
    with open(path, "rb") as f:
        data = f.read()
    ocr = ScorecardOCR()
    out = ocr.process_image(data, debug=True)
    print(json.dumps(out, indent=2))
