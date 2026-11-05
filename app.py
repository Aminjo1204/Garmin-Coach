"""Coach-Web-App. Start:  .venv\\Scripts\\python.exe app.py  → http://127.0.0.1:5057

Optionen:  --port 5057   --home DIR   (persönliche Daten in DIR statt im Projektordner, z. B. zum Ausprobieren)
"""

from __future__ import annotations

import argparse
import importlib
import mimetypes
import os
import threading

if __name__ == "__main__":
    _ap = argparse.ArgumentParser()
    _ap.add_argument("--port", type=int, default=int(os.environ.get("PORT", 5057)))
    _ap.add_argument("--home", help="Ordner für athlete.json, data/, plan/, feedback/, userdata/")
    ARGS = _ap.parse_args()
    if ARGS.home:
        os.makedirs(ARGS.home, exist_ok=True)
        os.environ["COACH_HOME"] = os.path.abspath(ARGS.home)

from flask import Flask, jsonify, request, send_from_directory  # noqa: E402

import coach.config  # noqa: E402
import coach.plan_builder  # noqa: E402
from coach import analysis, setup, userdata  # noqa: E402
from coach import sync as sync_mod  # noqa: E402

mimetypes.add_type("application/manifest+json", ".webmanifest")
mimetypes.add_type("text/javascript", ".js")

app = Flask(__name__, static_folder=str(coach.config.ROOT / "web"), static_url_path="")
_sync_lock = threading.Lock()


def _reload() -> None:
    """Nach neuem Profil/Plan: Module mit Werten aus athlete.json neu laden (Reihenfolge = Abhängigkeiten)."""
    for mod in (coach.config, userdata, coach.plan_builder, sync_mod, analysis, setup):
        importlib.reload(mod)


@app.get("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.get("/api/state")
def state():
    return jsonify(analysis.build_state())


@app.post("/api/sync")
def do_sync():
    if not _sync_lock.acquire(blocking=False):
        return jsonify({"busy": True}), 409
    try:
        info = sync_mod.sync(log=lambda *_: None)
    finally:
        _sync_lock.release()
    return jsonify({"sync": info, "state": analysis.build_state()})


@app.get("/api/activity/<int:aid>")
def detail(aid: int):
    d = analysis.activity_detail(aid)
    return (jsonify(d), 200) if d else (jsonify({"error": "keine FIT-Daten"}), 404)


@app.get("/api/userdata")
def get_userdata():
    return jsonify(userdata.load())


@app.post("/api/userdata")
def post_userdata():
    body = request.get_json(silent=True) or {}
    try:
        d = userdata.set_entry(body.get("kind"), body.get("key"), body.get("value"))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(d)


@app.get("/api/setup")
def get_setup():
    return jsonify(setup.suggestions())


@app.post("/api/setup")
def post_setup():
    try:
        res = setup.apply(request.get_json(silent=True) or {})
    except setup.SetupError as exc:
        return jsonify({"error": str(exc)}), 400
    _reload()
    return jsonify(res | {"state": analysis.build_state()})


@app.after_request
def no_cache(resp):
    resp.headers["Cache-Control"] = "no-store"
    return resp


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=ARGS.port, debug=False)
