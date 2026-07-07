"""
Scorecard extraction via a LOCAL vision LLM.

Talks to any OpenAI-compatible chat endpoint — llama.cpp (llama-server),
Ollama, LM Studio — so the model runs entirely on your own hardware.
Stdlib only (urllib); Pillow used for downscaling when available.

Config (env vars)
-----------------
OCR_LLM_URL         Endpoint. Two formats supported, detected from the path:
                    - Ollama NATIVE (recommended): http://host:11434/api/chat
                      Lets us send keep_alive so the model is loaded ONLY for
                      the duration of a scan and unloaded right after —
                      zero RAM footprint between scans.
                    - OpenAI-compatible: http://host:PORT/v1/chat/completions
                      (llama.cpp llama-server, LM Studio, Ollama compat mode)
                    Default: http://127.0.0.1:11434/api/chat
OCR_LLM_MODEL       Model name. Default: "qwen2.5vl:3b"
OCR_LLM_TIMEOUT     Request timeout in seconds. Default: 180 (cold model
                    load + inference on modest hardware).
OCR_LLM_KEEP_ALIVE  Ollama native only. How long the model stays in RAM
                    after a scan. Default "0" = unload immediately.
                    Use e.g. "5m" while batch-scanning several cards.

Suggested models (running on a helper box, NOT the NAS):
  - qwen2.5vl:3b   (~3 GB RAM while loaded, best accuracy/size for tables)
  - moondream      (~1.7 GB, lighter, weaker on dense tables)
The app itself can run on a 1 GB NAS — the model RAM is only used on the
machine OCR_LLM_URL points at, and only while a scan is in flight.

Public interface mirrors ScorecardOCR:
    LLMScorecardOCR().process_image(image_bytes: bytes) -> dict
Raises RuntimeError when the endpoint is unreachable so the caller can fall
back to the Tesseract pipeline.
"""

import base64
import io
import json
import os
import re
import sys
import urllib.error
import urllib.request

DEFAULT_URL = "http://127.0.0.1:11434/api/chat"

_PROMPT = """You are reading a photo of a golf scorecard. Extract its data as JSON.

Return ONLY a JSON object, no prose, matching exactly this schema:
{
  "course_name": string or null,   // course name (e.g. "Lakeside Course"); null if absent
  "club_name": string or null,     // club/facility name if distinct from course name
  "nine_hole_card": boolean,       // true if the card covers only 9 holes
  "pars": [int, ...],              // par per hole in hole order (9 or 18 values, each 3-5)
  "handicaps": [int, ...],         // stroke index / HDCP per hole (1-18), [] if absent
  "tee_boxes": [
    {
      "label": string,             // tee name as printed (e.g. "Black", "Championship")
      "color": string or null,     // canonical color: Black/Blue/White/Yellow/Red/Gold/Green/Silver
      "rating": float or null,     // course rating (55.0-82.0)
      "slope": int or null,        // slope (55-155)
      "yardages": [int, ...]       // yards per hole in hole order (80-650 each), [] if unreadable
    }
  ]
}

Rules:
- Hole order: 1..9 then 10..18. Front and back nine are often separate tables — concatenate them.
- Do NOT include OUT/IN/TOT column values in pars, handicaps, or yardages.
- Ratings often appear as "71.4/128" (rating/slope) near the tee name or in a side table.
- If a value is unreadable, use null (or omit the hole from yardages only if the whole row is unreadable).
- Never invent values. Missing is better than wrong."""


class LLMScorecardOCR:

    def __init__(self):
        self.url = os.environ.get("OCR_LLM_URL", DEFAULT_URL)
        self.model = os.environ.get("OCR_LLM_MODEL", "qwen2.5vl:3b")
        self.timeout = int(os.environ.get("OCR_LLM_TIMEOUT", "180"))
        self.keep_alive = os.environ.get("OCR_LLM_KEEP_ALIVE", "0")
        # Ollama native API supports keep_alive (load model per scan,
        # unload right after). OpenAI-compatible servers do not.
        self.native_ollama = self.url.rstrip("/").endswith("/api/chat")

    # ── Public ────────────────────────────────────────────────────────────

    def process_image(self, image_bytes: bytes) -> dict:
        image_bytes, mime = self._downscale(image_bytes)
        b64 = base64.b64encode(image_bytes).decode("ascii")

        if self.native_ollama:
            payload = {
                "model": self.model,
                "stream": False,
                "keep_alive": self.keep_alive,
                "options": {"temperature": 0},
                "messages": [{
                    "role": "user",
                    "content": _PROMPT,
                    "images": [b64],
                }],
            }
        else:
            payload = {
                "model": self.model,
                "temperature": 0,
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": _PROMPT},
                        {"type": "image_url",
                         "image_url": {"url": f"data:{mime};base64,{b64}"}},
                    ],
                }],
            }
        req = urllib.request.Request(
            self.url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, OSError, TimeoutError) as e:
            raise RuntimeError(f"LLM endpoint unreachable ({self.url}): {e}")

        try:
            if self.native_ollama:
                text = body["message"]["content"]
            else:
                text = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            raise RuntimeError(f"Unexpected LLM response shape: {str(body)[:300]}")

        raw = self._parse_json_block(text)
        result = self._coerce(raw)
        self._validate(result)
        self._score_confidence(result)
        return result

    def available(self) -> bool:
        """Cheap reachability probe (models endpoint or bare origin)."""
        base = re.sub(r"/(chat/completions|api/chat)/?$", "", self.url)
        probe = base + "/models" if base.endswith("/v1") else base
        try:
            req = urllib.request.Request(probe, method="GET")
            with urllib.request.urlopen(req, timeout=3):
                return True
        except Exception:
            return False

    # ── Helpers ───────────────────────────────────────────────────────────

    @staticmethod
    def _downscale(image_bytes: bytes, long_side: int = 1536):
        """Resize to keep prompts small; pass through untouched if PIL missing."""
        try:
            from PIL import Image
        except ImportError:
            return image_bytes, "image/jpeg"
        try:
            img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        except Exception as e:
            raise ValueError(f"Could not decode image: {e}")
        w, h = img.size
        scale = long_side / max(w, h)
        if scale < 1:
            img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=88)
        return buf.getvalue(), "image/jpeg"

    @staticmethod
    def _parse_json_block(text: str) -> dict:
        """Extract first JSON object from model output (tolerates code fences)."""
        text = re.sub(r"^```(?:json)?|```$", "", text.strip(),
                      flags=re.MULTILINE).strip()
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end <= start:
            raise RuntimeError(f"LLM returned no JSON: {text[:200]}")
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError as e:
            raise RuntimeError(f"LLM returned invalid JSON: {e}")

    @staticmethod
    def _coerce(raw: dict) -> dict:
        """Force the model output into the schema the frontend expects."""
        def _int(v, lo, hi):
            try:
                n = int(v)
            except (TypeError, ValueError):
                return None
            return n if lo <= n <= hi else None

        def _float(v, lo, hi):
            try:
                f = float(v)
            except (TypeError, ValueError):
                return None
            return f if lo <= f <= hi else None

        pars = [p for p in (_int(v, 3, 6) for v in (raw.get("pars") or []))
                if p is not None][:18]
        hcps = [h for h in (_int(v, 1, 18) for v in (raw.get("handicaps") or []))
                if h is not None][:18]

        tee_boxes = []
        for t in (raw.get("tee_boxes") or []):
            if not isinstance(t, dict):
                continue
            label = str(t.get("label") or "").strip()
            color = str(t.get("color") or "").strip().capitalize() or None
            if color not in ("Black", "Blue", "White", "Yellow", "Red",
                             "Gold", "Green", "Silver"):
                color = None
            yardages = [y for y in (_int(v, 80, 650)
                                    for v in (t.get("yardages") or []))
                        if y is not None][:18]
            if not label and not color:
                continue
            tee_boxes.append({
                "label":    label or color,
                "color":    color,
                "rating":   _float(t.get("rating"), 55.0, 82.0),
                "slope":    _int(t.get("slope"), 55, 155),
                "yardages": yardages,
            })

        nine = bool(raw.get("nine_hole_card")) or (0 < len(pars) <= 9)
        return {
            "course_name":      (str(raw["course_name"]).strip()
                                 if raw.get("course_name") else None),
            "club_name":        (str(raw["club_name"]).strip()
                                 if raw.get("club_name") else None),
            "nine_hole_card":   nine,
            "multiple_courses": None,
            "tee_boxes":        tee_boxes,
            "pars":             pars,
            "handicaps":        hcps,
            "warnings":         [],
            "confidence":       {"overall": 0.0, "pars": 0.0,
                                 "ratings": 0.0, "yardages": 0.0},
        }

    # Same validation/confidence semantics as the Tesseract pipeline so the
    # frontend review screen behaves identically for both backends.

    @staticmethod
    def _validate(result: dict):
        w = result.setdefault("warnings", [])
        n = 9 if result.get("nine_hole_card") else 18
        pars = result.get("pars", [])
        if not pars:
            w.append("No par values extracted")
        elif len(pars) < n:
            w.append(f"Only {len(pars)}/{n} par values extracted")
        if result.get("nine_hole_card"):
            w.append("Card appears to be 9-hole only")
        for tee in result.get("tee_boxes", []):
            lbl = tee.get("label", "?")
            n_yards = len(tee.get("yardages") or [])
            if tee.get("rating") is None:
                w.append(f"No rating/slope for tee: {lbl}")
            if n_yards < n:
                w.append(f"Only {n_yards}/{n} yardages for tee: {lbl}")

    @staticmethod
    def _score_confidence(result: dict):
        n = 9 if result.get("nine_hole_card") else 18
        pars = result.get("pars", [])
        pc = min(1.0, len(pars) / n) if pars else 0.0
        tees = result.get("tee_boxes", [])
        yc = (sum(min(1.0, len(t.get("yardages") or []) / n) for t in tees)
              / len(tees)) if tees else 0.0
        rc = (sum(1 for t in tees if t.get("rating") and t.get("slope"))
              / len(tees)) if tees else 0.0
        result["confidence"] = {
            "overall":  round(0.40 * yc + 0.35 * pc + 0.25 * rc, 2),
            "pars":     round(pc, 2),
            "ratings":  round(rc, 2),
            "yardages": round(yc, 2),
        }


# ── CLI ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python ocr_llm.py <image_path>", file=sys.stderr)
        sys.exit(1)
    with open(sys.argv[1], "rb") as f:
        data = f.read()
    out = LLMScorecardOCR().process_image(data)
    print(json.dumps(out, indent=2))
