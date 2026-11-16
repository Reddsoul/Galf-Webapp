"""
Scorecard extraction via a LOCAL vision LLM.

Talks to any OpenAI-compatible chat endpoint — llama.cpp (llama-server),
Ollama, LM Studio — so the model runs entirely on your own hardware.
Stdlib only (urllib); Pillow used for downscaling when available.

Config (env vars)
-----------------
Server, model and API key are NOT configured here: the app passes them in
from Settings -> Scan LLM (saved only after Test Connection succeeds).
There are no defaults. The CLI at the bottom reads OCR_LLM_URL /
OCR_LLM_MODEL / OCR_LLM_API_KEY for ad-hoc testing.

URL formats, detected from the path:
  - OpenAI-compatible: base URL ending in /v1 (".../chat/completions" is
    appended) or the full /v1/chat/completions URL. vLLM, LiteLLM,
    llama.cpp, LM Studio, Ollama compat mode.
  - Ollama native: http://host:11434/api/chat (supports keep_alive).

Tuning env vars:
OCR_LLM_DEBUG       "1" logs the raw model output to stderr.
OCR_LLM_THINKING    "1" lets reasoning models think before answering (slower,
                    sometimes more accurate). Default "0" = thinking off via
                    chat_template_kwargs.enable_thinking (vLLM/Qwen-style).
OCR_LLM_TIMEOUT     Request timeout in seconds. Default: 180 (cold model
                    load + inference on modest hardware).
OCR_LLM_KEEP_ALIVE  Ollama native only. How long the model stays in RAM
                    after a scan. Default "0" = unload immediately.
                    Use e.g. "5m" while batch-scanning several cards.

The model runs on another box (the Spark LLM server), never on the NAS —
the app itself stays stdlib-light and runs fine on a 1 GB NAS.

Public interface:
    LLMScorecardOCR().process_image(image_bytes: bytes) -> dict
Raises RuntimeError when the endpoint is unreachable or returns unusable output.
"""

import base64
import io
import json
import os
import re
import sys
import urllib.error
import urllib.request


_PROMPT = """You are reading a photo of a golf scorecard. Extract its data as JSON.

Return ONLY a JSON object, no prose, matching exactly this schema:
{
  "course_name": string or null,   // course name (e.g. "Lakeside Course"); null if absent
  "club_name": string or null,     // club/facility name if distinct from course name
  "nine_hole_card": boolean,       // true if the card covers only 9 holes
  "pars": [int or null, ...],      // par per hole in hole order (9 or 18 values, each 3-6)
  "handicaps": [int, ...],         // stroke index / HDCP per hole (1-18), [] if absent
  "tee_boxes": [
    {
      "label": string,             // tee name EXACTLY as printed (e.g. "Black", "Championship", "Blue/White")
      "color": string or null,     // canonical color: Black/Blue/White/Yellow/Red/Gold/Green/Silver
      "rating": float or null,     // course rating (55.0-82.0)
      "slope": int or null,        // slope (55-155)
      "yardages": [int or null, ...] // yards per hole in hole order, null for an unreadable hole
    }
  ]
}

Rules:
- Include EVERY tee row printed on the card — every row of yardages is its own tee box, even if it has no rating/slope. Combo tees (e.g. "Blue/White"), forward/ladies tees and junior tees are separate entries. Cards commonly have 4-8 tee rows; count them before answering.
- Each tee box must have its own distinct label. Do not merge two rows into one.
- PAR row: the row labelled "Par" (or "Men's Par"). Do NOT confuse it with the Handicap/HCP/Stroke Index row (values 1-18) or a yardage row. If there are separate men's and ladies' par rows, use the men's. Pars are almost always 3, 4 or 5 and an 18-hole total is usually 68-73 — check the OUT/IN totals against your values.
- Ratings/slopes may sit next to the tee name, in a separate side table, or in a footer, often as "71.4/128" or under headers like "R/S", "Rating/Slope", "CR/SL". Match them to the right tee.
- Ladies/forward tees often have separate ratings — use the men's rating unless only one is printed.
- Hole order: 1..9 then 10..18. Front and back nine are often separate tables — concatenate them.
- Do NOT include OUT/IN/TOT column values in pars, handicaps, or yardages.
- Ratings often appear as "71.4/128" (rating/slope) near the tee name or in a side table.
- If a single value is unreadable, put null in that hole's position — never skip it, or every later hole shifts. Use [] only if the whole row is unreadable.
- Never invent values. Missing is better than wrong."""


class LLMScorecardOCR:

    def __init__(self, url, model, api_key=""):
        url = (url or "").strip().rstrip("/")
        model = (model or "").strip()
        if not url or not model:
            raise ValueError("Scan LLM not configured: URL and model are required")
        # Accept a bare OpenAI-style base URL (".../v1").
        if url.endswith("/v1"):
            url += "/chat/completions"
        self.url = url
        self.model = model
        self.api_key = (api_key or "").strip()
        self.thinking = os.environ.get("OCR_LLM_THINKING", "0") == "1"
        self.debug = os.environ.get("OCR_LLM_DEBUG", "0") == "1"
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
                # Headroom for reasoning models that think before the JSON.
                "max_tokens": 8192,
                "response_format": {"type": "json_object"},
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": _PROMPT},
                        {"type": "image_url",
                         "image_url": {"url": f"data:{mime};base64,{b64}"}},
                    ],
                }],
            }
            if not self.thinking:
                payload["chat_template_kwargs"] = {"enable_thinking": False}
        try:
            body = self._post(payload)
        except urllib.error.HTTPError as e:
            # Some servers reject response_format / chat_template_kwargs —
            # retry once without the optional extras.
            optional = ("response_format", "chat_template_kwargs")
            if e.code == 400 and any(k in payload for k in optional):
                for k in optional:
                    payload.pop(k, None)
                try:
                    body = self._post(payload)
                except (urllib.error.URLError, OSError, TimeoutError) as e2:
                    raise RuntimeError(f"LLM request failed ({self.url}): {e2}")
            else:
                raise RuntimeError(f"LLM request failed ({self.url}): {e}")
        except (urllib.error.URLError, OSError, TimeoutError) as e:
            raise RuntimeError(f"LLM endpoint unreachable ({self.url}): {e}")

        try:
            if self.native_ollama:
                text = body["message"]["content"]
            else:
                text = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            raise RuntimeError(f"Unexpected LLM response shape: {str(body)[:300]}")
        if not text:
            # Reasoning models can burn max_tokens before writing the answer.
            raise RuntimeError("LLM returned empty content (token limit hit?)")

        if self.debug:
            print(f"[ocr_llm] raw model output:\n{text}", file=sys.stderr)
        raw = self._parse_json_block(text)
        return self._coerce(raw)

    def check(self) -> dict:
        """Probe the endpoint: list models and confirm ours is served.
        OpenAI-compatible only (Ollama native has no /v1/models)."""
        if self.native_ollama:
            base = self.url.rsplit("/api/chat", 1)[0]
            models_url, key = base + "/api/tags", "models"
        else:
            models_url, key = self.url.rsplit("/chat/completions", 1)[0] + "/models", "data"
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        req = urllib.request.Request(models_url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            return {"ok": False, "error": f"HTTP {e.code} from {models_url}"}
        except (urllib.error.URLError, OSError, TimeoutError, ValueError) as e:
            return {"ok": False, "error": f"Unreachable: {e}"}
        items = (body.get(key) or []) if isinstance(body, dict) else []
        names = [m.get("id") or m.get("name") for m in items if isinstance(m, dict)]
        if self.model not in names:
            return {"ok": False, "models": names,
                    "error": f'Server is up, but model "{self.model}" is not listed.'}
        return {"ok": True, "models": names}

    # ── Helpers ───────────────────────────────────────────────────────────

    def _post(self, payload: dict) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        req = urllib.request.Request(
            self.url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    @staticmethod
    def _downscale(image_bytes: bytes, long_side: int = 2048):
        """Resize to keep prompts small; pass through untouched if PIL missing."""
        try:
            from PIL import Image
        except ImportError:
            mime = ("image/png" if image_bytes[:8] == b"\x89PNG\r\n\x1a\n"
                    else "image/webp" if image_bytes[8:12] == b"WEBP"
                    else "image/jpeg")
            return image_bytes, mime
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

        def _positional(vals, lo, hi):
            # Keep hole positions: an unreadable hole stays null instead of
            # being dropped (dropping shifts every later hole by one).
            out = [_int(v, lo, hi) for v in (vals or [])][:18]
            while out and out[-1] is None:
                out.pop()
            return out

        pars = _positional(raw.get("pars"), 3, 6)
        # Positional like pars: an unreadable hole stays null so later holes
        # keep their index (the editor fills blanks only).
        hcps = _positional(raw.get("handicaps"), 1, 18)

        tee_boxes = []
        for t in (raw.get("tee_boxes") or []):
            if not isinstance(t, dict):
                continue
            label = str(t.get("label") or "").strip()
            color = str(t.get("color") or "").strip().capitalize() or None
            if color not in ("Black", "Blue", "White", "Yellow", "Red",
                             "Gold", "Green", "Silver"):
                color = None
            yardages = _positional(t.get("yardages"), 50, 750)
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
            "tee_boxes":        tee_boxes,
            "pars":             pars,
            "handicaps":        hcps,
        }


# ── CLI ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python ocr_llm.py <image_path>", file=sys.stderr)
        sys.exit(1)
    with open(sys.argv[1], "rb") as f:
        data = f.read()
    out = LLMScorecardOCR(os.environ.get("OCR_LLM_URL"),
                          os.environ.get("OCR_LLM_MODEL"),
                          os.environ.get("OCR_LLM_API_KEY", "")).process_image(data)
    print(json.dumps(out, indent=2))
