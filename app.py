#!/usr/bin/env python3
"""
Galf — Golf companion web app.
Flask wrapper around Backend.py. Run with: python app.py
"""

import os
import socket

from flask import Flask, request, jsonify, render_template, send_from_directory

from models import db, Round
from Backend import GolfBackend, generate_scorecard_data, _round_to_dict

try:
    from scorecard_ocr import ScorecardOCR
    _ocr = ScorecardOCR()
    OCR_AVAILABLE = True
except Exception:
    OCR_AVAILABLE = False
    _ocr = None

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------
_APP_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(_APP_DIR)  # Backend.py expects data/ relative to cwd

_DATA_PATH = os.environ.get("DATA_PATH", os.path.join(_APP_DIR, "data"))
_APP_NAME = os.environ.get("APP_NAME", "Galf")

_STATIC_DIR = os.path.join(_APP_DIR, "templates", "static")

app = Flask(__name__,
    template_folder=os.path.join(_APP_DIR, "templates"),
    static_folder=_STATIC_DIR)

app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change-me-in-production")
os.makedirs(_DATA_PATH, exist_ok=True)
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{os.path.join(_DATA_PATH, 'galf.db')}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db.init_app(app)

with app.app_context():
    db.create_all()

backend = GolfBackend()


# ---------------------------------------------------------------------------
# Main page
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/favicon.ico")
@app.route("/galf.ico")
def favicon_ico():
    return send_from_directory(_STATIC_DIR, "galf.ico", mimetype="image/x-icon")


@app.route("/apple-touch-icon.png")
@app.route("/apple-touch-icon-precomposed.png")
def apple_touch_icon():
    return send_from_directory(_STATIC_DIR, "galf.png", mimetype="image/png")


@app.route("/templates/static/<path:filename>")
def favicon_files(filename):
    return send_from_directory(_STATIC_DIR, filename)


# ---------------------------------------------------------------------------
# API: Courses
# ---------------------------------------------------------------------------
@app.route("/api/courses")
def api_courses():
    return jsonify(backend.get_courses())


@app.route("/api/courses", methods=["POST"])
def api_add_course():
    data = request.get_json()
    backend.add_course(data)
    return jsonify({"ok": True})


@app.route("/api/courses/<name>", methods=["PUT"])
def api_update_course(name):
    data = request.get_json()
    backend.update_course(name, data)
    return jsonify({"ok": True})


@app.route("/api/courses/<name>", methods=["DELETE"])
def api_delete_course(name):
    backend.delete_course(name)
    return jsonify({"ok": True})


@app.route("/api/courses/scan", methods=["POST"])
def api_scan_scorecard():
    if not OCR_AVAILABLE or _ocr is None:
        return jsonify({"error": "OCR not available",
                        "tip": "Install opencv-python-headless and tesseract"}), 503

    if "image" not in request.files:
        return jsonify({"error": "No image uploaded"}), 400

    image_file = request.files["image"]
    image_bytes = image_file.read()
    if not image_bytes:
        return jsonify({"error": "Empty image file"}), 400

    try:
        result = _ocr.process_image(image_bytes)
    except ValueError as e:
        return jsonify({"error": "Could not read image",
                        "tip": "Try better lighting or a flatter angle",
                        "detail": str(e)}), 400
    except Exception as e:
        return jsonify({"error": "OCR processing failed",
                        "tip": "Try better lighting or a flatter angle",
                        "detail": str(e)}), 500

    return jsonify(result)


@app.route("/api/courses/scan/confirm", methods=["POST"])
def api_scan_confirm():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400
    try:
        backend.add_course(data)
    except (ValueError, KeyError) as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# API: Rounds
# ---------------------------------------------------------------------------
@app.route("/api/rounds")
def api_rounds():
    rt = request.args.get("round_type", "all")
    sort = request.args.get("sort", "recent")
    result = []
    for idx, rd in backend.get_filtered_rounds(round_type=rt, sort_by=sort):
        rd_copy = dict(rd)
        rd_copy["_index"] = idx
        result.append(rd_copy)
    return jsonify(result)


@app.route("/api/rounds", methods=["POST"])
def api_add_round():
    data = request.get_json()
    try:
        backend.add_round(data)
    except (ValueError, KeyError) as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    return jsonify({"ok": True})


@app.route("/api/rounds/<int:idx>", methods=["DELETE"])
def api_delete_round(idx):
    backend.delete_round(idx)
    return jsonify({"ok": True})


@app.route("/api/rounds/<int:idx>/scorecard")
def api_scorecard(idx):
    row = Round.query.filter_by(user_id=backend.user_id).order_by(Round.id).offset(idx).limit(1).first()
    if row:
        return jsonify(generate_scorecard_data(backend, _round_to_dict(row)))
    return jsonify({"error": "Not found"}), 404


# ---------------------------------------------------------------------------
# API: Clubs
# ---------------------------------------------------------------------------
@app.route("/api/clubs")
def api_clubs():
    return jsonify(backend.get_clubs_sorted_by_distance())


@app.route("/api/clubs", methods=["POST"])
def api_add_club():
    data = request.get_json()
    ok = backend.add_club(data)
    return jsonify({"ok": ok})


@app.route("/api/clubs/<name>", methods=["PUT"])
def api_update_club(name):
    data = request.get_json()
    ok = backend.update_club(name, data)
    return jsonify({"ok": ok})


@app.route("/api/clubs/<name>", methods=["DELETE"])
def api_delete_club(name):
    backend.delete_club(name)
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# API: Stats
# ---------------------------------------------------------------------------
@app.route("/api/stats")
def api_stats():
    return jsonify(backend.get_statistics())


@app.route("/api/stats/handicap")
def api_handicap():
    idx = backend.calculate_handicap_index()
    return jsonify({"handicap_index": idx})


@app.route("/api/stats/differentials")
def api_differentials():
    return jsonify(backend.get_score_differentials())


@app.route("/api/stats/advanced")
def api_advanced_stats():
    return jsonify(backend.get_advanced_statistics())


@app.route("/api/stats/club-analytics")
def api_club_analytics():
    return jsonify(backend.get_club_analytics())


@app.route("/api/stats/stroke-leaks")
def api_stroke_leaks():
    return jsonify(backend.get_stroke_leak_analysis())


@app.route("/api/stats/best-round")
def api_best_round():
    is_sim = request.args.get("sim", "false").lower() == "true"
    best, idx = backend.get_best_round(is_sim=is_sim)
    if best:
        result = dict(best)
        result["_index"] = idx
        return jsonify(result)
    return jsonify({})


# ---------------------------------------------------------------------------
# API: Training Sessions
# ---------------------------------------------------------------------------
@app.route("/api/training")
def api_training():
    limit = request.args.get("limit", type=int)
    return jsonify(backend.get_training_sessions(limit=limit))


@app.route("/api/training", methods=["POST"])
def api_add_training():
    data = request.get_json()
    result = backend.add_training_session(data)
    return jsonify(result)


@app.route("/api/training/<int:session_id>", methods=["DELETE"])
def api_delete_training(session_id):
    ok = backend.delete_training_session(session_id)
    return jsonify({"ok": ok})


@app.route("/api/training/template")
def api_training_template():
    return jsonify(backend.get_adaptive_drill_template())


# ---------------------------------------------------------------------------
# API: User Preferences
# ---------------------------------------------------------------------------
@app.route("/api/prefs")
def api_prefs():
    return jsonify(backend.user_prefs)


@app.route("/api/prefs", methods=["PUT"])
def api_update_prefs():
    data = request.get_json()
    backend.user_prefs.update(data)
    backend.save_user_prefs()
    return jsonify({"ok": True})


@app.route("/api/manual")
def api_manual():
    manual_path = os.path.join(_APP_DIR, "MANUAL.md")
    with open(manual_path, "r") as f:
        return f.read(), 200, {"Content-Type": "text/plain; charset=utf-8"}


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------
def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5003))
    ip = get_local_ip()
    print(f"\n{'='*50}")
    print(f"  {_APP_NAME} is running!")
    print(f"  Local:   http://127.0.0.1:{port}")
    print(f"  Network: http://{ip}:{port}")
    print(f"{'='*50}\n")
    app.run(host="0.0.0.0", port=port, debug=False)
