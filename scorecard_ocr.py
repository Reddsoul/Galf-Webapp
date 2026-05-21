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

_NUM_FIX = str.maketrans({
    'O': '0', 'o': '0',
    'l': '1', 'I': '1', '|': '1',
    'S': '5', 's': '5',
    'B': '8', 'b': '6',
    'G': '6', 'g': '0',
    'q': '4',
    'D': '0', 'd': '0',
    'Z': '2', 'z': '2',
})

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
    cleaned = re.sub(r"[^0-9OolISsBbGgqDdZz|]", "", str(s))
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

    # Max aspect ratio for a strip.  Wide scorecards (front+back 9 side-by-side)
    # span >100× the row height; 200 covers any realistic scorecard layout.
    MAX_STRIP_AR = 200

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
        # Always run so tees without a distinctive background colour (e.g. white
        # tees on a white card) are still captured via text detection.
        # Deduplication inside _parse_fallback_row ensures colour-detected data
        # is never overwritten by worse binary-OCR data.
        binary = self._binarize(gray)
        strips = self._find_row_strips(gray, binary)
        clean  = self._remove_grid_lines(binary)
        for y1, y2 in strips:
            self._process_strip_fallback(img, clean, binary, y1, y2, result, par_found=par_found)

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

        # Standard scorecard column layout (after label column filtered by width):
        #   9-hole:  [h1..h9, OUT]             = 10 cells
        #   18-hole: [h1..h9, OUT, h10..h18]   = 19 cells  (no IN detected)
        #   18-hole: [h1..h9, OUT, h10..h18, IN] = 20 cells (both totals present)
        # The OUT column sits between h9 and h10 (position 9, 0-based).
        # Whitelist "345" caused OUT total "37" to read as "3"; whitelist is now
        # "0123456789" so totals read as multi-digit and are rejected by the caller.
        # Structural fix: skip OUT at position 9 (and IN at 19) explicitly.
        if len(hole_cells) == 10:
            hole_cells = hole_cells[:9]          # 9-hole + OUT → keep 9
        elif len(hole_cells) == 19:
            hole_cells = hole_cells[:9] + hole_cells[10:]      # 18-hole + OUT
        elif len(hole_cells) == 20:
            hole_cells = hole_cells[:9] + hole_cells[10:19]    # 18-hole + OUT + IN
        elif len(hole_cells) == 21:
            # Label column passed width filter: [label, h1..h9, OUT, h10..h18, IN]
            hole_cells = hole_cells[1:10] + hole_cells[11:20]
        elif len(hole_cells) > 21:
            # Unexpected extra columns — best effort
            hole_cells = hole_cells[:9] + hole_cells[10:19]

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

        Uses full digit whitelist so OUT/IN totals (e.g. "37") read as multi-digit
        numbers and are rejected by the `if txt in ("3","4","5")` check, rather than
        reading as "3" under the old narrow whitelist.
        """
        _WL = "-c tessedit_char_whitelist=0123456789"
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

    # ── Yardage cell OCR ──────────────────────────────────────────────────────

    def _ocr_yardage_cells(self, strip_rgb: np.ndarray,
                            invert: bool = False) -> list[int | None]:
        """
        Cell-based OCR for a tee-row yardage strip.

        Light strips (invert=False): column separators are dark vertical lines →
          find HIGH col_dark positions, treat as separator positions, cells are
          the spaces between consecutive separators.

        Dark strips (invert=True): after inversion, number characters are dark
          while background is white. Separator lines are also white (not dark).
          Strategy: find number-column CENTERS (high col_dark after inversion),
          then derive cell boundaries as midpoints between consecutive centers.
          This correctly handles dark tee rows where separators are not detectable.

        Blurry images are handled by smoothing col_dark before thresholding and
        using a larger group-merge gap (15 px instead of 8 px).
        """
        h, w = strip_rgb.shape[:2]
        gray = cv2.cvtColor(strip_rgb, cv2.COLOR_RGB2GRAY)
        _, bin_s = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        if invert:
            bin_s = cv2.bitwise_not(bin_s)

        col_dark = (255 - bin_s).astype(np.float32).sum(axis=0) / (255.0 * h)

        # Smooth to merge blurred/wide separator pixels into a single peak.
        # Kernel ≈ 3% of strip height, capped so it doesn't swallow narrow cells.
        k = min(max(3, h // 15), 21)
        if k % 2 == 0:
            k += 1
        col_dark_sm = np.convolve(col_dark, np.ones(k) / k, mode='same')

        # Larger merge gap handles separators blurred wider than 8 px.
        MERGE_GAP = 15

        if not invert:
            # ── Light strip: find dark separator lines (high col_dark) ──────────
            groups: list[int] = []
            for thresh in (0.5, 0.35, 0.2):
                sep_xs = np.where(col_dark_sm > thresh)[0]
                if not len(sep_xs):
                    continue
                grp = [int(sep_xs[0])]
                groups = []
                for x in sep_xs[1:]:
                    x = int(x)
                    if x - grp[-1] <= MERGE_GAP:
                        grp.append(x)
                    else:
                        groups.append(int(sum(grp) / len(grp)))
                        grp = [x]
                groups.append(int(sum(grp) / len(grp)))
                if len(groups) >= 9:
                    break

            if len(groups) < 9:
                return []

            # Cells = spaces between consecutive separators
            boundaries = [0] + groups + [w]
            cells = [(boundaries[i], boundaries[i + 1])
                     for i in range(len(boundaries) - 1)]
            spacings  = [x2 - x1 for x1, x2 in cells]
            median_w  = sorted(spacings)[len(spacings) // 2]
            lo, hi    = 0.5 * median_w, 1.8 * median_w
            hole_cells = [(x1, x2) for x1, x2 in cells if lo <= (x2 - x1) <= hi]

        else:
            # ── Dark strip (inverted): find number-column centers ────────────────
            # After inversion: digit pixels are dark → high col_dark.
            # Background and separator gaps → low col_dark (~0).
            # We find the clusters of dark pixels (= number columns) and put
            # cell boundaries at the midpoints between consecutive clusters.
            num_xs = np.where(col_dark_sm > 0.03)[0]
            if not len(num_xs):
                return []

            # Cluster number pixels; merge gap = 2.5% of total width (handles
            # wide numbers and the space within a multi-digit group like "420").
            merge_num = max(MERGE_GAP, w // 40)
            grp_n = [int(num_xs[0])]
            num_cols: list[int] = []          # center of each number column
            for x in num_xs[1:]:
                x = int(x)
                if x - grp_n[-1] <= merge_num:
                    grp_n.append(x)
                else:
                    num_cols.append(int(sum(grp_n) / len(grp_n)))
                    grp_n = [x]
            num_cols.append(int(sum(grp_n) / len(grp_n)))

            if len(num_cols) < 9:
                return []

            # Build cells centered on each number column.
            # Boundary = midpoint between consecutive column centers.
            boundaries = [0]
            for i in range(len(num_cols) - 1):
                boundaries.append((num_cols[i] + num_cols[i + 1]) // 2)
            boundaries.append(w)
            cells = [(boundaries[i], boundaries[i + 1])
                     for i in range(len(boundaries) - 1)]

            # Filter to keep only cells whose width matches the typical hole column.
            # The label column (leftmost, wider) and total columns are removed here.
            spacings  = [x2 - x1 for x1, x2 in cells]
            median_w  = sorted(spacings)[len(spacings) // 2]
            lo, hi    = 0.4 * median_w, 2.2 * median_w
            hole_cells = [(x1, x2) for x1, x2 in cells if lo <= (x2 - x1) <= hi]

        if len(hole_cells) < 9:
            return []

        if len(hole_cells) == 10:
            hole_cells = hole_cells[:9]
        elif len(hole_cells) >= 19:
            hole_cells = hole_cells[:18]

        scale = min(max(1.0, 80.0 / h), 8.0)  # cap: avoid absurd upscale for thin strips
        result: list[int | None] = []
        for x1, x2 in hole_cells:
            padded = self._prep_yardage_cell(bin_s, x1, x2, h, scale)
            val = self._ocr_single_yardage_cell(padded)
            if val is None:
                margin = max(2, (x2 - x1) // 10)
                x1e = max(0, x1 - margin)
                x2e = min(w, x2 + margin)
                padded2 = self._prep_yardage_cell(bin_s, x1e, x2e, h, scale)
                val = self._ocr_single_yardage_cell(padded2)
            result.append(val)

        while result and result[-1] is None:
            result.pop()
        return result

    @staticmethod
    def _prep_yardage_cell(bin_s: np.ndarray, x1: int, x2: int,
                            h: int, scale: float) -> np.ndarray:
        cell = bin_s[:, x1:x2]
        cw = max(1, int((x2 - x1) * scale))
        ch = max(1, int(h * scale))
        cell_r = cv2.resize(cell, (cw, ch), interpolation=cv2.INTER_LANCZOS4)
        return cv2.copyMakeBorder(cell_r, 10, 10, 10, 10,
                                  cv2.BORDER_CONSTANT, value=255)

    @staticmethod
    def _ocr_single_yardage_cell(padded: np.ndarray) -> int | None:
        """
        OCR one yardage cell; returns int in 80–650 or None.
        Digit-only whitelist prevents noise chars from corrupting 3-digit reads.
        Three passes: PSM 8, PSM 10, PSM 8 on dilated image.
        """
        _WL = "-c tessedit_char_whitelist=0123456789"
        tries = [
            ("--psm 8 --oem 3 " + _WL,  padded),
            ("--psm 10 --oem 3 " + _WL, padded),
            ("--psm 8 --oem 3 " + _WL,
             cv2.dilate(padded, np.ones((2, 2), np.uint8))),
        ]
        for cfg, img in tries:
            txt = pytesseract.image_to_string(img, config=cfg).strip()
            try:
                n = int(txt)
                if 80 <= n <= 650:
                    return n
            except (ValueError, TypeError):
                pass
        return None

    @staticmethod
    def _validate_yardage_sum(yards: list[int], n_holes: int) -> bool:
        """True if the total is a plausible yardage for the given hole count."""
        if len(yards) < n_holes:
            return True  # incomplete — can't rule it out
        total = sum(yards[:n_holes])
        if n_holes == 9:
            return 1200 <= total <= 4500
        if n_holes == 18:
            return 4500 <= total <= 8500
        return True

    # ── Tee label extraction ──────────────────────────────────────────────────

    # Width of the label column to read (pixels in original image).
    # The tee color name (e.g. "Gold", "Blue") always appears in the leftmost
    # column of the row.  Reading only this portion at higher magnification
    # avoids the resolution loss from downscaling the full wide strip.
    _LABEL_COL_PX = 700

    def _ocr_tee_label(self, strip_rgb: np.ndarray, invert: bool) -> str | None:
        """
        Read just the leftmost _LABEL_COL_PX pixels of a tee row to extract
        the tee colour name at a higher effective resolution than the full-strip
        scan provides.  Returns the normalised colour string or None.
        """
        h, w = strip_rgb.shape[:2]
        label_w = min(w, self._LABEL_COL_PX)
        label_strip = strip_rgb[:, :label_w]

        gray = cv2.cvtColor(label_strip, cv2.COLOR_RGB2GRAY)
        _, bin_l = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        if invert:
            bin_l = cv2.bitwise_not(bin_l)

        # Scale so the label strip is at least 300 px wide (guarantees ≥40 px chars)
        target_w = max(300, min(label_w * 3, 900))
        target_h = max(1, int(h * target_w / label_w))
        scaled = cv2.resize(bin_l, (target_w, target_h), interpolation=cv2.INTER_LANCZOS4)
        padded = cv2.copyMakeBorder(scaled, 12, 12, 12, 12,
                                    cv2.BORDER_CONSTANT, value=255)

        for cfg in (self._CFG_PSM7, self._CFG_PSM11):
            raw = pytesseract.image_to_string(padded, config=cfg).strip()
            for word in raw.replace("|", " ").split():
                if re.match(r"^[1-9]$", word):
                    return word  # numeric tee label ("1", "2", "3")
                # Handle merged "1" + rating, e.g. "177.3/123" → label "1"
                m = re.match(r"^([1-9])\d{2}\.\d/\d{2,3}$", word)
                if m:
                    return m.group(1)
                if len(word) >= 3 and re.match(r"^[A-Za-z]+$", word):
                    color = normalize_tee_color(word)
                    if color:
                        return word
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
                strip_rgb  = img[y1:y2 + 1, :]
                # Cell-based path: highest yardage accuracy
                yards_cell = self._ocr_yardage_cells(strip_rgb, invert=is_dark)
                # Token path: provides label + inline rating/slope
                tokens     = self._ocr_strip_tokens(strip_rgb, invert=is_dark)
                cell_valid = sum(1 for v in yards_cell if v is not None)

                # If the token scan didn't find a label as the first word, try
                # a dedicated high-res label scan on just the left portion.
                label_from_tokens = self._first_label_token(tokens)
                if not label_from_tokens:
                    recovered = self._ocr_tee_label(strip_rgb, is_dark)
                    if recovered:
                        tokens = [recovered] + tokens

                self._parse_tee_tokens(
                    tokens, result,
                    yards_override=yards_cell if cell_valid >= 7 else None,
                    hint_color=hint,
                )

    # ── Strip OCR ─────────────────────────────────────────────────────────────

    # Maximum pixels per OCR section. Keeps character resolution high enough
    # that Tesseract reads 3-digit numbers reliably regardless of strip height.
    _SECTION_W = 3000

    def _ocr_strip_tokens(self, strip_rgb: np.ndarray, invert: bool = False) -> list[str]:
        """
        OCR a row strip and return tokens left-to-right by x position.

        Wide strips are scanned in _SECTION_W-px sections so that each section
        is rendered at a resolution where individual characters are ≥20 px tall,
        rather than being squashed to unreadable size in one global downscale.

        The first section always covers the label column (tee color name).
        Subsequent sections cover the yardage columns.
        """
        h, w = strip_rgb.shape[:2]
        max_x = min(w, max(1, h * self.MAX_STRIP_AR))

        gray   = cv2.cvtColor(strip_rgb[:, :max_x], cv2.COLOR_RGB2GRAY)
        _, binimg = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        if invert:
            binimg = cv2.bitwise_not(binimg)

        def _tokens_from_section(section: np.ndarray, x_offset: int,
                                  scale: float) -> list[tuple[int, str]]:
            """OCR one horizontal section; return (global_x, token) pairs."""
            sw = max(1, int(section.shape[1] * scale))
            sh = max(1, int(section.shape[0] * scale))
            scaled = cv2.resize(section, (sw, sh), interpolation=cv2.INTER_LANCZOS4)
            pad = 10
            img_p = cv2.copyMakeBorder(scaled, pad, pad, pad, pad,
                                       cv2.BORDER_CONSTANT, value=255)

            d = pytesseract.image_to_data(
                img_p, config=self._CFG_PSM11,
                output_type=pytesseract.Output.DICT,
            )
            results = []
            for i in range(len(d["text"])):
                tok = d["text"][i].strip()
                if not tok or int(d["conf"][i]) <= 10:
                    continue
                if not any(c.isalnum() for c in tok):
                    continue
                local_x = max(0, d["left"][i] - pad)
                global_x = x_offset + int(local_x / scale)
                results.append((global_x, tok))
            return results

        all_pairs: list[tuple[int, str]] = []

        if max_x <= self._SECTION_W:
            # Single section: scale to TARGET_STRIP_W (existing behaviour).
            scale = min(1.0, self.TARGET_STRIP_W / max_x)
            all_pairs = _tokens_from_section(binimg[:, :max_x], 0, scale)

            # PSM 7 fallback for narrow / 9-hole strips
            if not all_pairs:
                sw2 = max(1, int(max_x * scale))
                sh2 = max(1, int(h * scale))
                sc2 = cv2.resize(binimg, (sw2, sh2), interpolation=cv2.INTER_LANCZOS4)
                p2 = cv2.copyMakeBorder(sc2, 10, 10, 10, 10,
                                        cv2.BORDER_CONSTANT, value=255)
                raw = pytesseract.image_to_string(p2, config=self._CFG_PSM7).strip()
                toks = [t for t in raw.replace("|", " ").split()
                        if any(c.isalnum() for c in t)]
                all_pairs = list(enumerate(toks))
        else:
            # Multi-section scan.  Each section is _SECTION_W px wide in the
            # original image.  We scale each section to the same _SECTION_W
            # output pixels so the effective resolution stays constant.
            scale = self._SECTION_W / self._SECTION_W  # always 1.0 per section
            x = 0
            while x < max_x:
                x_end = min(x + self._SECTION_W, max_x)
                section = binimg[:, x:x_end]
                # Scale so the section is rendered at TARGET_STRIP_W if it's
                # narrower (e.g. the final partial section).
                sec_w = x_end - x
                sec_scale = min(1.0, self.TARGET_STRIP_W / sec_w)
                all_pairs.extend(_tokens_from_section(section, x, sec_scale))
                x = x_end

        all_pairs.sort(key=lambda p: p[0])

        def _num_count(pairs):
            return sum(1 for _, t in pairs if re.match(r"^\d+$", t))

        # If the positional scan found very few numbers, try a single-line PSM 7
        # fallback on the full (downscaled) strip — better for thin strips.
        if _num_count(all_pairs) < 5 and max_x <= self._SECTION_W:
            scale_fb = min(1.0, self.TARGET_STRIP_W / max_x)
            sw_fb = max(1, int(max_x * scale_fb))
            sh_fb = max(1, int(h * scale_fb))
            sc_fb = cv2.resize(binimg[:, :max_x], (sw_fb, sh_fb),
                               interpolation=cv2.INTER_LANCZOS4)
            p_fb = cv2.copyMakeBorder(sc_fb, 10, 10, 10, 10,
                                      cv2.BORDER_CONSTANT, value=255)
            raw = pytesseract.image_to_string(p_fb, config=self._CFG_PSM7).strip()
            toks7 = [t for t in raw.replace("|", " ").split()
                     if any(c.isalnum() for c in t)]
            if _num_count(enumerate(toks7)) > _num_count(all_pairs):
                return toks7

        return [t for _, t in all_pairs]

    # ── Token parsers ─────────────────────────────────────────────────────────

    @staticmethod
    def _first_label_token(tokens: list[str]) -> str | None:
        """Return the first purely-alpha token, or None if tokens start with a number."""
        for tok in tokens[:4]:
            if re.match(r"^[A-Za-z]+$", tok) and len(tok) >= 3:
                return tok
        return None

    def _parse_par_tokens(self, tokens: list[str]) -> list[int]:
        """Extract par values {3,4,5} from a PAR-row token list."""
        values = []
        for tok in tokens:
            n = _to_int(tok)
            if n in (3, 4, 5):
                values.append(n)
        return values

    def _parse_tee_tokens(self, tokens: list[str], result: dict,
                          yards_override: list[int | None] | None = None,
                          hint_color: str | None = None):
        """
        From a tee-row token list, identify the label and yardage values.
        Label = first alpha cluster; yardages = values 80–650.
        yards_override: pre-computed cell-based yardages (higher accuracy).
          If supplied and passes sum validation, token-derived yardages are skipped.
          Falls back to token yardages if override fails validation.
        hint_color: canonical colour name from the colour-mask detection pass.
          Used as label fallback when the token stream has no alpha prefix.
        """
        if not tokens and hint_color is None:
            return

        label_parts: list[str] = []
        nums:        list[int]  = []
        hit_num = False
        for tok in (tokens or []):
            if not hit_num and re.match(r"^[A-Za-z'/\- ]+$", tok):
                label_parts.append(tok)
            elif not hit_num and self._RATE_RE.search(tok):
                # Rating/slope token before the label — skip without locking label scan
                continue
            else:
                hit_num = True
                n = _to_int(tok)
                if n is not None:
                    nums.append(n)

        label = " ".join(label_parts).strip()

        # If no alpha label found in tokens, fall back to the colour-mask hint.
        if not label and hint_color:
            label = hint_color

        if not label:
            return

        if yards_override is not None:
            yards = [v for v in yards_override if v is not None]
        else:
            yards = [v for v in nums if 80 <= v <= 650]

        if len(yards) < 7:
            return

        n_holes = 18 if len(yards) >= 15 else 9
        if not self._validate_yardage_sum(yards, n_holes):
            if yards_override is not None:
                # Cell OCR sum invalid — fall back to token yardages
                yards = [v for v in nums if 80 <= v <= 650]
                n_holes = 18 if len(yards) >= 15 else 9
                if len(yards) < 7 or not self._validate_yardage_sum(yards, n_holes):
                    return
            else:
                return

        color = normalize_tee_color(label) or hint_color
        # Match against existing tee by label OR colour (handles OCR label noise)
        existing = next(
            (t for t in result["tee_boxes"]
             if t["label"].lower() == label.lower()
             or (color and (t.get("color") or "").lower() == color.lower())),
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
        full_text = " ".join(tokens or [])
        m = self._RATE_RE.search(full_text)
        if m and tee_entry["rating"] is None:
            tee_entry["rating"] = float(m.group(1))
            tee_entry["slope"]  = int(m.group(2))

    # ── Fallback: strip-based scan ────────────────────────────────────────────

    def _inject_label_if_missing(
        self,
        tokens: list[str],
        strip_rgb: np.ndarray,
        invert: bool,
    ) -> list[str]:
        """
        If the token stream contains a rating token and yardage numbers but no
        recognisable label, OCR the label column at higher resolution to recover
        a numeric ("1"/"2"/"3") or colour-name label.
        """
        if not tokens:
            return tokens
        # Already has an alpha or digit label in the first few tokens?
        # Require ≥3 chars to avoid short OCR noise like "ra", "lo", etc.
        has_alpha = any(
            re.match(r"^[A-Za-z]{3,}$", t) for t in tokens[:5]
        )
        has_digit = any(re.match(r"^[1-9]$", t) for t in tokens[:4])
        if has_alpha or has_digit:
            return tokens
        # Needs enough yardage-range numbers to look like a tee row.
        # Also accepts a rating token (e.g. "78.4/103") as confirmation.
        yard_count = sum(
            1 for t in tokens
            if (n := _to_int(t)) is not None and 80 <= n <= 650
        )
        has_rate = any(self._RATE_RE.search(t) for t in tokens[:8])
        if yard_count < 7 and not has_rate:
            return tokens
        if yard_count < 5:
            return tokens
        label = self._ocr_tee_label(strip_rgb, invert)
        if label:
            return [label] + tokens
        return tokens

    def _process_strip_fallback(
        self,
        img_rgb: np.ndarray,
        clean: np.ndarray,
        binary: np.ndarray,
        y1: int,
        y2: int,
        result: dict,
        par_found: bool = False,
    ):
        """
        OCR a detected binary row strip in both polarities.
        par_found: if True, par row already extracted via colour detection —
          skip re-extracting pars unless the fallback finds more valid values.
        """
        strip_rgb = img_rgb[y1:y2 + 1, :]
        tokens_n  = self._ocr_strip_tokens(strip_rgb, invert=False)
        tokens_i  = self._ocr_strip_tokens(strip_rgb, invert=True)

        for tokens, invert_flag, supplement in [
            (tokens_n, False, False),
            (tokens_i, True,  True),
        ]:
            tokens = self._inject_label_if_missing(tokens, strip_rgb, invert_flag)
            self._parse_fallback_row(tokens, result, supplement, par_found=par_found)

    def _parse_fallback_row(self, tokens: list[str], result: dict, supplement: bool,
                            par_found: bool = False):
        if not tokens:
            return
        # Only apply the skip filter to the label (first few alpha tokens).
        # Applying it to the full token string blocks tee rows that happen to
        # contain inline "rating" or "slope" text after the yardages.
        label_preview = " ".join(
            t for t in tokens[:6] if re.match(r"^[A-Za-z'/\- ]+$", t)
        )
        if self._SKIP_RE.search(label_preview):
            return

        label_parts: list[str] = []
        nums: list[int] = []
        hit_num = False
        for tok in tokens:
            if not hit_num and re.match(r"^[A-Za-z'/\- ]+$", tok):
                label_parts.append(tok)
            elif not hit_num and self._RATE_RE.search(tok):
                # Rating/slope token (e.g. "75.6/107") printed before the label
                # in some layouts — skip it without locking out the label.
                continue
            elif not hit_num and not label_parts and re.match(r"^[1-9]$", tok):
                # Single-digit numeric tee label ("1", "2", "3") injected by
                # _inject_label_if_missing or appearing naturally at token start.
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
            # When colour detection already found the PAR row (par_found=True),
            # don't let the fallback overwrite it.  Wide strips (MAX_STRIP_AR=200)
            # can pick up split OUT/IN totals (e.g. "37"→"3"+"7") which corrupt
            # the par sequence by inserting spurious {3,4,5} values.
            if par_found:
                return
            valid = [v for v in nums if v in (3, 4, 5)]
            if len(valid) >= 7:
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
            (t for t in result["tee_boxes"]
             if t["label"].lower() == label.lower()
             or (color
                 and (t.get("color") or "").lower() == color.lower()
                 # Only colour-deduplicate when the matched tee's label is a
                 # known colour alias (not a custom name like "Championship").
                 # This prevents merging two tees that share a mapped colour
                 # (e.g. Championship+Tournament both map to Black).
                 and (t.get("label") or "").lower() in
                     {"black","blue","white","red","gold","green",
                      "silver","yellow"})),
            None,
        )

        if existing:
            # Tee already found — only update yardages if this read has more holes.
            if len(yards) > len(existing.get("yardages") or []):
                existing["yardages"] = yards[:18]
            return

        # New tee not found by colour detection (e.g. white-background tee)
        if supplement:
            return  # only add new tees on the non-inverted pass to avoid duplicates
        tee = {"label": label, "color": color, "rating": None, "slope": None,
               "yardages": yards[:18]}
        result["tee_boxes"].append(tee)

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

        # Weights reflect priority: yardages > pars > ratings
        result["confidence"] = {
            "overall":  round(0.40 * yc + 0.35 * pc + 0.25 * rc, 2),
            "pars":     round(pc, 2),
            "ratings":  round(rc, 2),
            "yardages": round(yc, 2),
        }
