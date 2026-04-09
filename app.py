#!/usr/bin/env python3
"""
Galf — Golf companion web app.
Flask wrapper around Backend.py. Run with: python app.py
"""

import os
import socket

from flask import Flask, request, jsonify, render_template, send_from_directory

from Backend import GolfBackend, generate_scorecard_data

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------
_APP_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(_APP_DIR)  # Backend.py expects data/ relative to cwd

_FAVICON_DIR = os.path.join(_APP_DIR, "favicon")

app = Flask(__name__,
    template_folder=os.path.join(_APP_DIR, "templates"))

backend = GolfBackend()


# ---------------------------------------------------------------------------
# Main page
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/favicon.ico")
def favicon_ico():
    return send_from_directory(_FAVICON_DIR, "Favicon-32.png", mimetype="image/png")


@app.route("/favicon/<path:filename>")
def favicon_files(filename):
    return send_from_directory(_FAVICON_DIR, filename)


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
    backend.add_round(data)
    return jsonify({"ok": True})


@app.route("/api/rounds/<int:idx>", methods=["DELETE"])
def api_delete_round(idx):
    backend.delete_round(idx)
    return jsonify({"ok": True})


@app.route("/api/rounds/<int:idx>/scorecard")
def api_scorecard(idx):
    rounds = backend.get_rounds()
    if 0 <= idx < len(rounds):
        sc = generate_scorecard_data(backend, rounds[idx])
        return jsonify(sc)
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
    rounds = backend.get_rounds()
    is_sim = request.args.get("sim", "false").lower() == "true"
    best = backend.get_best_round(is_sim=is_sim)
    if best:
        result = dict(best)
        try:
            result["_index"] = rounds.index(best)
        except ValueError:
            result["_index"] = None
        return jsonify(result)
    return jsonify({})


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
    port = int(os.environ.get("GALF_PORT", 5003))
    ip = get_local_ip()
    print(f"\n{'='*50}")
    print(f"  Galf is running!")
    print(f"  Local:   http://127.0.0.1:{port}")
    print(f"  Network: http://{ip}:{port}")
    print(f"{'='*50}\n")
    app.run(host="0.0.0.0", port=port, debug=False)
