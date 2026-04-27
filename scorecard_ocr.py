"""
Scorecard OCR — local, no internet required.
Uses Tesseract + OpenCV only.

Strategy
--------
1. Detect PAR row by its green background (#dff0d8) using RGB colour analysis.
2. Detect tee-colour rows by their known background colours.
3. For each detected row strip:
     - Clip to a 50:1 max aspect ratio (removes back panels / extra page area).
     - Downscale to TARGET_STRIP_W pixels wide.
     - Run Tesseract PSM 11 (sparse text) — works reliably on wide, thin strips.
4. Parse tokens left-to-right:
     - PAR strip  → values in {3, 4, 5}
     - Tee strips → label + values in 80–650 (totals >650 excluded automatically)
5. Fallback: if colour detection yields no PAR, run a strip-based scan on the
   binarised image using horizontal line detection.

Produces the JSON schema expected by the +Add Course editor in index.html.
"""

import io
import math
import re

import cv2
import numpy as np
import pytesseract
from PIL import Image

# ── Colour normalisation ───────────────────────────────────────────────────────

_COLOR_ALIASES: dict[str, str] = {
    "black":          "Black",  "blk":      "Black",  "championship": "Black",
    "tips":           "Black",  "knight":   "Black",
    "blue":           "Blue",   "blu":      "Blue",   "back":         "Blue",
    "white":          "White",  "wht":      "White",  "regular":      "White",
    "middle":         "White",
    "yellow":         "Yellow", "yel":      "Yellow", "senior":       "Yellow",
    "red":            "Red",    "ladies":   "Red",    "women":        "Red",
    "forward":        "Red",
    "gold":           "Gold",   "gld":      "Gold",   "super":        "Gold",
    "green":          "Green",  "grn":      "Green",
    "silver":         "Silver", "slv":      "Silver", "platinum":     "Silver",
    "tournament":     "Black",
}

_NUM_FIX = str.maketrans("OlISBGgqDZ", "0115860408")

# Known tee background colours (RGB) with tolerance used for row detection.
# Each entry: (label_hint, R_center, G_center, B_center, tolerance)
_TEE_COLORS = [
    ("Black",  17,  17,  17, 40),
    ("Blue",   21,  95, 192, 50),
    ("Red",   198,  40,  40, 50),
    ("Gold",  200, 150,  12, 55),
    ("Green",  46, 125,  50, 50),
    ("Silver", 158, 158, 158, 40),
    # White/Championship tees have near-white bg — detected via label text only
]


def normalize_tee_color(label: str) -> str | None:
    if not label:
        return None
    low = label.lower().strip()
    if low in _COLOR_ALIASES:
        return _COLOR_ALIASES[low]
    first = low.split()[0] if low.split() else ""
    if first in _COLOR_ALIASES:
        return _COLOR_ALIASES[first]
    for alias, color in _COLOR_ALIASES.items():
        if alias in low:
            return color
    return None


def _to_int(s: str) -> int | None:
    if not s:
        return None
    cleaned = re.sub(r"[^0-9OlISBGgqDZ]", "", str(s))
    if not cleaned:
        return None
    try:
        return int(cleaned.translate(_NUM_FIX))
    except (ValueError, TypeError):
        return None


# ── Main class ─────────────────────────────────────────────────────────────────

class ScorecardOCR:

    # Width (px) to downscale each row strip to before Tesseract.
    # Keeps strips wide enough to preserve text while capping aspect ratio.
    TARGET_STRIP_W = 1500

    # Max aspect ratio for a strip — clips back panels / page-level content.
    MAX_STRIP_AR = 50

    _CFG_PSM11 = "--psm 11 --oem 3"
    _CFG_PSM7  = "--psm 7  --oem 3"
    _CFG_PSM6  = "--psm 6  --oem 3"

    _PAR_RE  = re.compile(r"\bpar\b",   re.IGNORECASE)
    _HCP_RE  = re.compile(r"\b(hdcp|hcp|handicap|m\s*hcp|w\s*hcp|stroke)\b", re.IGNORECASE)
    _SKIP_RE = re.compile(r"\b(scorer|attest|date|net|gross|local|rules|rating|slope)\b",
                          re.IGNORECASE)
    _RATE_RE = re.compile(r"(6\d\.\d|7\d\.\d|8[0-2]\.\d)\s*/\s*(1[0-5]\d|[5-9]\d)")

    # ── Public ────────────────────────────────────────────────────────────────

    def process_image(self, image_bytes: bytes) -> dict:
        result = self._empty()

        try:
            pil = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            img = np.array(pil)
        except Exception as e:
            raise ValueError(f"Could not decode image: {e}")

        # Deskew the full RGB image so all colour-based row detection sees
        # horizontal bands (even on photos rotated up to ~5°).
        gray  = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        angle = self._detect_skew(gray)
        if abs(angle) >= 0.3:
            img  = self._rotate_rgb(img, angle)
            gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)

        h, w = img.shape[:2]
        gray = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)

        # Course name from top portion of image
        top_h    = max(1, h // 7)
        top_text = pytesseract.image_to_string(gray[:top_h, :], config=self._CFG_PSM6)
        self._extract_course_name(top_text, result)

        # ── PAR row via green colour detection ────────────────────────────────
        par_found = self._process_par_row(img, result)

        # ── Tee rows via background colour detection ──────────────────────────
        self._process_tee_rows(img, result)

        # ── Fallback: binarise + strip scan ──────────────────────────────────
        if not par_found or not result["tee_boxes"]:
            binary = self._binarize(gray)
            strips = self._find_row_strips(gray, binary)
            clean  = self._remove_grid_lines(binary)
            for y1, y2 in strips:
                self._process_strip_fallback(img, clean, binary, y1, y2, result)

        # 9-hole flag
        if 0 < len(result["pars"]) <= 10:
            result["nine_hole_card"] = True

        self._validate(result)
        self._score_confidence(result)
        return result

    # ── PAR row detection ────────────────────────────────────────────────────

    def _process_par_row(self, img: np.ndarray, result: dict) -> bool:
        """
        Find rows whose pixels match the standard PAR-row green (#dff0d8).
        Tight colour gate: G-R≥8, G-B≥15, R<235 — excludes near-white card
        backgrounds (including the slightly greenish #eef2f0 variant).
        Image must already be deskewed before calling this.
        """
        h, w = img.shape[:2]
        R = img[:, :, 0].astype(np.int16)
        G = img[:, :, 1].astype(np.int16)
        B = img[:, :, 2].astype(np.int16)

        mask = (
            (G >= 210) & (G <= 255) &
            (R >= 180) & (R <= 234) &
            (B >= 175) & (B <= 246) &
            (G - R >= 8) &
            (G - B >= 15)
        )
        cov = mask.sum(axis=1) / w

        par_ys = np.where(cov > 0.15)[0]
        if not len(par_ys):
            return False

        groups = self._cluster_rows(par_ys, gap=15)
        found  = False

        for y1, y2 in groups:
            strip_rgb = img[y1:y2 + 1, :]

            # Cell-based OCR: split strip at vertical separators, OCR each cell.
            # Preserves hole positions — None means OCR failed for that cell.
            pars_cell = self._ocr_par_cells(strip_rgb)  # list[int|None]

            # Token-based OCR: PSM 11 / PSM 7 full-strip fallback.
            # Better on 9-hole or thin strips where separator detection fails.
            pars_token = self._parse_par_tokens(
                self._ocr_strip_tokens(strip_rgb, invert=False)
            )

            # Count valid (non-None) values for comparison
            cell_valid  = sum(1 for v in pars_cell if v is not None)
            token_valid = len(pars_token)

            if cell_valid >= token_valid and cell_valid >= 7:
                # Use positional list; trailing Nones already stripped
                pars: list[int | None] = pars_cell[:18]
            elif token_valid >= 7:
                pars = pars_token[:18]  # type: ignore[assignment]
            else:
                continue

            n_valid = sum(1 for v in pars if v is not None)
            best    = sum(1 for v in result["pars"] if v is not None) if result["pars"] else 0
            if n_valid > best:
                result["pars"] = pars
                found = True
                # Stop after first green band that yields ≥9 valid values.
                # On layouts with separate men's/women's PAR rows (full_womens),
                # the men's row always appears first; accepting it prevents the
                # women's row from overwriting with a higher-coverage but wrong read.
                if n_valid >= 9:
                    break

        return found

    def _ocr_par_cells(self, strip_rgb: np.ndarray) -> list[int | None]:
        """
        Locate vertical column separators in the PAR strip, then OCR each
        hole cell individually with PSM 8 + whitelist '345'.

        Returns a positional list (int or None per detected hole cell).
        None means OCR failed for that cell — the position is preserved so
        callers can decide how to handle gaps.
        Returns [] if fewer than 9 separators are found (fall through to
        token-based OCR).
        """
        h, w = strip_rgb.shape[:2]
        gray = cv2.cvtColor(strip_rgb, cv2.COLOR_RGB2GRAY)
        _, bin_s = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        # Column dark-pixel fraction — separators are near-solid dark vertical lines
        col_dark = (255 - bin_s).astype(np.float32).sum(axis=0) / (255.0 * h)

        groups: list[int] = []
        for thresh in (0.5, 0.35, 0.2):
            sep_xs = np.where(col_dark > thresh)[0]
            if not len(sep_xs):
                continue
            grp = [int(sep_xs[0])]
            groups = []
            for x in sep_xs[1:]:
                x = int(x)
                if x - grp[-1] <= 8:
                    grp.append(x)
                else:
                    groups.append(int(sum(grp) / len(grp)))
                    grp = [x]
            groups.append(int(sum(grp) / len(grp)))
            if len(groups) >= 9:
                break

        if len(groups) < 9:
            return []

        boundaries = [0] + groups + [w]
        cells      = [(boundaries[i], boundaries[i + 1])
                      for i in range(len(boundaries) - 1)]
        spacings   = [x2 - x1 for x1, x2 in cells]
        median_w   = sorted(spacings)[len(spacings) // 2]
        lo, hi     = 0.5 * median_w, 1.5 * median_w
        hole_cells = [(x1, x2) for x1, x2 in cells if lo <= (x2 - x1) <= hi]

        if len(hole_cells) < 9:
            return []

        # 9-hole: 9 holes + OUT total = 10 cells (same width); 18-hole: 18+IN = 19.
        # Drop the trailing total cell to avoid reading "36" → "3" as a par value.
        if len(hole_cells) == 10:
            hole_cells = hole_cells[:9]
        elif len(hole_cells) == 19:
            hole_cells = hole_cells[:18]

        scale  = max(1.0, 80.0 / h)
        result: list[int | None] = []
        for x1, x2 in hole_cells:
            cell   = bin_s[:, x1:x2]
            cw     = max(1, int((x2 - x1) * scale))
            ch     = max(1, int(h * scale))
            cell_r = cv2.resize(cell, (cw, ch), interpolation=cv2.INTER_LANCZOS4)
            padded = cv2.copyMakeBorder(cell_r, 10, 10, 10, 10,
                                        cv2.BORDER_CONSTANT, value=255)
            result.append(self._ocr_single_par_cell(padded))

        # Drop trailing Nones from OUT/IN total columns that slipped through
        while result and result[-1] is None:
            result.pop()

        return result

    @staticmethod
    def _ocr_single_par_cell(padded: np.ndarray) -> int | None:
        """
        OCR a single pre-padded binary cell image, returning 3, 4, 5, or None.
        Tries three passes: PSM 8, PSM 10, then PSM 8 on a mildly dilated image.
        The dilation pass recovers digits that JPEG+rotation fragmented into
        characters that Tesseract reads as 'a' or similar noise.
        """
        _WL = "-c tessedit_char_whitelist=345"
        tries = [
            ("--psm 8 --oem 3 " + _WL,  padded),
            ("--psm 10 --oem 3 " + _WL, padded),
            ("--psm 8 --oem 3 " + _WL,  cv2.dilate(padded, np.ones((2, 2), np.uint8))),
        ]
        for cfg, img in tries:
            txt = pytesseract.image_to_string(img, config=cfg).strip()
            if txt in ("3", "4", "5"):
                return int(txt)
        return None

    # ── Tee row detection ────────────────────────────────────────────────────

    def _process_tee_rows(self, img: np.ndarray, result: dict):
        """
        Scan for rows whose background matches known tee colours.
        Each detected colour band → extract strip → OCR for label + yardages.
        """
        h, w = img.shape[:2]
        R = img[:, :, 0].astype(np.int16)
        G = img[:, :, 1].astype(np.int16)
        B = img[:, :, 2].astype(np.int16)

        for hint, rc, gc, bc, tol in _TEE_COLORS:
            mask = (
                (np.abs(R - rc) <= tol) &
                (np.abs(G - gc) <= tol) &
                (np.abs(B - bc) <= tol)
            )
            cov    = mask.sum(axis=1) / w
            tee_ys = np.where(cov > 0.12)[0]
            if not len(tee_ys):
                continue

            is_dark = (rc * 0.299 + gc * 0.587 + bc * 0.114) < 100

            for y1, y2 in self._cluster_rows(tee_ys, gap=20):
                strip_rgb = img[y1:y2 + 1, :]
                tokens    = self._ocr_strip_tokens(strip_rgb, invert=is_dark)
                self._parse_tee_tokens(tokens, result)

    # ── Strip OCR ─────────────────────────────────────────────────────────────

    def _ocr_strip_tokens(self, strip_rgb: np.ndarray, invert: bool = False) -> list[str]:
        """
        Downscale a row strip to TARGET_STRIP_W, binarise, run PSM 11.
        Returns a flat list of token strings (words), left-to-right by x position.
        PSM 11 (sparse text) handles wide thin strips much better than PSM 7.
        """
        h, w = strip_rgb.shape[:2]
        # Clip back-panel / extra-page area: strip width ≤ h * MAX_STRIP_AR
        max_x   = min(w, max(1, h * self.MAX_STRIP_AR))
        strip   = strip_rgb[:, :max_x]

        gray    = cv2.cvtColor(strip, cv2.COLOR_RGB2GRAY)
        _, binimg = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        if invert:
            binimg = cv2.bitwise_not(binimg)

        sw = self.TARGET_STRIP_W
        sw = min(sw, max_x)                    # don't upscale tiny images
        sh = max(1, int(h * sw / max_x))
        scaled = cv2.resize(binimg, (sw, sh), interpolation=cv2.INTER_LANCZOS4)

        pad = 10
        img_pad = cv2.copyMakeBorder(scaled, pad, pad, pad, pad,
                                     cv2.BORDER_CONSTANT, value=255)

        # Run both PSM 11 (sparse) and PSM 7 (single line) and pick the richer result.
        # PSM 11 handles wide 18-hole double-section rows; PSM 7 is better for
        # 9-hole single-section rows at the same scaled dimensions.
        def _from_psm11(img_p):
            d = pytesseract.image_to_data(
                img_p, config=self._CFG_PSM11,
                output_type=pytesseract.Output.DICT,
            )
            ws = [
                (d["left"][i], d["text"][i].strip())
                for i in range(len(d["text"]))
                if d["text"][i].strip()
                and int(d["conf"][i]) > 10
                and any(c.isalnum() for c in d["text"][i])
            ]
            ws.sort(key=lambda x: x[0])
            return [w[1] for w in ws]

        def _from_psm7(img_p):
            raw = pytesseract.image_to_string(img_p, config=self._CFG_PSM7).strip()
            return [t for t in raw.replace("|", " ").split()
                    if any(c.isalnum() for c in t)]

        tokens11 = _from_psm11(img_pad)
        tokens7  = _from_psm7(img_pad)

        # Pick the token list that yields more numeric-looking tokens
        def _num_count(toks):
            return sum(1 for t in toks if re.match(r"^\d+$", t))

        tokens = tokens11 if _num_count(tokens11) >= _num_count(tokens7) else tokens7
        return tokens

    # ── Token parsers ─────────────────────────────────────────────────────────

    def _parse_par_tokens(self, tokens: list[str]) -> list[int]:
        """Extract par values {3,4,5} from a PAR-row token list."""
        values = []
        for tok in tokens:
            n = _to_int(tok)
            if n in (3, 4, 5):
                values.append(n)
        return values

    def _parse_tee_tokens(self, tokens: list[str], result: dict):
        """
        From a tee-row token list, identify the label and yardage values.
        Label = first alpha cluster; yardages = values 80–650.
        """
        if not tokens:
            return

        label_parts: list[str] = []
        nums:        list[int]  = []
        hit_num = False
        for tok in tokens:
            if not hit_num and re.match(r"^[A-Za-z'/ -]+$", tok):
                label_parts.append(tok)
            else:
                hit_num = True
                n = _to_int(tok)
                if n is not None:
                    nums.append(n)

        label  = " ".join(label_parts).strip()
        if not label:
            return

        yards = [v for v in nums if 80 <= v <= 650]
        if len(yards) < 7:
            return

        color    = normalize_tee_color(label)
        existing = next(
            (t for t in result["tee_boxes"] if t["label"].lower() == label.lower()),
            None,
        )

        if existing:
            if len(yards) > len(existing.get("yardages") or []):
                existing["yardages"] = yards[:18]
        else:
            tee = {"label": label, "color": color,
                   "rating": None, "slope": None, "yardages": yards[:18]}
            result["tee_boxes"].append(tee)

        # Inline rating/slope (e.g. "73.4/129" on the label row)
        tee_entry = existing or result["tee_boxes"][-1]
        full_text = " ".join(tokens)
        m = self._RATE_RE.search(full_text)
        if m and tee_entry["rating"] is None:
            tee_entry["rating"] = float(m.group(1))
            tee_entry["slope"]  = int(m.group(2))

    # ── Fallback: strip-based scan ────────────────────────────────────────────

    def _process_strip_fallback(
        self,
        img_rgb: np.ndarray,
        clean: np.ndarray,
        binary: np.ndarray,
        y1: int,
        y2: int,
        result: dict,
    ):
        """
        OCR a detected binary row strip in both polarities.
        Used when colour detection fails (e.g. non-standard PAR row colour).
        """
        strip_rgb = img_rgb[y1:y2 + 1, :]
        tokens_n  = self._ocr_strip_tokens(strip_rgb, invert=False)
        tokens_i  = self._ocr_strip_tokens(strip_rgb, invert=True)

        for tokens, supplement in [(tokens_n, False), (tokens_i, True)]:
            self._parse_fallback_row(tokens, result, supplement)

    def _parse_fallback_row(self, tokens: list[str], result: dict, supplement: bool):
        if not tokens or self._SKIP_RE.search(" ".join(tokens)):
            return

        label_parts: list[str] = []
        nums: list[int] = []
        hit_num = False
        for tok in tokens:
            if not hit_num and re.match(r"^[A-Za-z'/ -]+$", tok):
                label_parts.append(tok)
            else:
                hit_num = True
                n = _to_int(tok)
                if n is not None:
                    nums.append(n)

        label = " ".join(label_parts).strip()

        is_par = bool(self._PAR_RE.search(label)) or bool(self._PAR_RE.search(" ".join(tokens[:3])))
        is_hcp = bool(self._HCP_RE.search(label))

        if is_par:
            valid = [v for v in nums if v in (3, 4, 5)]
            if len(valid) >= 7 and (not supplement or len(valid) > len(result["pars"])):
                result["pars"] = valid[:18]
            return

        # Unlabelled heuristic: ≥8 values, >75 % are {3,4,5}
        valid_p = [v for v in nums if v in (3, 4, 5)]
        if (not result["pars"] and not is_hcp
                and len(valid_p) >= 8
                and len(valid_p) / max(len(nums), 1) > 0.75):
            result["pars"] = valid_p[:18]
            return

        if is_hcp:
            valid = [v for v in nums if 1 <= v <= 18]
            if len(valid) >= 7 and not supplement:
                result["handicaps"] = valid[:18]
            return

        yards = [v for v in nums if 80 <= v <= 650]
        if len(yards) < 7 or not label:
            return

        color    = normalize_tee_color(label)
        existing = next(
            (t for t in result["tee_boxes"] if t["label"].lower() == label.lower()),
            None,
        )
        if supplement and existing:
            if len(yards) > len(existing.get("yardages") or []):
                existing["yardages"] = yards[:18]
            return

        tee = existing or {
            "label": label, "color": color,
            "rating": None, "slope": None, "yardages": [],
        }
        if not existing:
            result["tee_boxes"].append(tee)
        tee["yardages"] = yards[:18]

        full_text = " ".join(tokens)
        m = self._RATE_RE.search(full_text)
        if m and tee["rating"] is None:
            tee["rating"] = float(m.group(1))
            tee["slope"]  = int(m.group(2))

    # ── Row strip detection (fallback) ────────────────────────────────────────

    def _find_row_strips(self, gray: np.ndarray, binary: np.ndarray) -> list[tuple[int, int]]:
        h, w = gray.shape
        _, gray_inv = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)
        bin_inv     = cv2.bitwise_not(binary)
        combined    = cv2.add(gray_inv, bin_inv)
        hk = cv2.getStructuringElement(cv2.MORPH_RECT, (max(50, w // 10), 1))
        hl = cv2.morphologyEx(combined, cv2.MORPH_OPEN, hk)
        proj   = np.sum(hl, axis=1) / 255
        min_px = w * 0.12
        raw_ys = [y for y in range(h) if proj[y] > min_px]
        if len(raw_ys) < 4:
            return []
        bounds = self._cluster(raw_ys, gap=5)
        return [
            (bounds[i] + 1, bounds[i + 1] - 1)
            for i in range(len(bounds) - 1)
            if bounds[i + 1] - bounds[i] >= 8
        ]

    # ── Image helpers ─────────────────────────────────────────────────────────

    @staticmethod
    def _detect_skew(gray: np.ndarray) -> float:
        """Return the skew angle (degrees) via Hough line analysis."""
        try:
            edges = cv2.Canny(gray, 50, 150, apertureSize=3)
            lines = cv2.HoughLines(edges, 1, math.pi / 180, threshold=150)
            if lines is None:
                return 0.0
            angles = []
            for line in lines[:30]:
                rho, theta = line[0]
                angle = math.degrees(theta) - 90
                if abs(angle) < 20:
                    angles.append(angle)
            if not angles:
                return 0.0
            return float(sorted(angles)[len(angles) // 2])
        except Exception:
            return 0.0

    @staticmethod
    def _rotate_rgb(img_rgb: np.ndarray, angle: float) -> np.ndarray:
        h, w = img_rgb.shape[:2]
        M = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
        return cv2.warpAffine(img_rgb, M, (w, h),
                              flags=cv2.INTER_LINEAR,
                              borderMode=cv2.BORDER_REPLICATE)

    @staticmethod
    def _binarize(gray: np.ndarray) -> np.ndarray:
        _, b = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        return b

    @staticmethod
    def _remove_grid_lines(binary: np.ndarray) -> np.ndarray:
        h, w  = binary.shape
        inv   = cv2.bitwise_not(binary)
        hk    = cv2.getStructuringElement(cv2.MORPH_RECT, (max(60, w // 12), 1))
        vk    = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(25, h // 15)))
        grid  = cv2.dilate(
            cv2.add(cv2.morphologyEx(inv, cv2.MORPH_OPEN, hk),
                    cv2.morphologyEx(inv, cv2.MORPH_OPEN, vk)),
            np.ones((1, 2), np.uint8),
        )
        return cv2.bitwise_not(cv2.subtract(inv, grid))

    # ── Utility ───────────────────────────────────────────────────────────────

    @staticmethod
    def _cluster_rows(ys: np.ndarray, gap: int = 15) -> list[tuple[int, int]]:
        groups: list[tuple[int, int]] = []
        grp = [int(ys[0])]
        for y in ys[1:]:
            y = int(y)
            if y - grp[-1] <= gap:
                grp.append(y)
            else:
                groups.append((grp[0], grp[-1]))
                grp = [y]
        groups.append((grp[0], grp[-1]))
        return groups

    @staticmethod
    def _cluster(positions: list[int], gap: int = 5) -> list[int]:
        if not positions:
            return []
        clusters, group = [], [positions[0]]
        for p in positions[1:]:
            if p - group[-1] <= gap:
                group.append(p)
            else:
                clusters.append(int(sum(group) / len(group)))
                group = [p]
        clusters.append(int(sum(group) / len(group)))
        return clusters

    def _extract_course_name(self, text: str, result: dict):
        lines = [l.strip() for l in text.splitlines() if len(l.strip()) > 3]
        name_lines = [
            l for l in lines
            if not re.match(r"^\d", l)
            and sum(c.isalpha() for c in l) > len(l) * 0.4
        ]
        if name_lines and not result["course_name"]:
            result["course_name"] = name_lines[0]
        if len(name_lines) >= 2 and not result["club_name"]:
            result["club_name"] = name_lines[1]

    # ── Output schema ─────────────────────────────────────────────────────────

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
            w.append("No par values extracted — try better lighting or a flatter angle")
        else:
            bad = [i + 1 for i, p in enumerate(pars) if p is not None and p not in (3, 4, 5)]
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
            "overall":  round(0.5 * pc + 0.3 * yc + 0.2 * rc, 2),
            "pars":     round(pc, 2),
            "ratings":  round(rc, 2),
            "yardages": round(yc, 2),
        }
