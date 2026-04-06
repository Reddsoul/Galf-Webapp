#!/usr/bin/env python3
"""
Galf — Golf companion web app.
Flask wrapper around Backend.py. Run with: python app.py
Access from iPhone at http://<mac-local-ip>:5000
"""

import os
import socket
from functools import wraps

from flask import (
    Flask, request, jsonify, render_template, session, redirect, url_for
)

from Backend import GolfBackend, generate_scorecard_data

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------
# Resolve paths relative to this file so it works regardless of cwd
_APP_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(_APP_DIR)  # Backend.py expects Data/ relative to cwd

app = Flask(__name__, template_folder=os.path.join(_APP_DIR, "templates"))
app.secret_key = os.urandom(24)

# Single-user password gate
APP_PASSWORD = "galf"  # Change this to your preferred password

# Initialize backend
backend = GolfBackend()


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("authenticated"):
            if request.is_json or request.path.startswith("/api/"):
                return jsonify({"error": "Not authenticated"}), 401
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        pw = request.form.get("password", "")
        if pw == APP_PASSWORD:
            session["authenticated"] = True
            return redirect(url_for("index"))
        return render_template("login.html", error="Wrong password")
    return render_template("login.html", error=None)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ---------------------------------------------------------------------------
# Main page — serves the SPA shell
# ---------------------------------------------------------------------------
@app.route("/")
@login_required
def index():
    return render_template("index.html")


# ---------------------------------------------------------------------------
# API: Courses
# ---------------------------------------------------------------------------
@app.route("/api/courses")
@login_required
def api_courses():
    return jsonify(backend.get_courses())


@app.route("/api/courses", methods=["POST"])
@login_required
def api_add_course():
    data = request.get_json()
    backend.add_course(data)
    return jsonify({"ok": True})


@app.route("/api/courses/<name>", methods=["PUT"])
@login_required
def api_update_course(name):
    data = request.get_json()
    backend.update_course(name, data)
    return jsonify({"ok": True})


@app.route("/api/courses/<name>", methods=["DELETE"])
@login_required
def api_delete_course(name):
    backend.delete_course(name)
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# API: Rounds
# ---------------------------------------------------------------------------
@app.route("/api/rounds")
@login_required
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
@login_required
def api_add_round():
    data = request.get_json()
    backend.add_round(data)
    return jsonify({"ok": True})


@app.route("/api/rounds/<int:idx>", methods=["DELETE"])
@login_required
def api_delete_round(idx):
    backend.delete_round(idx)
    return jsonify({"ok": True})


@app.route("/api/rounds/<int:idx>/scorecard")
@login_required
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
@login_required
def api_clubs():
    return jsonify(backend.get_clubs_sorted_by_distance())


@app.route("/api/clubs", methods=["POST"])
@login_required
def api_add_club():
    data = request.get_json()
    ok = backend.add_club(data)
    return jsonify({"ok": ok})


@app.route("/api/clubs/<name>", methods=["PUT"])
@login_required
def api_update_club(name):
    data = request.get_json()
    ok = backend.update_club(name, data)
    return jsonify({"ok": ok})


@app.route("/api/clubs/<name>", methods=["DELETE"])
@login_required
def api_delete_club(name):
    backend.delete_club(name)
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# API: Stats
# ---------------------------------------------------------------------------
@app.route("/api/stats")
@login_required
def api_stats():
    return jsonify(backend.get_statistics())


@app.route("/api/stats/handicap")
@login_required
def api_handicap():
    idx = backend.calculate_handicap_index()
    return jsonify({"handicap_index": idx})


@app.route("/api/stats/differentials")
@login_required
def api_differentials():
    return jsonify(backend.get_score_differentials())


@app.route("/api/stats/advanced")
@login_required
def api_advanced_stats():
    return jsonify(backend.get_advanced_statistics())


@app.route("/api/stats/club-analytics")
@login_required
def api_club_analytics():
    return jsonify(backend.get_club_analytics())


@app.route("/api/stats/stroke-leaks")
@login_required
def api_stroke_leaks():
    return jsonify(backend.get_stroke_leak_analysis())


@app.route("/api/stats/best-round")
@login_required
def api_best_round():
    rounds = backend.get_rounds()
    best = backend.get_best_round()
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
@login_required
def api_prefs():
    return jsonify(backend.user_prefs)


@app.route("/api/prefs", methods=["PUT"])
@login_required
def api_update_prefs():
    data = request.get_json()
    backend.user_prefs.update(data)
    backend.save_user_prefs()
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------
def get_local_ip():
    """Get the machine's local IP for LAN access."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


if __name__ == "__main__":
    port = int(os.environ.get("GALF_PORT", 5001))
    ip = get_local_ip()
    print(f"\n{'='*50}")
    print(f"  Galf is running!")
    print(f"  Local:   http://127.0.0.1:{port}")
    print(f"  Network: http://{ip}:{port}")
    print(f"  Password: {APP_PASSWORD}")
    print(f"{'='*50}\n")
    app.run(host="0.0.0.0", port=port, debug=False)